from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	ORDER_ACTIONS_KEYBOARD, MODIFY_KEYBOARD, REMOVE_KEYBOARD, ORDER_RESPOND_KEYBOARD, ORDER_EXECUTOR_KEYBOARD,
	CANCEL_KEYBOARD, CONTINUE_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import send_notify_message
from bot.constants.patterns import CANCEL_PATTERN, CONTINUE_PATTERN
from bot.constants.static import ORDER_FIELD_DATA, ORDER_RESPONSE_MESSAGE_TEXT
from bot.entities import TGMessage
from bot.handlers.common import (
	get_section, update_order, go_back_section, edit_or_reply_message, load_orders,
	prepare_current_section, get_order_status, order_has_approved_executor, show_order_related_users, add_section,
	delete_messages_by_key, update_section, generate_categories_list
)
from bot.states.main import MenuState
from bot.utils import (
	match_query, data_to_string, validate_number, validate_date, extract_fields, get_formatted_date,
	generate_inline_markup, find_obj_in_list, format_output_text, update_text_by_keyword, generate_reply_markup
)


async def add_order_fields_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция добавления/обновления данных заказа на бирже """

	section = get_section(context)
	query_message = update.message.text

	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	field_name = local_data.get("order_field_name")
	order_id = local_data.get("order_id")

	# если нажата кнопка Отменить после выбора категорий у заказа, то прервем операцию и аернемся на уровень выше
	if match_query(CANCEL_PATTERN, query_message):
		if order_id:  # удалим созданный заказ при отмене
			await update_order(update.message, context, int(order_id), method="DELETE")

		state = await go_back_section(update, context, "back")
		message = await update.message.reply_text(
			"Создание заказа было отменено!",
			reply_markup=get_section(context).get("reply_markup")
		)
		chat_data["last_message_id"] = message.message_id
		return state

	# если продолжаем и категории еще не сохранены в локальной переменной order_data
	elif match_query(CONTINUE_PATTERN, query_message) and not local_data["order_data"].get("categories"):
		await update.message.delete()
		selected_categories = local_data.pop("selected_categories", None)
		if selected_categories:
			local_data["order_data"] = {"categories": list(selected_categories.keys())}
			return await new_order_callback(update, context)
		else:
			text = "Можно только выбирать из списка!"
			await edit_or_reply_message(context, text=text, message_type="warn", lifetime=3)
			return section["state"]

	elif not field_name:
		await update.message.delete()
		text = "Можно только выбирать из списка!"
		await edit_or_reply_message(context, text=text, message_type="warn", lifetime=3)
		return section["state"]

	# сохранение и валидация введенных данных
	state = await modify_order_fields_choice(update, context)
	if not state:  # если некорректно введены данные или ошибка чтения/сохранения заказа
		return section["state"]

	if field_name == "title":
		field_name = "description"
		title = "Добавьте подробное описание"

	elif field_name == "description":
		field_name = "price"
		title = f'Укажите желаемую цену за работы'

	elif field_name == "price":
		field_name = "expire_date"
		title = "Определите конечную дату выполнения работ или введите \\*️⃣ если срок не органичен"

	else:
		field_name = None
		title = None
		chat_data["local_data"].pop("order_data")

	if field_name and title:
		message = await update.message.reply_text(title, reply_markup=section["reply_markup"])
		chat_data["last_message_ids"].update({f'{field_name}_question': message.message_id})
		chat_data["local_data"].update({"order_field_name": field_name})

	if not field_name:  # если конец цикла добавления полей
		order = await load_orders(update.message, context, order_id=order_id)
		state = await go_back_section(update, context, "back")
		if order:
			message = await update.message.reply_text(
				f'✅ Ваш заказ _{order["title"]}_\n'
				f'успешно размещен на бирже услуг!\n'
				f'🗃 _{data_to_string(order.get("categories"), field_names="name", separator=", ")}_',
				reply_markup=get_section(context).get("reply_markup")
			)
			chat_data["last_message_id"] = message.message_id
		return state

	return section["state"]


async def modify_order_fields_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция обновления полей заказа дизайнера """
	section = get_section(context)
	is_new_order = section["state"] == MenuState.ADD_ORDER

	chat_data = context.chat_data
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	local_data = chat_data.setdefault("local_data", {})
	order_data = local_data.setdefault("order_data", {})
	field_name = local_data["order_field_name"]
	field_value = update.message.text.strip()
	message_text = field_value

	if field_name == "price":
		price = validate_number(field_value)
		if not price:
			await update.message.delete()
			chat_data["warn_message_id"] = await edit_or_reply_message(
				context,
				text=f'Цена указана некорректно!\nПовторите ввод',
				message=last_message_ids.get(field_name),
				message_type="warn",
				reply_markup=section["reply_markup"]
			)
			return

		field_value = price
		message_text = f'{field_value}₽'

	if field_name == "expire_date":
		if field_value != "*":
			date = validate_date(field_value)
			if not date:
				await update.message.delete()
				message = await edit_or_reply_message(
					context,
					message=last_message_ids.get(field_name),
					text=f'Дата указана некорректно!\nПовторите ввод.\n_Допустимый формат: дд.мм.гггг или *_',
					message_type="warn",
					reply_markup=section["reply_markup"]
				)
				chat_data["warn_message_id"] = message.message_id
				return

			message_text, field_value = date

		else:
			field_value = None
			message_text = "бессрочно"

		local_data["order_data"] = {"status": 1}

	data_changed = True
	order_data.update({field_name: field_value})
	order_id = local_data.get("order_id", None)
	if order_id:
		order = await load_orders(update.message, context, order_id=order_id)
		if not order:
			return
		data_changed = not bool(order[field_name] == field_value)

	order, error_text = await update_order(update.message, context, order_id, data=local_data["order_data"])
	if error_text:
		chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			message=last_message_ids.get(field_name),
			text=error_text,
			reply_markup=section["reply_markup"],
		)
		return

	await update.message.delete()
	local_data["order_data"] = {}
	if not order_id:
		local_data["order_id"] = order["id"]

	if data_changed:
		message_text = f'✅ *{message_text}*'

	elif field_name == "expire_date":
		message_text = f'✅ *{message_text}*'

	else:
		message_text = f'❕ *{message_text}*\n_данные идентичны!_'

	if not is_new_order:  # если это изменение заказа, то дополнительно к сообщению добавляем заголовок с названием поля
		message_text = f'{ORDER_FIELD_DATA[field_name]}:\n' + message_text

	message_id = await edit_or_reply_message(
		context,
		text=message_text,
		message=last_message_ids.get(field_name),
		reply_markup=section["reply_markup"]
	)

	# сохраним id измененного сообщения для удаления при возврате
	last_message_ids.update({field_name: message_id})

	return section["state"]


async def show_order_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк вывода детальной информации по заказу """
	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	order_id = int(query_data.lstrip("order_"))

	order = await load_orders(query.message, context, order_id=order_id)
	if not order:
		return section["state"]

	order_status, _ = get_order_status(order)
	order_price = f'{order["price"]}₽' if order["price"] else "по договоренности"
	category_list = " / ".join(extract_fields(order["categories"], "name")).lower()

	# сохраним временно данные заказа для других колбэков на текущем и следующих уровнях меню
	local_data = context.chat_data.setdefault("local_data", {})
	local_data.update({
		"order_id": order_id,
		"executor_id": order.get("executor", None)
	})
	user_role = section.get("user_role", "contender")
	user_is_owner = order["owner"] == context.user_data["details"]["id"]
	user_is_contender = order["executor"] == context.user_data["details"]["id"]
	date_string, expire_date, current_date = get_formatted_date(order["expire_date"])

	state = section["state"]
	menu_markup = back_menu

	message = await query.message.reply_text(f'*{order["title"]}*', reply_markup=menu_markup)
	messages = [message]
	inline_markup = None

	if user_role != "creator" and user_is_contender:  # если пользователь является выбранным претендентом
		if order["status"] == 1:  # и заказ активный
			if order_has_approved_executor(order):  # и это подтвержденный исполнитель, то предложим сдать работу
				inline_markup = generate_inline_markup(
					ORDER_ACTIONS_KEYBOARD[4],
					callback_data=f'order_{order_id}__action_4'
				)

			else:  # иначе предложим принять/отклонить заказ
				inline_markup = generate_inline_markup(
					[[ORDER_ACTIONS_KEYBOARD[2]], [ORDER_ACTIONS_KEYBOARD[3]]],
					callback_data=['2', '3'],
					callback_data_prefix=f'order_{order_id}__action_'
				)

	elif user_role == "creator" and user_is_owner:
		if order["status"] == 0:  # заказ приостановлен, можно изменить и удалить
			if not expire_date or current_date <= expire_date:  # если срок актуален, то можно разместить, изменить
				inline_markup = generate_inline_markup(
					[[ORDER_ACTIONS_KEYBOARD[0]], MODIFY_KEYBOARD, REMOVE_KEYBOARD],
					callback_data=['0', '10', '11'],
					callback_data_prefix=f'order_{order_id}__action_'
				)

			else:
				inline_markup = generate_inline_markup(
					[MODIFY_KEYBOARD, REMOVE_KEYBOARD],
					callback_data=['10', '11'],
					callback_data_prefix=f'order_{order_id}__action_'
				)

		elif order['executor']:  # если заказчик выбрал исполнителя
			if order["status"] == 4:  # заказ досрочно завершен, то можно только удалить
				inline_markup = generate_inline_markup(
					REMOVE_KEYBOARD,
					callback_data=f'order_{order_id}__action_11'
				)

			elif order["status"] == 2:  # заказ в стадии сдачи, то предложить кнопки: принять или на доработку
				inline_markup = generate_inline_markup(
					[[ORDER_ACTIONS_KEYBOARD[5]], [ORDER_ACTIONS_KEYBOARD[6]]],
					callback_data=['5', '6'],
					callback_data_prefix=f'order_{order_id}__action_'
				)

			elif order["status"] == 1:  # заказ активный
				# и исполнитель начал выполнять заказ, то предложить досрочно завершить
				if order_has_approved_executor(order):
					inline_markup = generate_inline_markup(
						ORDER_ACTIONS_KEYBOARD[7],
						callback_data=f'order_{order_id}__action_7'
					)

		elif order["status"] == 1:  # если у заказа нет исполнителя и заказ активный
			# и срок исполнения не истек или дата бессрочная, то можно приостановить заказ
			if not expire_date or current_date <= expire_date:
				inline_markup = generate_inline_markup(
					ORDER_ACTIONS_KEYBOARD[1],
					callback_data=f'order_{order_id}__action_1'
				)
			else:  # если просрочен, то сменим статус на приостановлено и разрешим только править или удалить
				inline_markup = generate_inline_markup(
					[MODIFY_KEYBOARD, REMOVE_KEYBOARD],
					callback_data=['10', '11'],
					callback_data_prefix=f'order_{order_id}__action_'
				)
				# обновим запись и получим новый статус
				data = {"status": 0, "responded_users": []}
				order, error_text = await update_order(query.message, context, order_id, data=data)
				if error_text:
					message = await query.message.reply_text(text=error_text)
					context.chat_data["warn_message_id"] = message.message_id

				order_status, _ = get_order_status(order)

	# если это пока никто и заказ активный, то предложим откликнуться или снять отклик
	elif order["status"] == 1:
		user_id = context.user_data["details"]["id"]
		responded_user, _ = find_obj_in_list(order["responded_users"], {"id": user_id})
		action_code = int(bool(responded_user))  # флаг: пользователь уже есть в списке откликнувшихся или нет
		responded_user_counter = f' ({len(order["responded_users"]) or "0"})'
		inline_markup = generate_inline_markup(
			[ORDER_RESPOND_KEYBOARD[action_code] + responded_user_counter],
			callback_data=f'order_{order_id}__action_{20 + action_code}'
		)

	message = await query.message.reply_text(
		f'`{order["description"]}`'
		f'{format_output_text("_Категория_", category_list, tag="_")}\n'
		f'{format_output_text("Автор заказа", order["owner_name"] if not user_is_owner else "", tag="*")}'
		f'{format_output_text(ORDER_FIELD_DATA["price"], order_price, tag="*")}'
		f'{format_output_text(ORDER_FIELD_DATA["expire_date"], date_string if date_string else "не установлен", tag="*")}\n'
		f'{format_output_text("Статус", order_status, tag="*")}',
		reply_markup=inline_markup
	)
	messages.append(message)

	# отобразим исполнителя или всех претендентов, которые откликнулись на заказ дизайнера,
	# если это владелец заказа, а не исполнитель
	if user_role == "creator" and order["status"] > 0:
		messages += await show_order_related_users(query.message, context, order)

	add_section(
		context,
		state=state,
		messages=messages,
		query_message=query_data,
		reply_markup=menu_markup,
		save_full_messages=True
	)

	return state


async def manage_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк смены статуса заказа пользователем """

	query = update.callback_query
	await query.answer()

	section = get_section(context)
	query_data = query.data
	query_list = query_data.split('__')

	if len(query_list) < 2:
		return None

	user_id = context.user_data["details"]["id"]
	local_data = context.chat_data.setdefault("local_data", {})
	executor_id = local_data.get("executor_id", None)
	order_id = int(query_list[0].lstrip("order_"))
	action_code = int(query_list[1].lstrip("action_"))
	order = await load_orders(query.message, context, order_id)
	status = order["status"]
	notify_message = {}
	decline_notify_message = {}
	params = {}

	tg_messages = section["messages"]
	title_message = tg_messages.pop(0)  # извлечем сообщение с заголовком текущей секции
	order_details_message = tg_messages.pop(0)  # извлечем сообщение с описанием заказа
	inline_markup = None
	action_message = {"message": context.chat_data.get("last_message_id", None)}

	# если заказ удаляется
	if action_code == 11:
		action_message["text"] = "_Хотите удалить заказ навсегда?_"
		action_message["reply_markup"] = generate_inline_markup(
			["Да, хочу", "Нет, передумал"],
			callback_data=["yes", "no"],
			callback_data_prefix=f'remove_order_{order_id}__'
		)

	# если заказ редактируется
	elif action_code == 10:
		action_message["text"] = "_Что желаете изменить ?_"
		action_message["reply_markup"] = generate_inline_markup(
			list(ORDER_FIELD_DATA.values()),
			callback_data=list(ORDER_FIELD_DATA.keys()),
			callback_data_prefix=f'modify_order_{order_id}__'
		)

	# если соискатель откликнулся или отозвал свою кандидатуру еще до утверждения
	elif action_code in [20, 21]:
		action_index = action_code - 20
		action_message["text"] = ORDER_RESPONSE_MESSAGE_TEXT[action_index]
		action_message["error"] = f'Не удалось {"снять" if action_index == 1 else "оставить"} Вашу заявку'

		if action_index == 0:  # если претендент откликнулся на заказ
			params = {"add_user": user_id}
			username = context.user_data["details"]["name"] or context.user_data["details"]["username"]
			message_text = f'Пользователь откликнулся на Ваш заказ:\n _"{order["title"]}"_\n'
			notify_message = {"user_id": order["owner"], "from_name": username, "text": message_text}
			responded_user_counter = f' ({len(order["responded_users"]) + 1})'

		else:  # если претендент на заказ отзывает свой отклик до выбора его исполнителем
			params = {"remove_user": user_id}
			responded_user_counter = f' ({len(order["responded_users"]) - 1 if order["responded_users"] else 0})'

		action_index = abs(action_code - 21)
		inline_markup = generate_inline_markup(
			[ORDER_RESPOND_KEYBOARD[action_index] + responded_user_counter],
			callback_data=f'order_{order_id}__action_2{action_index}'
		)

	# если заказ досрочно завершен
	elif action_code == 7:
		status = 4
		action_message["text"] = "Заказ был досрочно завершен!"
		message_text = f'Информируем о том, что взятый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'был завершен владельцем в одностороннем порядке!\n\n' \
		               f'_Для получения комментариев можете обратиться к заказчику напрямую._'
		notify_message = {"user_id": executor_id, "from_name": order["owner_name"], "text": message_text}

	# если заказ отправлен на доработку
	elif action_code == 6:
		status = 1
		action_message["text"] = "Вы отказались принять работы!\nУведомление о доработке заказа отправлено исполнителю!"
		message_text = f'Информируем о том, что взятый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'не был принят и требует доработки!\n\n' \
		               f'_Для уточнения деталей обратитесь к заказчику напрямую._'
		notify_message = {"user_id": executor_id, "from_name": order["owner_name"], "text": message_text}

	# если заказ принят заказчиком
	elif action_code == 5:
		status = 3
		action_message["text"] = "Вы приняли работы у исполнителя вашего заказа!"
		message_text = f'Информируем о том, что взятый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'был успешно принят заказчиком!'
		notify_message = {"user_id": executor_id, "from_name": order["owner_name"], "text": message_text}

	# если заказ сдается исполнителем
	elif action_code == 4:
		status = 2
		action_message["text"] = "Вы инициировали процесс передачи выполненных работ...\nОжидайте ответ от заказчика!"
		message_text = f'Информируем о том, что исполнитель предлагает Вам принять работы по заказу:\n' \
		               f'_"{order["title"]}"_'
		notify_message = {"user_id": order["owner"], "from_name": order["executor_name"], "text": message_text}

	# если запрос начать работу отклонен выбранным претендентом
	elif action_code == 3:
		status = 1
		params = {"clear_executor": user_id}
		action_message["text"] = "Вы отклонили предложение на выполнение заказа!"
		username = context.user_data["details"]["name"] or context.user_data["details"]["username"]
		message_text = f'Информируем о том, что претендент на выполнение заказа:\n_"{order["title"]}"_\n' \
		               f'отказался от начала работ!'
		decline_notify_message = {"user_id": order["owner"], "from_name": username, "text": message_text}

		# создадим сообщение для других соискателей кроме отказавшегося претендента
		message_text = f'Информируем о том, что рассматриваемый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'по прежнему актуален!\nЗаказчик рассматривает Вашу кандидатуру.'
		notify_message = {"user_id": [], "from_name": order["owner_name"], "text": message_text}
		for user in order["responded_users"]:
			if user["id"] != user_id:
				notify_message["user_id"].append(user["id"])

	# если запрос подтвержден выбранным претендентом
	elif action_code == 2:
		status = 1
		params = {"remove_user": user_id}  # удалим пользователя из списка соискателей
		action_message["text"] = "Ваш статус исполнителя успешно подтвержден!"
		username = context.user_data["details"]["name"] or context.user_data["details"]["username"]
		message_text = f'Информируем о том, что претендент на выполнение заказа:\n_"{order["title"]}"_' \
		               f'подтвердил согласие выполнить работу!'
		notify_message = {"user_id": order["owner"], "from_name": username, "text": message_text}

		# создадим сообщение с отказом всем соискателям кроме исполнителя
		message_text = f'Информируем о том, что рассматриваемый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'был предложен другому пользователю.\nВозможно в будущем еще удастся поработать с Вами.\nУдачи!'
		decline_notify_message = {"user_id": [], "from_name": order["owner_name"], "text": message_text}
		for user in order["responded_users"]:
			if user["id"] != user_id:
				decline_notify_message["user_id"].append(user["id"])

	# если приостановлен заказ, то добавим кнопки: активировать, изменить и удалить
	elif action_code == 1:
		status = 0
		action_message["text"] = "Заказ приостановлен!"
		# создадим сообщение для всех соискателей об отмене заказа
		message_text = f'Информируем о том, что рассматриваемый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'был отозван самим заказчиком!'
		notify_message = {"user_id": [], "from_name": order["owner_name"], "text": message_text}
		for user in order["responded_users"]:
			notify_message["user_id"].append(user["id"])

		inline_markup = generate_inline_markup(
			[[ORDER_ACTIONS_KEYBOARD[0]], MODIFY_KEYBOARD, REMOVE_KEYBOARD],
			callback_data=['0', '10', '11'],
			callback_data_prefix=f'order_{order_id}__action_'
		)

	# если заказ размещен, то добавим кнопку: снять заказ
	elif action_code == 0:
		status = 1
		action_message["text"] = "Заказ был успешно размещен на бирже!"
		inline_markup = generate_inline_markup(
			[ORDER_ACTIONS_KEYBOARD[1]],
			callback_data=['1'],
			callback_data_prefix=f'order_{order_id}__action_'
		)

	if action_code < 10 or action_code >= 20:
		data = {"status": status} if status is not None else {}
		order, error_text = await update_order(query.message, context, order_id, params=params, data=data)
		if not error_text:
			if order["status"] == 0:  # если заказ остановлен, удалим с экрана список откликнувшихся и его подзаголовок
				await delete_messages_by_key(context, tg_messages)
				tg_messages = []

			# обновим статус в сообщении с описанием заказа
			order_status, _ = get_order_status(order)
			try:
				order_details_message = await query.message.edit_text(
					text=update_text_by_keyword(query.message.text_markdown, "Статус:", f'Статус: *{order_status}*'),
					reply_markup=inline_markup
				)
				# обновим сообщения в текущей секции
				order_details_message = TGMessage.create_message(order_details_message)

			except TelegramError:
				pass

			# отправим сообщение пользователям с уведомлением о новом статусе заказа
			if notify_message:
				await send_notify_message(context, **notify_message)

			# отправим сообщение соискателям с уведомлением об отказе
			if decline_notify_message:
				await send_notify_message(context, **decline_notify_message)

		else:
			action_message["text"] = error_text

	# выведем сообщение о действии, изменении заказа или ошибке
	if action_message.get("text"):
		action_message.pop("error", None)
		message = await edit_or_reply_message(context, **action_message)
		context.chat_data["last_message_id"] = message.message_id

	section["messages"] = [title_message, order_details_message] + tg_messages
	update_section(context, messages=section["messages"])


async def select_order_executor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк выбора и снятия дизайнером пользователя на роль исполнителя заказа """

	query = update.callback_query
	await query.answer()

	query_data = query.data
	query_list = query.data.split('__')

	if len(query_list) < 2:
		return

	user_is_selected = len(query_list) > 2
	order_id = int(query_list[0].lstrip("order_"))
	executor_id = int(query_list[1].lstrip("executor_"))
	order = context.chat_data["orders"][order_id]
	last_message_id = context.chat_data.get("last_message_id", None)

	section = get_section(context)
	tg_messages = section.get("messages", [])
	contender_messages = []
	error_text = None

	if order["status"] == 0:
		error_text = "🚫 Операция недоступна если заказ не активирован!"

	elif order["status"] > 2:
		error_text = "🚫 Операция недоступна если заказ завершен!"

	if error_text:
		context.chat_data["last_message_id"] = await edit_or_reply_message(context, error_text, message=last_message_id)
		return

	title_message = tg_messages.pop(0)  # извлечем сообщение с заголовком раздела
	order_details_message = tg_messages.pop(0)  # извлечем сообщение с описанием заказа
	contenders_title_message = tg_messages.pop(0)  # извлечем сообщение с заголовком списка претендентов

	inline_markup = None

	# Выберем текущего претендента в качестве предполагаемого исполнителя
	if not user_is_selected:
		order, error_text = await update_order(query.message, context, order_id, data={"executor": executor_id})
		if error_text:
			message_id = await edit_or_reply_message(context, error_text, message=last_message_id)
			context.chat_data["last_message_id"] = message_id
			return

		# удалим кнопку выбора у всех претендентов кроме выбранного
		for message in tg_messages:
			if message.message_id != query.message.message_id:
				details_keyboard = message.reply_markup.inline_keyboard[0][0]
				button = InlineKeyboardButton(details_keyboard.text, callback_data=details_keyboard.callback_data)
				_message = await edit_or_reply_message(
					context,
					text=message.text,
					message=message.message_id,
					reply_markup=InlineKeyboardMarkup([[button]]),
					return_only_id=False
				)

			else:
				# обновим кнопку текущего сообщения
				user_markup = generate_inline_markup(
					[[ORDER_EXECUTOR_KEYBOARD[0], ORDER_EXECUTOR_KEYBOARD[2]]],
					callback_data=["user_" + str(executor_id), query_data + "__is_selected"]
				)
				_message = await query.message.edit_reply_markup(user_markup)

			contender_messages.append(TGMessage.create_message(_message))

	# если пользователь уже выбран на роль исполнителя, то откажемся от него и отобразим оставшихся претендентов
	else:
		# обновление данных заказа с пустым значением executor и удалим его из претендентов
		order, error_text = await update_order(query.message, context, order_id, params={"clear_executor": executor_id})
		if error_text:
			message_id = await edit_or_reply_message(context, error_text, message=last_message_id)
			context.chat_data["last_message_id"] = message_id
			return

		# добавим кнопки выбора у оставшихся претендентов
		for message in tg_messages:
			if message.message_id != query.message.message_id:
				details_keyboard = message.reply_markup.inline_keyboard[0][0]
				user_id = details_keyboard.callback_data.lstrip("user_")
				buttons = [
					InlineKeyboardButton(details_keyboard.text, callback_data=details_keyboard.callback_data),
					InlineKeyboardButton(
						ORDER_EXECUTOR_KEYBOARD[1],
						callback_data=f'order_{order["id"]}__executor_{user_id}'
					)
				]

				_message = await edit_or_reply_message(
					context,
					text=message.text,
					message=message.message_id,
					reply_markup=InlineKeyboardMarkup([buttons]),
					return_only_id=False
				)
				contender_messages.append(TGMessage.create_message(_message))

		# удалим текущее сообщение с исполнителем после отказа
		await query.message.delete()

		# обновим кнопку в сообщении с описанием заказа
		inline_markup = generate_inline_markup(
			ORDER_ACTIONS_KEYBOARD[1],
			callback_data=f'order_{order_id}__status_1'
		)

	# обновим сообщение с описанием заказа: сменим статус и заменим кнопку
	order_status, _ = get_order_status(order)

	modified_text = update_text_by_keyword(order_details_message.text, "Статус:", f'Статус: *{order_status}*')
	_message = await edit_or_reply_message(
		context,
		text=modified_text,
		message=order_details_message.message_id,
		reply_markup=inline_markup,
		return_only_id=False
	)
	order_details_message = TGMessage.create_message(_message)

	update_section(
		context,
		messages=[title_message, order_details_message, contenders_title_message] + contender_messages
	)


async def modify_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк изменения заказа дизайнера """

	query = update.callback_query
	await query.answer()

	query_data = query.data.split("__")
	button_type = query_data[-1]
	chat_data = context.chat_data
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	local_data = chat_data.setdefault("local_data", {})

	order_title = ORDER_FIELD_DATA.get(button_type, "")
	if order_title:
		local_data["order_field_name"] = button_type
		message_text = f'*{order_title}*\n_Введите новое значение_'
		if button_type == "expire_date":
			message_text += " в формате: _дд.мм.гггг_ или введите символ *️⃣ для бессрочного варианта."
	else:
		message_text = "_⚠️ Некорректное поле!_"

	message = await query.message.reply_text(message_text)
	last_message_ids[button_type] = message.message_id

	return MenuState.MODIFY_ORDER


async def remove_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк удаления заказа дизайнера """

	query = update.callback_query
	await query.answer()

	query_data = query.data.lstrip('remove_order_').split("__")
	if len(query_data) < 2:
		return

	order_id = int(query_data[0])
	button_type = query_data[-1]
	last_message_id = context.chat_data.get("last_message_id", None)

	if button_type == "yes":
		order, error_text = await update_order(query.message, context, order_id, method="DELETE")
		message_text = "✔️ Ваш заказ успешно удален!"
		if error_text:
			message_text = f'❗️{error_text}'
		message_id = await edit_or_reply_message(context, text=message_text, message=last_message_id)
		context.chat_data["last_message_id"] = message_id

	else:
		await delete_messages_by_key(context, last_message_id)


async def new_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк размещения заказа на бирже """

	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	order_categories = local_data.get("order_data", {}).get("categories")
	section = get_section(context)
	if section["state"] != MenuState.ADD_ORDER:
		section = await prepare_current_section(context, leave_messages=True)

	state = MenuState.ADD_ORDER
	selected_cat = section.get("selected_cat")

	local_data["order_data"] = {
		"owner": context.user_data["details"]["id"],
		"status": 0,
	}

	# если пользователь находится в категории и там размещает заказ или она уже выбрана, то перейдем к названию задачи
	if order_categories or selected_cat:
		local_data["order_data"].update({"categories": order_categories or [selected_cat]})
		local_data["order_field_name"] = "title"
		menu_markup = generate_reply_markup([CANCEL_KEYBOARD], one_time_keyboard=False)
		reply_message = await query.message.reply_text(f'Как назовем задачу?', reply_markup=menu_markup)
		messages = [reply_message.message_id]

	# иначе перейдем к выбору категорий
	else:
		# local_data["order_data"].update({"categories": []})
		menu_markup = generate_reply_markup([CONTINUE_KEYBOARD], one_time_keyboard=False)
		title = str(state).upper()

		reply_message = await query.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		messages = [reply_message.message_id]

		inline_markup = await generate_categories_list(query.message, context, groups=1, button_type="checkbox")
		if not inline_markup:
			return section["state"]

		subtitle = '🗃 В какой категории будем размещать заявку?'
		inline_message = await query.message.reply_text(subtitle, reply_markup=inline_markup)
		messages.append(inline_message.message_id)

	if section["state"] != MenuState.ADD_ORDER:
		add_section(context, state=state, messages=messages, reply_markup=menu_markup)

	else:
		update_section(
			context,
			messages=section["messages"] + messages,
			reply_markup=menu_markup
		)

	return state
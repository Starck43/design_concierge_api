from typing import Optional, Tuple, Literal, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	CANCEL_KEYBOARD, CONTINUE_KEYBOARD, REPLY_KEYBOARD, MODIFY_KEYBOARD, REMOVE_KEYBOARD, ORDER_ACTIONS_KEYBOARD,
	ORDER_RESPOND_KEYBOARD, ORDER_EXECUTOR_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import place_new_order_message, restricted_access_message
from bot.constants.patterns import (
	BACK_PATTERN, CANCEL_PATTERN, CONTINUE_PATTERN, NEW_DESIGNER_ORDER_PATTERN, DONE_ORDERS_PATTERN
)
from bot.constants.static import ORDER_FIELD_DATA, ORDER_RESPONSE_MESSAGE_TEXT, ORDER_STATUS, ORDER_RELATED_USERS_TITLE
from bot.entities import TGMessage
from bot.handlers.common import (
	delete_messages_by_key, get_section, prepare_current_section, add_section, update_section, go_back_section,
	generate_categories_list, edit_or_reply_message, update_order, load_orders, load_user, send_message_to
)
from bot.handlers.details import show_user_card_message
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	match_query, validate_number, validate_date, extract_fields, get_formatted_date, generate_inline_markup,
	find_obj_in_list, format_output_text, update_text_by_keyword, generate_reply_markup, format_output_link,
	detect_social, find_obj_in_dict, data_to_string
)


async def designer_orders_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция отображения архивных заказов дизайнера на Бирже услуг """

	await update.message.delete()
	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]

	# Подраздел - НОВЫЙ ЗАКАЗ, если это Дизайнер
	if match_query(NEW_DESIGNER_ORDER_PATTERN, update.message.text) and priority_group == Group.DESIGNER:
		return await new_order_callback(update, context)

	section = await prepare_current_section(context, keep_messages=True)
	query_message = section.get("query_message") or update.message.text
	state = MenuState.DESIGNER_ORDERS

	# Подраздел - АРХИВНЫЕ ЗАКАЗЫ
	if match_query(DONE_ORDERS_PATTERN, query_message) and priority_group == Group.DESIGNER:
		params = {"owner_id": user_details["id"], "status": [3, 4]}
		orders = await load_orders(update.message, context, params=params)

		messages = [update.message.message_id]
		if orders:
			extra_messages = await show_user_orders(
				update.message,
				orders,
				title=query_message,
				user_role="creator",
			)
			# объединим список id сообщений 'Мои заказы' с id сообщений из 'Архивные заказы'
			messages += [message.message_id for message in extra_messages]

		else:
			message = await update.message.reply_text(f'❕Список пустой.', reply_markup=back_menu)
			messages.append(message.message_id)

		# дополним список текущих сообщений архивными
		update_section(context, messages=section["messages"] + messages)

	else:
		return await go_back_section(update, context)

	return state


async def order_details_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция обработки сообщений в чате между заказчиком и исполнителем """

	section = get_section(context)
	section["messages"].append(update.message.message_id)
	query_message = update.message.text
	user_details = context.user_data["details"]
	local_data = context.chat_data.setdefault("local_data", {})
	order_id = context.chat_data["selected_order"]
	reply_to_message_id = local_data.get("reply_to_message_id", None)

	order = await load_orders(update.message, context, order_id=order_id)
	user_is_owner = order["owner"] == user_details["id"]
	user_id = order["executor_id"] if user_is_owner else order["owner_id"]
	name = user_details["contact_name"] or user_details["name"]
	username = user_details["username"]
	message_id = update.message.message_id

	# если заказчик выбрал претендента, то все сообщения будут считаться перепиской
	if not match_query(BACK_PATTERN, query_message) and order["executor"]:
		inline_markup = generate_inline_markup(
			REPLY_KEYBOARD,
			callback_data=f'order_{order_id}__message_id_{message_id}'
		)
		try:
			await send_message_to(
				context,
				user_id=user_id,
				text=query_message,
				from_name=name,
				from_username=username,
				reply_to_message_id=reply_to_message_id,
				reply_markup=inline_markup
			)
		except TelegramError:
			# Message to reply not found
			# TODO: отправить повторно с текстом пред. сообщения взятого с сервера по reply_to_message_id
			await send_message_to(
				context,
				user_id=user_id,
				text=query_message,
				from_name=name,
				from_username=username,
				reply_markup=inline_markup
			)

		context.chat_data["last_message_id"] = await edit_or_reply_message(
			context,
			text="Сообщение отправлено!",
			message=context.chat_data.get("last_message_id"),
			delete_before_reply=True,
			reply_markup=section["reply_markup"]
		)

	else:
		return await go_back_section(update, context)

	return section["state"]


async def reply_to_order_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк ответа пользователей на сообщения друг другу """

	query = update.callback_query
	await query.answer()

	query_data = query.data.rsplit("__")
	order_id = int(query_data[0].lstrip("order_"))
	message_id = int(query_data[-1].lstrip("message_id_"))

	section = get_section(context)
	local_data = context.chat_data.setdefault("local_data", {})
	context.chat_data["selected_order"] = order_id
	local_data["reply_to_message_id"] = message_id

	context.chat_data["last_message_id"] = await edit_or_reply_message(
		context,
		text="Ваш ответ на сообщение:",
		message=context.chat_data.get("last_message_id", None),
		delete_before_reply=True,
		reply_markup=section["reply_markup"]
	)
	return MenuState.ORDER


async def add_order_fields_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция добавления/обновления данных заказа на бирже """

	section = get_section(context)
	query_message = update.message.text

	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	field_name = local_data.get("order_field_name")
	order_id = chat_data.get("selected_order")

	# если нажата кнопка Отменить после выбора категорий у заказа, то прервем операцию и аернемся на уровень выше
	if match_query(CANCEL_PATTERN, query_message):
		if order_id:  # удалим созданный заказ при отмене
			await update_order(update.message, context, int(order_id), method="DELETE")

		state = await go_back_section(update, context, message_text="🚫 Создание заказа было отменено!")
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
		local_data["owner"] = context.user_data["details"]["id"]
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
		categories = f'🗃 _{data_to_string(order.get("categories"), field_names="name", separator=", ")}_'
		message_text = f'✅ Заказ *{order["title"]}* успешно размещен на бирже услуг!\n{categories}'

		state = await go_back_section(update, context, message_text=message_text)

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
	order_id = chat_data.get("selected_order", None)
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
		context.chat_data["selected_order"] = order["id"]

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
	data = query_data.rsplit("__")
	order_id = int(data[0].lstrip("order_"))
	user_role = section.get("user_role", "contender")
	if len(data) > 1:
		user_role = data[-1]

	order = await load_orders(query.message, context, order_id=order_id)
	if not order:
		return

	order_status, _ = get_order_status(order)
	order_price = f'{order["price"]}₽' if order["price"] else "по договоренности"
	category_list = " / ".join(extract_fields(order["categories"], "name")).lower()

	# сохраним id заказа для других колбэков на текущем и следующих уровнях меню
	context.chat_data["selected_order"] = order_id
	user_is_owner = order["owner"] == context.user_data["details"]["id"]
	user_is_contender = order["executor"] == context.user_data["details"]["id"]
	date_string, expire_date, current_date = get_formatted_date(order["expire_date"])

	state = MenuState.ORDER
	menu_markup = back_menu

	message = await query.message.reply_text(f'*{order["title"]}*', reply_markup=menu_markup)
	messages = [message]
	inline_markup = None
	info_message_text = None

	if user_role != "creator" and user_is_contender:  # если пользователь является выбранным претендентом
		if order["status"] == 1:  # и заказ активный
			if order_has_approved_executor(order):  # и это подтвержденный исполнитель, то предложим сдать работу
				inline_markup = generate_inline_markup(
					[[ORDER_ACTIONS_KEYBOARD[8]], [ORDER_ACTIONS_KEYBOARD[4]]],
					callback_data=[
						f'owner_contact_info_{order["owner"]}',
						f'order_{order_id}__action_4'
					]
				)

			else:  # иначе предложим принять/отклонить заказ
				order_status = "необходимо заключить договор 🖋"
				inline_markup = generate_inline_markup(
					[[ORDER_ACTIONS_KEYBOARD[8]], [ORDER_ACTIONS_KEYBOARD[2]], [ORDER_ACTIONS_KEYBOARD[3]]],
					callback_data=[
						f'owner_contact_info_{order["owner"]}',
						f'apply_order_{order_id}',
						f'order_{order_id}__action_3'
					]
				)
				info_message_text = "❕ Перед началом работ рекомендуем связаться с заказчиком предоставленным способом, " \
				                    "чтобы обсудить все детали заказа и только после этого принять предложение."

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
		f'{format_output_text("категория", category_list, tag="_")}\n'
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

	if info_message_text:
		message = await query.message.reply_text(info_message_text)
		context.chat_data["last_message_id"] = message.message_id

	add_section(
		context,
		state=state,
		messages=messages,
		query_message=query_data,
		reply_markup=menu_markup,
		save_full_messages=True,
		user_role=user_role
	)

	return state


async def manage_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк смены статуса заказа пользователем """

	query = update.callback_query
	await query.answer()

	section = get_section(context)
	query_data = query.data.split('__')
	if len(query_data) < 2:
		return None

	user_id = context.user_data["details"]["id"]
	order_id = int(query_data[0].lstrip("order_"))
	action_code = int(query_data[1].lstrip("action_"))

	order = await load_orders(query.message, context, order_id)
	executor_id = order["executor"]
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
			name = context.user_data["details"]["name"]
			message_text = f'Специалист откликнулся на Ваш заказ:\n _"{order["title"]}"_\n'
			notify_message = {"user_id": order["owner_id"], "from_name": name, "text": message_text}
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
		               f'был завершен заказчиком!\n\n' \
		               f'_Для получения комментариев можете обратиться к заказчику напрямую._'
		notify_message = {"user_id": executor_id, "from_name": order["owner_name"], "text": message_text}

	# если заказ отправлен на доработку
	elif action_code == 6:
		status = 1
		action_message["text"] = "Вы отказались принять работы!\nУведомление о доработке заказа отправлено исполнителю!"
		message_text = f'Информируем о том, что взятый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'не был принят и требует доработки!\n\n' \
		               f'_Для уточнения деталей обратитесь к заказчику напрямую_'
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
		message_text = f'Исполнитель просит принять работу по заказу:\n_"{order["title"]}"_'
		notify_message = {"user_id": order["owner_id"], "from_name": order["executor_name"], "text": message_text}

	# если запрос начать работу отклонен выбранным претендентом
	elif action_code == 3:
		status = 1
		params = {"clear_executor": user_id}
		action_message["text"] = "Вы отклонили предложение на выполнение заказа!"
		name = context.user_data["details"]["name"]
		message_text = f'Информируем о том, что претендент на выполнение заказа:\n_"{order["title"]}"_\n' \
		               f'не принял предложение!'
		decline_notify_message = {"user_id": order["owner_id"], "from_name": name, "text": message_text}

		# создадим сообщение для других соискателей кроме отказавшегося претендента
		message_text = f'Информируем о том, что рассматриваемый Вами заказ:\n _"{order["title"]}"_\n' \
		               f'снова выставлен на биржу!'
		notify_message = {"user_id": [], "from_name": order["owner_name"], "text": message_text}
		for user in order["responded_users"]:
			if user["id"] != user_id:
				notify_message["user_id"].append(user["id"])

	# если запрос подтвержден выбранным претендентом
	elif action_code == 2:
		status = 1
		params = {"remove_user": user_id}  # удалим пользователя из списка соискателей
		action_message["text"] = "Вы взяли заказ и можете приступать к работе!"
		name = context.user_data["details"]["name"]
		message_text = f'Изменился статус заказа\n_"{order["title"]}\n"_' \
		               f'Выбранный исполнитель принял условия договора и начал работу!'
		notify_message = {"user_id": order["owner_id"], "from_name": name, "text": message_text}

		# создадим сообщение с отказом всем соискателям кроме исполнителя
		message_text = f'Информируем о том, что заказ:\n _"{order["title"]}"_\n' \
		               f'был предложен другому исполнителю.\nВозможно в будущем удастся поработать с Вами.\nУдачи!'
		decline_notify_message = {"user_id": [], "from_name": order["owner_name"], "text": message_text}
		for user in order["responded_users"]:
			if user["id"] != user_id:
				decline_notify_message["user_id"].append(user["id"])

		# удалим сообщение с предложением принять условия договора
		await delete_messages_by_key(context, context.chat_data.get("last_message_ids").get("order_offer_text"))

		inline_markup = generate_inline_markup(
			[ORDER_ACTIONS_KEYBOARD[8]],
			callback_data=[f'owner_contact_info_{order["owner"]}']
		)

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

			order_details_message = await edit_or_reply_message(
				context,
				text=update_text_by_keyword(order_details_message.text, "Статус:", f'Статус: *{order_status}*'),
				message=order_details_message.message_id,
				return_message_id=False,
				reply_markup=inline_markup
			)
			# обновим сообщения в текущей секции
			order_details_message = TGMessage.create_message(order_details_message)

			# отправим сообщение пользователям с уведомлением о новом статусе заказа
			if notify_message:
				inline_markup = generate_order_notification_markup(order, notify_message["user_id"])
				await send_message_to(context, **notify_message, reply_markup=inline_markup)

			# отправим сообщение соискателям с уведомлением об отказе
			if decline_notify_message:
				inline_markup = generate_order_notification_markup(order, decline_notify_message["user_id"])
				await send_message_to(context, **decline_notify_message, reply_markup=inline_markup)

		else:
			action_message["text"] = error_text

	# выведем сообщение о действии, изменении заказа или ошибке
	if action_message.get("text"):
		action_message.pop("error", None)
		context.chat_data["last_message_id"] = await edit_or_reply_message(context, **action_message)

	section["messages"] = [title_message, order_details_message] + tg_messages
	update_section(context, messages=section["messages"])


async def select_order_executor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк выбора или отказа дизайнером от претендента на роль исполнителя заказа """

	query = update.callback_query
	await query.answer()

	if context.user_data["details"].get("access", -1) < 0:
		await delete_messages_by_key(context, "warn_message_id")
		message = await restricted_access_message(update.message)
		context.chat_data["warn_message_id"] = message.message_id
		return

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
					return_message_id=False
				)

			else:
				# обновим кнопку текущего сообщения
				user_markup = generate_inline_markup(
					[[ORDER_EXECUTOR_KEYBOARD[0], ORDER_EXECUTOR_KEYBOARD[2]]],
					callback_data=["user_" + str(executor_id), query_data + "__is_selected"]
				)
				_message = await query.message.edit_reply_markup(user_markup)

			contender_messages.append(TGMessage.create_message(_message))

		message_text = f'Вы были выбраны в качестве претендента на выполнение заказа:\n_"{order["title"]}"_\n' \
		               f'Теперь Вы можете согласовать детали заказа и приступить к работе!'

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
					return_message_id=False
				)
				contender_messages.append(TGMessage.create_message(_message))

		# удалим текущее сообщение с исполнителем после отказа
		await query.message.delete()
		message_text = f'Заказчик отказался от Вашей кандидатуры на выполнение заказа:\n _"{order["title"]}"_'

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
		return_message_id=False
	)
	order_details_message = TGMessage.create_message(_message)

	inline_markup = generate_inline_markup(
		[ORDER_RESPOND_KEYBOARD[3]],
		callback_data=[f'order_{order["id"]}__executor'],
	)
	await send_message_to(
		context,
		user_id=executor_id,
		text=message_text,
		from_name=order["owner_name"],
		reply_markup=inline_markup
	)

	update_section(
		context,
		messages=[title_message, order_details_message, contenders_title_message] + contender_messages
	)


async def apply_order_offer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк принятия условий договора исполнителем заказа """

	query = update.callback_query
	await query.answer()

	query_data = query.data
	order_id = int(query_data.lstrip("apply_order_"))
	last_message_ids = context.chat_data.setdefault("last_message_ids", {})

	# выведем файл с условиями оферты
	message = await context.bot.send_document(
		chat_id=query.message.chat_id,
		caption="Договор оказания услуг",
		document=open('terms.txt', 'rb')
	)
	last_message_ids["order_offer"] = message.message_id

	inline_markup = generate_inline_markup(["Принять условия"], callback_data=[f'order_{order_id}__action_2'])
	message = await query.message.reply_text(
		"Необходимо принять условия договора, чтобы сделка была совершена!\n"
		"Если Вы согласны, то нажмите на кнопку *Принять условия*",
		reply_markup=inline_markup
	)
	last_message_ids["order_offer_text"] = message.message_id


async def get_order_contact_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк получения сообщения с контактными данными от владельца заказа """

	query = update.callback_query
	await query.answer()

	last_message_ids = context.chat_data.setdefault("last_message_ids", {})
	if last_message_ids.get("contact_add_info"):
		return

	owner_id = int(query.data.lstrip("owner_contact_info_"))
	user = await load_user(query.message, context, user_id=owner_id, with_details=True)

	if user is None:
		text = "Не удалось получить контактные данные о заказчике!\nОтправляйте сообщение через строку ввода"
	else:
		text = "Заказчик открыл свои данные для работы.\n"
		text += "Выбирайте удобный способ общения или общайтесь прямо здесь, отправляя текстовые сообщения в строке"
		inline_message = await show_user_card_message(context, user=user)
		last_message_ids["contact_info"] = inline_message.message_id

	inline_message = await query.message.reply_text("ℹ️ " + text)
	last_message_ids["contact_add_info"] = inline_message.message_id


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

	if context.user_data["details"].get("access", -1) < 0:
		await delete_messages_by_key(context, "warn_message_id")
		message = await restricted_access_message(query.message)
		context.chat_data["warn_message_id"] = message.message_id
		return

	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	order_categories = local_data.get("order_data", {}).get("categories")
	section = get_section(context)

	if section["state"] != MenuState.ADD_ORDER:
		section = await prepare_current_section(context, keep_messages=True)

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
		update_section(context, messages=section["messages"] + messages, reply_markup=menu_markup)

	return state


def order_has_approved_executor(order: dict) -> bool:
	""" Вернет истина, если претендент отсутствует в списке откликнувшихся на заказ responded_users """
	if not order["executor"]:
		return False

	responded_user = find_obj_in_dict(order["responded_users"], {"id": order["executor"]})
	return not bool(responded_user)


def get_order_status(order: dict) -> Tuple[str, str]:
	"""
	Получение статуса заказа в виде строки
	Returns:
		Tuple (статус, дата выполнения заказа)
	"""
	date_string, expire_date, current_date = get_formatted_date(order["expire_date"])
	is_valid = not expire_date or current_date <= expire_date

	if order["status"] == 0:
		order_status = ORDER_STATUS[0]
	elif order["status"] == 1:
		if not is_valid:
			order_status = ORDER_STATUS[4]
		elif order["executor"]:
			order_status = ORDER_STATUS[int(order_has_approved_executor(order) + 2)]
		else:
			order_status = ORDER_STATUS[1]
	elif order["status"] == 2:
		order_status = ORDER_STATUS[5]
	elif order["status"] == 3:
		order_status = ORDER_STATUS[6]
	else:
		order_status = ORDER_STATUS[7]

	return order_status, date_string


async def show_user_orders(
		message: Message,
		orders: list,
		user_role: Literal["creator", "contender", "executor"],
		user_id: int = None,
		title: str = None,
		reply_markup: ReplyKeyboardMarkup = back_menu
) -> list:
	""" Вывод на экран списка заказов пользователя по его id:
		Args:
			message: объект с сообщением,
			orders: заказы дизайнера,
			user_role: флаг указывающий на текущую роль пользователя,
			user_id: id текущего пользователя,
			title: заголовок для сообщений,
			reply_markup: клавиатура для reply message.
		Returns:
			массив Message сообщений
	 """
	# TODO: проверить актуальная информация или нет
	messages = []

	if title:
		reply_message = await message.reply_text(f'*{title.upper()}*\n', reply_markup=reply_markup)
		messages.append(reply_message)

	if not orders:
		message_text = "❕Список заказов пустой"
		reply_message = await message.reply_text(message_text, reply_markup=reply_markup)
		messages.append(reply_message)

		if user_role == "creator":
			inline_message = await place_new_order_message(message)
			messages.append(inline_message)

		return messages

	elif not user_role:
		return messages

	for index, order in enumerate(orders, 1):
		order_has_executor = order_has_approved_executor(order)
		order_button_text = ORDER_RESPOND_KEYBOARD[3]

		if user_role == "creator":
			order_button_text = ORDER_RESPOND_KEYBOARD[4]
			if order["status"] == 2:
				order_button_text = ORDER_RESPOND_KEYBOARD[5]

			responded_user_counter = len(order["responded_users"])
			if order["status"] < 2 and responded_user_counter and not order_has_executor:
				# вставим счетчик между названием кнопки и ее иконкой справа
				order_button_text = f'{order_button_text[:-2]} ({responded_user_counter}) {order_button_text[-1]}'

		elif order["executor"] == user_id and not order_has_executor:
			order_button_text = ORDER_RESPOND_KEYBOARD[2]

		inline_markup = generate_inline_markup(
			[order_button_text],
			callback_data=[f'order_{order["id"]}__{user_role}']  # добавим роль обязательно
		)

		inline_message_text = format_output_text(f'{index}', order["title"] + "\n", tag="`", default_sep=".")

		order_status, date_string = get_order_status(order)
		# if user_role == "contender":
		#   inline_message_text += f'\nЗаказчик: _{order["owner_name"]}_'

		if not user_role == "creator" and not order_has_executor and order["executor"] == user_id:
			order_status = "необходимо заключить договор ✍️"

		if order_has_executor and order["executor"] != user_id and order.get("executor_name"):
			inline_message_text += f'\nИсполнитель: _{order["executor_name"]}_'

		order_price = f'{order["price"]}₽' if order["price"] else "по договоренности"
		inline_message_text += f'\nСтоимость работ: _{order_price}_'

		if date_string:
			inline_message_text += f'\nСрок реализации: _{date_string}_'

		if order_status:
			inline_message_text += f'\nСтатус: _{order_status}_'

		inline_message = await message.reply_text(inline_message_text, reply_markup=inline_markup)
		messages.append(inline_message)

	if user_role == "creator":
		inline_message = await place_new_order_message(message)
		messages.append(inline_message)

	return messages


async def show_order_related_users(message: Message, context: ContextTypes.DEFAULT_TYPE, order: dict) -> List[Message]:
	""" Вывод данных претендентов на заказ или исполнителя с inline кнопками управления """

	executor_id = order["executor"]
	users = order["responded_users"]

	if not executor_id and not users:
		return []

	order_has_executor = order_has_approved_executor(order)
	selected_postfix = ""
	inline_messages = []

	# если пользователь был выбран дизайнером
	if executor_id:
		if order_has_executor:  # если подтвержденный исполнитель
			executor = await load_user(message, context, user_id=executor_id)
			if executor:
				users = [executor]

		else:
			selected_postfix = "__is_selected"

	# изменим заголовок списка претендентов или исполнителя
	_message = await message.reply_text(f'_{ORDER_RELATED_USERS_TITLE[int(order_has_executor)]}:_')
	inline_messages.append(_message)

	for user in users:
		buttons = [InlineKeyboardButton(ORDER_EXECUTOR_KEYBOARD[0], callback_data=f'user_{user["id"]}')]
		if order["status"] == 1 and not order_has_executor:
			user_is_contender = user["id"] == executor_id
			if not executor_id or user_is_contender:
				buttons.append(InlineKeyboardButton(
					ORDER_EXECUTOR_KEYBOARD[int(user_is_contender) + 1],
					callback_data=f'order_{order["id"]}__executor_{user["id"]}{selected_postfix}'
				))

		rating_text = str(user["total_rating"]) if user["total_rating"] else "отсутствует"
		_message = await message.reply_text(
			f'*{user["name"]}*'
			f'{format_output_text("рейтинг", "⭐️" + rating_text)}',
			reply_markup=InlineKeyboardMarkup([buttons])
		)
		inline_messages.append(_message)

	return inline_messages


def generate_order_notification_markup(order: dict, user_id: any) -> Optional[InlineKeyboardMarkup]:
	if order["status"] > 0 and not isinstance(user_id, list):
		if user_id == order["executor"]:
			user_role = "executor"
		else:
			user_role = "creator" if user_id == order["owner_id"] else "contender"

		return generate_inline_markup(
			[ORDER_RESPOND_KEYBOARD[3]],
			callback_data=[f'order_{order["id"]}__{user_role}']
		)

	return None

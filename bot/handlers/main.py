from typing import Optional, Callable, Union, Literal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ChatAction
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	SUPPLIERS_REGISTER_KEYBOARD, USER_DETAILS_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD, DESIGNER_SERVICES_KEYBOARD,
	OUTSOURCER_SERVICES_KEYBOARD, DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD, DESIGNER_SERVICES_ORDERS_KEYBOARD,
	ORDER_EXECUTOR_KEYBOARD, ORDER_RESPOND_KEYBOARD, ORDER_ACTIONS_KEYBOARD, MODIFY_KEYBOARD, REMOVE_KEYBOARD,
	CONTINUE_KEYBOARD, CANCEL_KEYBOARD, FAVORITE_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SEGMENT_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import (
	select_categories_message, add_new_user_message, select_events_message, choose_sandbox_message,
	place_new_order_message, send_notify_message,
	required_category_warn_message, only_in_list_warn_message
)
from bot.constants.patterns import (
	ADD_FAVOURITE_PATTERN, REMOVE_FAVOURITE_PATTERN, DESIGNER_ORDERS_PATTERN, PLACED_DESIGNER_ORDERS_PATTERN,
	OUTSOURCER_ACTIVE_ORDERS_PATTERN, DONE_ORDERS_PATTERN, USER_FEEDBACK_PATTERN, NEW_DESIGNER_ORDER_PATTERN,
	CONTINUE_PATTERN, CANCEL_PATTERN
)
from bot.constants.static import (
	ORDER_REMOVE_MESSAGE_TEXT, ORDER_RESPONSE_MESSAGE_TEXT,
	ORDER_ERROR_MESSAGE_TEXT, ORDER_FIELD_SET, SUPPLIER_SUBTITLE
)
from bot.entities import TGMessage
from bot.handlers.common import (
	delete_messages_by_key, load_cat_users, load_categories,
	load_user, load_orders, build_inline_username_buttons,
	update_order, edit_or_reply_message, get_order_status, show_user_orders,
	prepare_current_section, add_section, update_section, get_section,
	show_order_related_users, order_has_approved_executor, go_back_section, update_favourites
)
from bot.handlers.details import show_user_card_message
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_markup, match_query, fetch_user_data, send_action, find_obj_in_list, format_output_text,
	update_text_by_keyword, get_key_values, generate_inline_markup, get_formatted_date, extract_fields, validate_date,
	validate_number, data_list_to_string, find_obj_in_dict
)


async def main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция обработки сообщений в главном разделе """

	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]

	chat_data = context.chat_data
	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text
	messages = [update.message]
	menu_markup = back_menu
	callback = main_menu_choice

	# Раздел - РЕЕСТР ПОСТАВЩИКОВ
	if match_query(MenuState.SUPPLIERS_REGISTER, query_message) and priority_group in [Group.DESIGNER, Group.SUPPLIER]:
		state = MenuState.SUPPLIERS_REGISTER
		title = str(state).upper()

		if priority_group == Group.DESIGNER:
			menu_markup = generate_reply_markup(SUPPLIERS_REGISTER_KEYBOARD)

		if not chat_data.get("supplier_categories"):
			# Получим список поставщиков для добавления в реестр
			chat_data["supplier_categories"] = await load_categories(update.message, context, group=2)
			if not chat_data["supplier_categories"]:
				return await go_back_section(update, context, "back")

		reply_message = await update.message.reply_text(text=f'*{title}*', reply_markup=menu_markup)
		inline_message = await select_categories_message(update.message, chat_data["supplier_categories"])
		messages += [reply_message, inline_message]

	# Раздел - БИРЖА УСЛУГ
	elif match_query(MenuState.SERVICES, query_message) and priority_group in [Group.DESIGNER, Group.OUTSOURCER]:
		state = MenuState.SERVICES

		# если пользователь состоит в группе Аутсорсер
		if priority_group == Group.OUTSOURCER:
			keyboard = OUTSOURCER_SERVICES_KEYBOARD
			menu_markup = generate_reply_markup(keyboard, is_persistent=False)

			# получение списка всех активных заказов с сервера для категорий текущего пользователя
			cat_ids = get_key_values(user_details["categories"], "id")
			params = {"categories": cat_ids, "actual": "true", "status": 1}
			orders = await load_orders(update.message, context, params=params)

			messages += await show_user_orders(
				update.message,
				orders=orders,
				user_id=user_details["id"],
				user_role="contender",
				reply_markup=menu_markup
			)

		# если пользователь в группе Дизайнер
		else:
			keyboard = DESIGNER_SERVICES_KEYBOARD
			if Group.has_role(user_details, Group.OUTSOURCER):  # и еще аутсорсер
				keyboard = DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD

			menu_markup = generate_reply_markup(keyboard)
			title = str(state).upper()
			subtitle = "Категории исполнителей:"

			if not chat_data.get("outsourcer_categories"):
				# Получим категории для аутсорсеров
				chat_data["outsourcer_categories"] = await load_categories(update.message, context, group=1)
				if not chat_data["outsourcer_categories"]:
					return section["state"]

			reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
			inline_message = await select_categories_message(
				update.message,
				title=subtitle,
				category_list=chat_data["outsourcer_categories"]
			)
			messages += [reply_message, inline_message]

	# Раздел - СОБЫТИЯ
	elif match_query(MenuState.DESIGNER_EVENTS, query_message) and priority_group in [Group.DESIGNER, Group.OUTSOURCER]:
		state = MenuState.DESIGNER_EVENTS
		title = str(state).upper()
		reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		inline_message = await select_events_message(update.message)
		messages += [reply_message, inline_message]

	# Раздел - БАРАХОЛКА (купить/продать/поболтать)
	elif match_query(MenuState.DESIGNER_SANDBOX, query_message) and priority_group in [
		Group.DESIGNER, Group.OUTSOURCER
	]:
		# TODO: [task 4]:
		#  создать логику добавления в группы телеграм после регистрации и повесить на кнопки ссылки для перехода
		state = MenuState.DESIGNER_SANDBOX
		title = str(state).upper()
		reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		inline_message = await choose_sandbox_message(update.message)
		messages += [reply_message, inline_message]

	else:
		return await go_back_section(update, context)

	add_section(
		context,
		state=state,
		query_message=query_message,
		messages=messages,
		reply_markup=menu_markup,
		callback=callback,
	)

	return state


async def services_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция обработки сообщений в разделе Бирже услуг """

	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]

	# Подраздел - НОВЫЙ ЗАКАЗ, если это Дизайнер
	if match_query(NEW_DESIGNER_ORDER_PATTERN, update.message.text) and priority_group == Group.DESIGNER:
		await update.message.delete()
		return await new_order_callback(update, context)

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text
	state = MenuState.ORDERS
	menu_markup = back_menu
	callback = services_choice
	messages = [update.message]
	user_role: Literal["creator", "contender", "executor"]

	# Подраздел - МОИ ЗАКАЗЫ, если это Дизайнер
	if match_query(DESIGNER_ORDERS_PATTERN, query_message) and priority_group == Group.DESIGNER:
		title = "Мои размещенные заказы"
		user_role = "creator"
		menu_markup = generate_reply_markup(DESIGNER_SERVICES_ORDERS_KEYBOARD)
		params = {"owner_id": user_details["id"], "status": [0, 1, 2]}

	# Подраздел - АКТИВНЫЕ ЗАКАЗЫ НА БИРЖЕ
	elif match_query(PLACED_DESIGNER_ORDERS_PATTERN, query_message) and priority_group == Group.DESIGNER:
		title = "Размещенные заказы"
		user_role = "contender"
		params = {"actual": "true", "status": 1}
		# если это Дизайнер и Аутсорсер, то получим все активные заказы из категорий пользователя, исключая собственные
		if Group.has_role(user_details, Group.OUTSOURCER):
			cat_ids = get_key_values(user_details["categories"], "id")
			params.update({"categories": cat_ids, "exclude_owner_id": user_details["id"]})

	# Подраздел - ВЗЯТЫЕ В РАБОТУ ЗАКАЗЫ, если это Аутсорсер
	elif match_query(OUTSOURCER_ACTIVE_ORDERS_PATTERN, query_message) and Group.has_role(user_details,
	                                                                                     Group.OUTSOURCER):
		title = "Взятые заказы"
		user_role = "executor"
		# все активные заказы для исполнителя с его id
		params = {"executor_id": user_details["id"], "status": [1, 2]}

	# Подраздел - ЗАВЕРШЕННЫЕ ЗАКАЗЫ, если это Аутсорсер
	elif match_query(DONE_ORDERS_PATTERN, query_message) and Group.has_role(user_details, Group.OUTSOURCER):
		title = "Выполненные заказы"
		user_role = "executor"
		# все завершенные заказы для исполнителя с его id
		params = {"executor_id": user_details["id"], "status": 3}

	else:
		return await go_back_section(update, context)

	orders = await load_orders(update.message, context, params=params)

	messages += await show_user_orders(
		update.message,
		orders=orders,
		title=title,
		user_role=user_role,
		user_id=user_details["id"],
		reply_markup=menu_markup
	)

	add_section(
		context,
		state=state,
		query_message=query_message,
		messages=messages,
		reply_markup=menu_markup,
		callback=callback,
		user_role=user_role
	)

	return state


async def designer_orders_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция отображения архивных заказов дизайнера на Бирже услуг """

	await update.message.delete()
	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]

	section = await prepare_current_section(context, leave_messages=True)
	query_message = section.get("query_message") or update.message.text
	state = section["state"]

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
		section["messages"] += messages
		update_section(context, messages=section["messages"])

	else:
		return await go_back_section(update, context)

	return state


async def suppliers_search_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция поиска поставщиков"""

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text

	state = MenuState.SUPPLIERS_SEARCH
	title = str(state).upper()

	# TODO: [task 2]: Разработать механизм поиска поставщика в таблице User по критериям
	reply_message = await update.message.reply_text(f'__{title}__\n', reply_markup=back_menu)

	inline_message = await update.message.reply_text(
		f'Выберите критерии поиска:\n'
		f'[кнопки]\n'
		f'[кнопки]'
	)

	add_section(
		context,
		state=state,
		query_message=query_message,
		messages=[update.message, reply_message, inline_message],
		callback=suppliers_search_choice
	)

	return state


async def user_details_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция обработки сообщений в карточке пользователя """

	await update.message.delete()
	chat_data = context.chat_data
	selected_user = chat_data["selected_user"]

	section = get_section(context)
	query_message = update.message.text
	state = section["state"]
	keyboard = USER_DETAILS_KEYBOARD.copy()
	menu_markup = generate_reply_markup(keyboard)

	# Подраздел - ОСТАВИТЬ ОТЗЫВ
	if match_query(USER_FEEDBACK_PATTERN, query_message):
		title = f'Отзыв о поставщике'
		message = await update.message.reply_text(
			title,
			reply_markup=menu_markup
		)

	# Подраздел - ДОБАВИТЬ В ИЗБРАННОЕ
	elif match_query(ADD_FAVOURITE_PATTERN, query_message):
		_, error_text = await update_favourites(update.message, context, selected_user["id"], method="POST")
		if not error_text:
			keyboard[0][0] = FAVORITE_KEYBOARD[1]
			menu_markup = generate_reply_markup(keyboard)
			section.update({"reply_markup": menu_markup})
			chat_data["selected_user"]["in_favourite"] = True
			name = selected_user["name"]

			message = await update.message.reply_text(
				f'{name.upper()} добавлен(а) в избранное!',
				reply_markup=menu_markup
			)

		else:
			message = await update.message.reply_text(f'❗️{error_text}', reply_markup=menu_markup)
			chat_data["warn_message_id"] = message.message_id
			return state

	# Подраздел - УДАЛИТЬ ИЗ ИЗБРАННОГО
	elif match_query(REMOVE_FAVOURITE_PATTERN, query_message):
		_, error_text = await update_favourites(update.message, context, selected_user["id"], method="DELETE")
		if not error_text:
			keyboard[0][0] = FAVORITE_KEYBOARD[0]
			menu_markup = generate_reply_markup(keyboard, is_persistent=True)
			section.update({"reply_markup": menu_markup})
			chat_data["selected_user"]["in_favourite"] = False
			name = selected_user["name"]

			message = await update.message.reply_text(
				f'{name.upper()} удален(а) из избранного!',
				reply_markup=menu_markup
			)

		else:
			message = await update.message.reply_text(f'❗️{error_text}', reply_markup=menu_markup)
			chat_data["warn_message_id"] = message.message_id
			return state

	else:
		return await go_back_section(update, context)

	section["messages"] += TGMessage.create_list([update.message, message], only_ids=True)

	return state


async def add_order_fields_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция добавления/обновления данных заказа на бирже """

	section = get_section(context)
	query_message = update.message.text

	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	field_name = local_data.get("order_field_name")
	order_id = local_data.get("order_id")
	await delete_messages_by_key(context, "warn_message_id")

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
		selected_categories = local_data.get("selected_categories")
		if selected_categories:
			local_data["order_data"] = {"categories": list(selected_categories.keys())}
			local_data.pop("selected_categories")
			return await new_order_callback(update, context)
		else:
			await required_category_warn_message(update.message, context)
			return section["state"]

	elif not field_name:
		await update.message.delete()
		await only_in_list_warn_message(update.message, context)
		return section["state"]

	# сохранение и валидация введенных данных
	order = await modify_order_fields_choice(update, context)
	if not order:  # если некорректно введены данные или ошибка чтения/сохранения заказа
		return section["state"]

	if field_name == "title":
		field_name = "description"
		title = "Добавьте подробное описание"

	elif field_name == "description":
		field_name = "price"
		title = f'Укажите желаемую цену за работы'

	elif field_name == "price":
		field_name = "expire_date"
		title = "Определите конечную дату выполнения работ или введите \\* если срок не органичен"

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
				f'Категория: _{data_list_to_string(order.get("categories"), field_names="name", separator=", ")}_',
				reply_markup=get_section(context).get("reply_markup")
			)
			chat_data["last_message_id"] = message.message_id
		return state

	return section["state"]


async def modify_order_fields_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
	""" Функция обновления полей заказа дизайнера """
	section = get_section(context)
	is_new_order = section["state"] == MenuState.ADD_ORDER

	chat_data = context.chat_data
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	local_data = chat_data.setdefault("local_data", {})
	field_name = local_data["order_field_name"]
	field_value = update.message.text.strip()
	message_text = field_value

	if field_name == "price":
		price = validate_number(field_value)
		if not price:
			await update.message.delete()
			message = await edit_or_reply_message(
				update.message,
				message_id=last_message_ids.get(field_name),
				text=f'⚠️ Цена указана некорректно!\nПовторите ввод',
				reply_markup=section["reply_markup"],
			)
			chat_data["warn_message_id"] = message.message_id
			return

		field_value = price
		message_text = f'{field_value}₽'

	if field_name == "expire_date":
		if field_value != "*":
			date = validate_date(field_value)
			if not date:
				await update.message.delete()
				message = await edit_or_reply_message(
					update.message,
					message_id=last_message_ids.get(field_name),
					text=f'⚠️ Дата указана некорректно!\nПовторите ввод.\n_Допустимый формат: дд.мм.гггг или *_',
					reply_markup=section["reply_markup"],
				)
				chat_data["warn_message_id"] = message.message_id
				return

			message_text, field_value = date

		else:
			field_value = None
			message_text = "бессрочно"

		local_data["order_data"] = {"status": 1}

	data_changed = True
	local_data["order_data"].update({field_name: field_value})
	order_id = local_data.get("order_id", None)
	if order_id:
		order = await load_orders(update.message, context, order_id=order_id)
		if not order:
			return
		data_changed = not bool(order[field_name] == field_value)

	order = await update_order(update.message, context, order_id, data=local_data["order_data"])
	if not order:
		return

	await update.message.delete()
	local_data["order_data"] = {}
	if not order_id:
		local_data["order_id"] = order["id"]

	if data_changed:
		message_text = f'☑️ *{message_text}*'

	elif field_name == "expire_date":
		message_text = f'☑️ *{message_text}*'

	else:
		message_text = f'❕*{message_text}*\n_данные идентичны!_'

	if not is_new_order:  # если это изменение заказа, то дополнительно к сообщению добавляем заголовок с названием поля
		message_text = f'{ORDER_FIELD_SET[field_name]}:\n' + message_text

	message = await edit_or_reply_message(
		update.message,
		message_id=last_message_ids.get(field_name),
		text=message_text,
		reply_markup=section["reply_markup"]
	)

	# сохраним id измененного сообщения для удаления при возврате
	last_message_ids.update({field_name: message.message_id})

	return order


@send_action(ChatAction.TYPING)
async def select_suppliers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Отображение списка пользователей из группы SUPPLIER в разделе: Реестр поставщиков -> Категория """

	return await select_users_in_category(update, context, callback=select_suppliers_in_cat_callback)


@send_action(ChatAction.TYPING)
async def select_outsourcers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Отображение списка пользователей из группы DESIGNER,OUTSOURCER в разделе: Биржа услуг -> Категория """

	return await select_users_in_category(update, context, callback=select_outsourcers_in_cat_callback)


async def select_users_in_category(
		update: Union[Update, CallbackQuery],
		context: ContextTypes.DEFAULT_TYPE,
		callback: Callable
) -> str:
	""" Вспомогательная функция загрузки и отображения списка пользователей в категории по cat_id.
		is_supplier_register - раздел, в котором отображать контент: Реестр или Биржа
	"""
	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	priority_group = context.user_data["priority_group"]
	chat_data = context.chat_data
	# установим флаг для понимания откуда вызывалась эта функция
	is_supplier_register = callback.__name__ == "select_suppliers_in_cat_callback"

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	state = section["state"]
	menu_markup = back_menu

	cat_id = query_data.lstrip("category_")

	users = await load_cat_users(query.message, context, cat_id)
	if not users:
		return state

	inline_markup = build_inline_username_buttons(users)
	categories = chat_data.get("supplier_categories" if is_supplier_register else "outsourcer_categories")
	selected_cat = find_obj_in_dict(categories, params={"id": int(cat_id)})
	if not selected_cat:
		return state

	title = f'➡️ Категория *{selected_cat["name"].upper()}*'
	subtitle = SUPPLIER_SUBTITLE[int(is_supplier_register)]

	reply_message = await query.message.reply_text(title, reply_markup=menu_markup)
	inline_message = await query.message.reply_text(subtitle, reply_markup=inline_markup)
	messages = [reply_message, inline_message]

	if priority_group == Group.DESIGNER:
		if is_supplier_register:
			keyboard = SUPPLIERS_REGISTER_KEYBOARD
			menu_markup = generate_reply_markup(keyboard)

			# TODO: [task 3]: реализовать добавление рекомендованного пользователя
			extra_message = await add_new_user_message(query.message, category=selected_cat)
			messages.append(extra_message)

		else:
			# выведем в конце сообщение с размещением нового заказа
			extra_message = await place_new_order_message(query.message, category=selected_cat)

		messages.append(extra_message)

	add_section(
		context,
		state=state,
		messages=messages,
		reply_markup=menu_markup,
		query_message=query_data,
		callback=callback,
		selected_cat=cat_id
	)

	return state


@send_action(ChatAction.TYPING)
async def show_user_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Колбэк вывода на экран подробной информации о пользователе по его id """

	query = update.callback_query
	await query.answer()

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	supplier_id = int(query_data.lstrip("user_"))
	priority_group = context.user_data["priority_group"]
	user_id = context.user_data["details"]["id"]

	chat_data = context.chat_data

	state = MenuState.USER_DETAILS
	reply_markup = back_menu
	# callback = show_user_details_callback

	user = await load_user(query.message, context, user_id=supplier_id, with_details=True)
	if user is None:
		return section["state"]

	chat_data["selected_user"] = user
	# если пользователь и выбранный поставщик не одно лицо, то добавим кнопки с избранным и отзывами
	if supplier_id != user_id and priority_group == Group.DESIGNER:
		in_favourite = user["in_favourite"]
		keyboard = USER_DETAILS_KEYBOARD.copy()
		keyboard[0][0] = FAVORITE_KEYBOARD[int(in_favourite)]
		reply_markup = generate_reply_markup(keyboard)

	title = f'{"✅ " if user["user_id"] else ""}'
	title += f'Профиль {"поставщика" if Group.has_role(user, Group.SUPPLIER) else "исполнителя"}\n'
	title += f'*{user["username"].upper()}*\n'
	reply_message = await query.message.reply_text(title, reply_markup=reply_markup)
	inline_message = await show_user_card_message(query.message, context, user=user)

	add_section(
		context,
		state=state,
		messages=[reply_message, inline_message],
		reply_markup=reply_markup,
		query_message=query_data
	)

	return state


async def recommend_new_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Добавление нового пользователя для текущей группы
	query = update.callback_query
	await query.answer()

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	menu_markup = back_menu
	state = section["state"]
	callback = recommend_new_user_callback

	# TODO: [task 3]:
	#  Необходимо продолжить реализацию добавления рекомендованного пользователя и вынести логику в отдельный файл
	#  Использовать логику в registration.py

	message = await query.message.reply_text(
		text='Как называется компания, которую Вы рекомендуете?',
		reply_markup=menu_markup
	)

	add_section(
		context,
		state=state,
		messages=[message],
		reply_markup=menu_markup,
		query_message=query_data,
		callback=callback
	)

	return state


async def change_supplier_segment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор сегмента поставщика
	query = update.callback_query
	await query.answer()

	query_data = query.data.split("__")
	if len(query_data) < 2:
		return
	user_id = int(query_data[0].lstrip("user_"))
	segment = int(query_data[1].lstrip("segment_"))
	section = get_section(context)

	# сохраним изменения пользователя с обновленным сегментом
	res = await fetch_user_data(user_id, data={"segment": segment}, method="PATCH")
	if not res["data"]:
		return section["state"]

	context.chat_data["selected_user"]["segment"] = segment

	user_details_message = section["messages"].pop(1)  # получим последнее сохраненное сообщение
	# обновим сегмент в карточке пользователя
	modified_text = update_text_by_keyword(
		text=user_details_message.text,
		keyword="Сегмент",
		replacement=f'`Сегмент`: 🎯 _{SEGMENT_KEYBOARD[segment]}_'
	)
	message = await edit_or_reply_message(
		query.message,
		message_id=user_details_message.message_id,
		text=modified_text
	)
	section["messages"].insert(1, TGMessage.create_message(message))

	temp_messages = context.chat_data.get("temp_messages", {})
	await edit_or_reply_message(
		query.message,
		message_id=temp_messages.get("user_segment"),
		text=f'☑️ Рейтинг был изменен!\nСпасибо за Ваше участие'
	)


async def select_events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор события
	query = update.callback_query
	await query.answer()

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	event_type_id = int(query_data.lstrip("event_type_"))
	state = MenuState.DESIGNER_EVENTS
	menu_markup = generate_reply_markup([BACK_KEYBOARD + TO_TOP_KEYBOARD], share_location=True)
	callback = select_events_callback

	if event_type_id == 0:
		message = await query.message.reply_text(
			f'Вот что сейчас проходит в нашем городе:\n',
			reply_markup=menu_markup,
		)

	elif event_type_id == 1:
		message = await query.message.reply_text(
			f'Вот что сейчас проходит в России:\n',
			reply_markup=menu_markup,
		)

	elif event_type_id == 2:
		message = await query.message.reply_text(
			f'Вот что сейчас проходит в мире:\n',
			reply_markup=menu_markup,
		)

	else:
		return await go_back_section(update, context)

	add_section(
		context,
		state=state,
		messages=[message],
		reply_markup=menu_markup,
		query_message=query_data,
		callback=callback
	)

	return state


async def select_sandbox_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор барахолки/песочницы
	query = update.callback_query
	await query.answer()

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	sandbox_type_id = int(query_data.lstrip("sandbox_type_"))
	state = MenuState.DESIGNER_SANDBOX
	menu_markup = back_menu

	if sandbox_type_id:
		message = await query.message.reply_text(
			f'Перейдем в группу "{DESIGNER_SANDBOX_KEYBOARD[sandbox_type_id]}"\n',
			reply_markup=menu_markup,
		)

	else:
		return await go_back_section(update, context)

	add_section(
		context,
		state=state,
		messages=[message],
		reply_markup=menu_markup,
		query_message=query_data
	)

	return state


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
		return await go_back_section(update, context, "back")

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
	inline_markup = None

	message = await query.message.reply_text(f'*{order["title"]}*', reply_markup=menu_markup)
	messages = [message]

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

			elif order["status"] == 2:  # заказ в стадии сдачи, то предложить кнопки: принять и на доработку
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
				order = await update_order(query.message, context, order_id, data={"status": 0, "responded_users": []})
				order_status, _ = get_order_status(order)

	# если это пока никто и заказ активный, то предложим откликнуться или снять отклик
	elif order["status"] == 1:
		user_id = context.user_data["details"]["id"]
		responded_user, _ = find_obj_in_list(order["responded_users"], {"id": user_id})
		action_code = int(bool(responded_user))  # флаг: пользователь уже есть в списке откликнувшихся или нет
		inline_markup = generate_inline_markup(
			[ORDER_RESPOND_KEYBOARD[action_code]],
			callback_data=f'order_{order_id}__action_{20 + action_code}'
		)

	message = await query.message.reply_text(
		f'`{order["description"]}`'
		f'{format_output_text("_Категория_", category_list, value_tag="_")}\n'
		f'{format_output_text("Автор заказа", order["owner_name"] if not user_is_owner else "", value_tag="*")}'
		f'{format_output_text(ORDER_FIELD_SET["price"], order_price, value_tag="*")}'
		f'{format_output_text(ORDER_FIELD_SET["expire_date"], date_string if date_string else "не установлен", value_tag="*")}\n'
		f'{format_output_text("Статус", order_status, value_tag="*")}',
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
	action_message = {"message_id": context.chat_data.get("last_message_id", None)}

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
			list(ORDER_FIELD_SET.values()),
			callback_data=list(ORDER_FIELD_SET.keys()),
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

		else:  # если претендент на заказ отзывает свой отклик до выбора его исполнителем
			params = {"remove_user": user_id}

		action_index = abs(action_code - 21)
		inline_markup = generate_inline_markup(
			ORDER_RESPOND_KEYBOARD[action_index],
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
		order = await update_order(query.message, context, order_id, params=params, data=data)
		if order:
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
			action_message["text"] = action_message.get("error", "Не удалось изменить данные о заказе на сервере!")

	# выведем сообщение о действии, изменении заказа или ошибке
	if action_message.get("text"):
		action_message.pop("error", None)
		message = await edit_or_reply_message(query.message, **action_message)
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
	error_message_text = None

	if order["status"] == 0:
		error_message_text = ORDER_ERROR_MESSAGE_TEXT[0]

	elif order["status"] > 2:
		error_message_text = ORDER_ERROR_MESSAGE_TEXT[1]

	if error_message_text:
		message = await edit_or_reply_message(query.message, error_message_text, message_id=last_message_id)
		context.chat_data["last_message_id"] = message.message_id
		return

	title_message = tg_messages.pop(0)  # извлечем сообщение с заголовком раздела
	order_details_message = tg_messages.pop(0)  # извлечем сообщение с описанием заказа
	contenders_title_message = tg_messages.pop(0)  # извлечем сообщение с заголовком списка претендентов

	inline_markup = None

	# Выберем текущего претендента в качестве предполагаемого исполнителя
	if not user_is_selected:
		order = await update_order(query.message, context, order_id, data={"executor": executor_id})
		if not order:
			return

		# удалим кнопку выбора у всех претендентов кроме выбранного
		for message in tg_messages:
			if message.message_id != query.message.message_id:
				details_keyboard = message.reply_markup.inline_keyboard[0][0]
				button = InlineKeyboardButton(details_keyboard.text, callback_data=details_keyboard.callback_data)
				_message = await edit_or_reply_message(
					query.message,
					message_id=message.message_id,
					text=message.text,
					reply_markup=InlineKeyboardMarkup([[button]])
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
		order = await update_order(query.message, context, order_id, params={"clear_executor": executor_id})
		if not order:
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
					query.message,
					message_id=message.message_id,
					text=message.text,
					reply_markup=InlineKeyboardMarkup([buttons])
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

	_message = await edit_or_reply_message(
		query.message,
		message_id=order_details_message.message_id,
		text=update_text_by_keyword(order_details_message.text, "Статус:", f'Статус: *{order_status}*'),
		reply_markup=inline_markup
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

	query_data = query.data.lstrip('modify_order_').split("__")
	if len(query_data) < 2:
		return

	order_id = int(query_data[0])
	button_type = query_data[-1]
	chat_data = context.chat_data
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	local_data = chat_data.setdefault("local_data", {})

	message_text = ORDER_FIELD_SET.get(button_type, "")
	if message_text:
		message_text = f'*{message_text}*\n_Введите новое значение_'
		if button_type == "expire_date":
			message_text += " в формате: дд.мм.гггг или укажите символ \\* для бессрочного варианта."
	else:
		message_text = "_Некорректное поле!_"

	message = await query.message.reply_text(message_text)
	last_message_ids[button_type] = message.message_id
	local_data["order_data"][button_type] = ""

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
		order = await update_order(query.message, context, order_id, method="DELETE")
		message_text = ORDER_REMOVE_MESSAGE_TEXT[int(bool(order))]
		message = await edit_or_reply_message(query.message, message_id=last_message_id, text=message_text)
		context.chat_data["last_message_id"] = message.message_id

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

	else:
		# local_data["order_data"].update({"categories": []})
		menu_markup = generate_reply_markup([CONTINUE_KEYBOARD], one_time_keyboard=False)
		title = str(state).upper()
		subtitle = 'В какой категории будем размещать заявку?'

		reply_message = await query.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		messages = [reply_message.message_id]

		if not chat_data.get("outsourcer_categories"):
			chat_data["outsourcer_categories"] = await load_categories(query.message, context, group=1)
			if not chat_data["outsourcer_categories"]:
				return section["state"]

		inline_message = await select_categories_message(
			query.message,
			title=subtitle,
			category_list=chat_data["outsourcer_categories"]
		)
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

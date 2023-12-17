from typing import Optional, Literal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error, InputFile
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	SUPPLIERS_REGISTER_KEYBOARD, USER_DETAILS_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD, DESIGNER_SERVICES_KEYBOARD,
	OUTSOURCER_SERVICES_KEYBOARD, DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD, DESIGNER_SERVICES_ORDERS_KEYBOARD,
	FAVORITES_ACTIONS_KEYBOARD, SEGMENT_KEYBOARD,
	SEARCH_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import (
	recommend_new_user_message, select_events_message, place_new_order_message, select_search_options_message,
	restricted_access_message
)
from bot.constants.patterns import (
	ADD_FAVOURITE_PATTERN, REMOVE_FAVOURITE_PATTERN, DESIGNER_ORDERS_PATTERN, PLACED_DESIGNER_ORDERS_PATTERN,
	OUTSOURCER_ACTIVE_ORDERS_PATTERN, DONE_ORDERS_PATTERN, USER_FEEDBACK_PATTERN, NEW_DESIGNER_ORDER_PATTERN
)
from bot.constants.static import CAT_GROUP_DATA, MONTH_NAME_LIST
from bot.entities import TGMessage
from bot.handlers.common import (
	load_cat_users, load_user, load_orders, generate_users_list, generate_categories_list, update_favourites,
	edit_or_reply_message, prepare_current_section, add_section, get_section, go_back_section, delete_messages_by_key,
	load_events
)
from bot.handlers.details import show_user_card_message
from bot.handlers.order import new_order_callback, show_user_orders
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_markup, match_query, fetch_user_data, send_action, update_text_by_keyword, get_key_values,
	find_obj_in_dict, generate_inline_markup, convert_date, format_output_text
)


async def main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция обработки сообщений в главном разделе """

	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text
	messages = [update.message]
	menu_markup = generate_reply_markup(BACK_KEYBOARD)
	callback = main_menu_choice

	# Раздел - РЕЕСТР ПОСТАВЩИКОВ
	if match_query(MenuState.SUPPLIERS_REGISTER, query_message) and priority_group in [Group.DESIGNER, Group.SUPPLIER]:
		state = MenuState.SUPPLIERS_REGISTER
		if priority_group == Group.DESIGNER:
			menu_markup = generate_reply_markup(SUPPLIERS_REGISTER_KEYBOARD)

		title = str(state).upper()
		reply_message = await update.message.reply_text(text=f'*{title}*', reply_markup=menu_markup)
		messages.append(reply_message)

		# генерируем инлайн кнопки для списка категорий
		inline_markup = await generate_categories_list(update.message, context, groups=2)
		if not inline_markup:
			return section["state"]
		inline_message = await update.message.reply_text('🗃 Список категорий:', reply_markup=inline_markup)
		messages.append(inline_message)

	# Раздел - БИРЖА УСЛУГ
	elif match_query(MenuState.SERVICES, query_message) and priority_group in [Group.DESIGNER, Group.OUTSOURCER]:
		state = MenuState.SERVICES

		# если пользователь состоит только в группе Аутсорсер
		if priority_group == Group.OUTSOURCER:
			keyboard = OUTSOURCER_SERVICES_KEYBOARD
			menu_markup = generate_reply_markup(keyboard, is_persistent=False)
			title = str(state).upper()
			reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
			messages.append(reply_message)

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
			reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
			messages.append(reply_message)

			inline_markup = await generate_categories_list(update.message, context, groups=1)
			if not inline_markup:
				return section["state"]

			inline_message = await update.message.reply_text("🗃 Категории исполнителей:", reply_markup=inline_markup)
			messages.append(inline_message)

	# Раздел - ЛИЧНЫЙ ПОМОЩНИК
	elif match_query(MenuState.PERSONAL_ASSISTANT, query_message) and priority_group in [Group.DESIGNER]:
		state = MenuState.PERSONAL_ASSISTANT
		title = str(state).upper()
		reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		inline_message = await update.message.reply_text(
			f'В этом разделе Вы сможете обращаться за профессиональной помощью к искусственному интеллекту.\n'
			f'_В стадии разработки..._'
		)
		messages += [reply_message, inline_message]

	# Раздел - СОБЫТИЯ
	elif match_query(MenuState.DESIGNER_EVENTS, query_message) and priority_group in [Group.DESIGNER, Group.OUTSOURCER]:
		state = MenuState.DESIGNER_EVENTS
		title = str(state).upper()
		reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		inline_message = await select_events_message(update.message)
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
		cat_group=2 if state == MenuState.SUPPLIERS_REGISTER else 1
	)

	return state


async def services_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция обработки сообщений в разделе Биржа услуг """

	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]

	# Подраздел - НОВЫЙ ЗАКАЗ, если это Дизайнер
	if match_query(NEW_DESIGNER_ORDER_PATTERN, update.message.text) and priority_group == Group.DESIGNER:
		await update.message.delete()
		return await new_order_callback(update, context)

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text
	state = MenuState.SERVICES
	menu_markup = back_menu
	callback = services_choice
	messages = [update.message]
	user_role: Literal["creator", "contender", "executor"]

	# Подраздел - МОИ ЗАКАЗЫ, если это Дизайнер
	if match_query(DESIGNER_ORDERS_PATTERN, query_message) and priority_group == Group.DESIGNER:
		state = MenuState.DESIGNER_ORDERS
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
			# params.update({"categories": cat_ids, "exclude_owner_id": user_details["id"]})
			params.update({"categories": cat_ids})

	# Подраздел - ВЗЯТЫЕ В РАБОТУ ЗАКАЗЫ, если это Аутсорсер
	elif match_query(OUTSOURCER_ACTIVE_ORDERS_PATTERN, query_message) and Group.has_role(user_details,
	                                                                                     Group.OUTSOURCER):
		title = "Взятые заказы"
		user_role = "executor"
		# все активные заказы для исполнителя с его id
		params = {"executor_id": user_details["id"], "status": [1, 2]}

	# Подраздел - АРХИВНЫЕ ЗАКАЗЫ, если это Аутсорсер
	elif match_query(DONE_ORDERS_PATTERN, query_message) and Group.has_role(user_details, Group.OUTSOURCER):
		title = "Выполненные заказы"
		user_role = "executor"
		# все завершенные заказы для исполнителя с его id
		params = {"executor_id": user_details["id"], "status": 3}

	elif match_query(DONE_ORDERS_PATTERN, query_message) and priority_group == Group.DESIGNER:
		state = MenuState.DESIGNER_ORDERS
		params = {"owner_id": user_details["id"], "status": [3, 4]}
		title = "Закрытые заказы"
		user_role = "creator"

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
		# TODO: сделать отзыв о поставщике
		title = f'Отзыв о поставщике в процессе реализации...'
		message = await update.message.reply_text(title, reply_markup=menu_markup)

	# Подраздел - ДОБАВИТЬ В ИЗБРАННОЕ
	elif match_query(ADD_FAVOURITE_PATTERN, query_message):
		if context.user_data["details"].get("access", -1) < 0:
			await delete_messages_by_key(context, "warn_message_id")
			message = await restricted_access_message(update.message, reply_markup=menu_markup)
			chat_data["warn_message_id"] = message.message_id
			return state

		_, error_text = await update_favourites(update.message, context, selected_user["id"], method="POST")
		if not error_text:
			keyboard[0][0] = FAVORITES_ACTIONS_KEYBOARD[1]
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
		if context.user_data["details"].get("access", -1) < 0:
			await delete_messages_by_key(context, "warn_message_id")
			message = await restricted_access_message(update.message, reply_markup=menu_markup)
			chat_data["warn_message_id"] = message.message_id
			return state

		_, error_text = await update_favourites(update.message, context, selected_user["id"], method="DELETE")
		if not error_text:
			keyboard[0][0] = FAVORITES_ACTIONS_KEYBOARD[0]
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


async def users_search_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция поиска поставщиков и исполнителей по критериям """

	section = await prepare_current_section(context, keep_messages=True)
	query_message = section.get("query_message") or update.message.text
	state = MenuState.USERS_SEARCH
	callback = users_search_choice
	title = f'*{str(state).upper()}*'

	if context.user_data["details"].get("access", -1) < 0:
		menu_markup = back_menu
		reply_message = await update.message.reply_text(title, reply_markup=menu_markup)
		inline_message = await restricted_access_message(update.message)

	else:
		keyboard = [SEARCH_KEYBOARD, BACK_KEYBOARD + TO_TOP_KEYBOARD]
		menu_markup = generate_reply_markup(keyboard, one_time_keyboard=False)
		reply_message = await update.message.reply_text(title, reply_markup=menu_markup)
		inline_message = await select_search_options_message(update.message, cat_group=section.get("cat_group", 2))

	add_section(
		context,
		state=state,
		query_message=query_message,
		messages=[update.message, reply_message, inline_message],
		reply_markup=menu_markup,
		callback=callback,
		cat_group=section.get("cat_group", 2)  # передадим неосновное свойство с группой категории пользователей
	)

	return state


@send_action(ChatAction.TYPING)
async def select_users_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция загрузки и отображения списка пользователей в категории по cat_id """

	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or query.data
	query_data = query_message.split("__")
	cat_id = query_data[-1].lstrip("category_")

	if len(query_data) > 1:
		group = int(query_data[0].lstrip("group_"))
		if group >= len(CAT_GROUP_DATA):
			return section["state"]
		group_data = CAT_GROUP_DATA[group]

	else:
		group = None
		group_data = None

	priority_group = context.user_data["priority_group"]
	chat_data = context.chat_data
	state = section["state"]
	menu_markup = back_menu
	callback = select_users_list_callback

	# загрузим всех пользователей в выбранной категории
	users = await load_cat_users(query.message, context, cat_id)
	if not users:
		return state

	# генерируем инлайн кнопки списка поставщиков
	inline_markup = generate_users_list(users)
	categories = chat_data.get(f'{group_data["name"]}_cats' if group_data else "categories")
	selected_cat = find_obj_in_dict(categories, params={"id": int(cat_id)})
	if not selected_cat:
		return state

	title = f'🗃 Категория *{selected_cat["name"].upper()}*'
	reply_message = await query.message.reply_text(title, reply_markup=menu_markup)

	subtitle = group_data["title"]
	inline_message = await query.message.reply_text(subtitle, reply_markup=inline_markup)
	messages = [reply_message, inline_message]

	if priority_group == Group.DESIGNER:
		message = await recommend_new_user_message(query.message, category=selected_cat)
		messages.append(message)

		if group == 2:
			keyboard = SUPPLIERS_REGISTER_KEYBOARD
			menu_markup = generate_reply_markup(keyboard)

		else:
			# выведем в конце сообщение с размещением нового заказа
			message = await place_new_order_message(query.message, category=selected_cat)
			messages.append(message)

	add_section(
		context,
		state=state,
		messages=messages,
		reply_markup=menu_markup,
		query_message=query_message,
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
		keyboard[0][0] = FAVORITES_ACTIONS_KEYBOARD[int(in_favourite)]
		reply_markup = generate_reply_markup(keyboard)

	title = f'{"💠 " if user["user_id"] else ""}'
	title += f'Профиль {"поставщика" if Group.has_role(user, Group.SUPPLIER) else "исполнителя"}\n'
	title += f'*{user["name"].upper()}*\n'
	reply_message = await query.message.reply_text(title, reply_markup=reply_markup)
	inline_message = await show_user_card_message(context, user=user)

	add_section(
		context,
		state=state,
		messages=[reply_message, inline_message],
		reply_markup=reply_markup,
		query_message=query_data
	)

	return state


async def change_supplier_segment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор сегмента поставщика
	query = update.callback_query
	await query.answer()

	if context.user_data["details"].get("access", -1) < 0:
		await delete_messages_by_key(context, "warn_message_id")
		message = await restricted_access_message(query.message)
		context.chat_data["warn_message_id"] = message.message_id
		return

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
		context,
		text=modified_text,
		message=user_details_message.message_id,
		return_message_id=False
	)
	section["messages"].insert(1, TGMessage.create_message(message))

	temp_messages = context.chat_data.get("temp_messages", {})
	await edit_or_reply_message(
		context,
		text=f'✅ Рейтинг был изменен!\nСпасибо за Ваше участие',
		message=temp_messages.get("user_segment"),
	)


async def select_events_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк выбора группы мероприятий в своей области: город/страна/мир """

	query = update.callback_query
	await query.answer()

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	events_type = int(query_data.lstrip("events_type_"))
	priority_group = min(context.user_data["details"]["groups"])

	events = await load_events(query.message, context, events_type=events_type, group=priority_group)
	state = MenuState.DESIGNER_EVENTS
	menu_markup = back_menu
	inline_message = None

	if events_type == 0:
		title = f'Мероприятия в вашем городе\n_В стадии разработки_',

	elif events_type == 1:
		title = f'Мероприятия в России'

	elif events_type == 2:
		title = f'События в мире в ближайшие 12 месяцев'

	else:
		return await go_back_section(update, context, "Выберите место где пройдут мероприятия в ближайший год!")

	if not events:
		title = "Ближайшие мероприятия не найдены!"
		inline_markup = None

	else:
		# получаем список уникальных месяцев из ключей объекта с событиями
		callback_data = list(events.keys())
		months_list = [
			f'{MONTH_NAME_LIST[int(month) - 1][:3].upper()} {year}' for month, year in
			(data.split(".") for data in callback_data)
		]
		# создадим инлайн кнопки для выбора месяца по 4 в ряд
		inline_markup = generate_inline_markup(
			months_list,
			callback_data=callback_data,
			callback_data_prefix=f'events_type_{events_type}__',
			cols=4
		)

	message = await query.message.reply_text(title, reply_markup=menu_markup)
	if inline_markup:
		inline_message = await query.message.reply_text('В каком месяце ищите мероприятия?', reply_markup=inline_markup)

	add_section(
		context,
		state=state,
		messages=[update.message, message, inline_message],
		reply_markup=menu_markup,
		query_message=query_data
	)

	return state


async def select_events_month_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк выбора месяца с мероприятиями в своей области """

	query = update.callback_query
	await query.answer()

	section = await prepare_current_section(context)
	query_data = section.get("query_message") or query.data
	events_type, events_date = query_data.split("__")
	events_type = int(events_type.lstrip("events_type_"))
	month, year = events_date.split(".")
	events = await load_events(query.message, context, events_type=events_type, events_date=events_date)
	state = MenuState.DESIGNER_EVENTS

	if events:
		text = f'Список мероприятий на {MONTH_NAME_LIST[int(month) - 1]} {year}:'
		message = await query.message.reply_text(text, reply_markup=back_menu)
		messages = [message.message_id]

		for event in events:
			event_date = event.get("start_date")
			if event.get("end_date"):
				event_date += " - " + event["end_date"]

			caption = f'*{event.get("title")}*\n' \
			          f'`{event.get("description")}`\n' \
			          f'{format_output_text("📍", event.get("location"), default_sep=" ", tag="_")}\n' \
			          f'{format_output_text("📅", event_date, default_sep=" ", tag="_")}'

			event_markup = InlineKeyboardMarkup(
				[[InlineKeyboardButton("Перейти на сайт", url=event.get("source_link"))]]
			)
			try:
				message = await context.bot.send_photo(
					chat_id=query.message.chat_id,
					photo=event.get("cover"),
					caption=caption,
					reply_markup=event_markup
				)
			except error.BadRequest:
				message = await query.message.reply_text(
					caption,
					reply_markup=event_markup
				)
			messages.append(message)

	else:
		message = await query.message.reply_text("Список мероприятий отсутствует", reply_markup=back_menu)
		messages = [message.message_id]

	add_section(
		context,
		state=state,
		messages=messages,
		save_full_messages=False
	)

	return state

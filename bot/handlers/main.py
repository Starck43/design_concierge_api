from typing import Optional, Literal

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	SUPPLIERS_REGISTER_KEYBOARD, USER_DETAILS_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD, DESIGNER_SERVICES_KEYBOARD,
	OUTSOURCER_SERVICES_KEYBOARD, DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD, DESIGNER_SERVICES_ORDERS_KEYBOARD,
	FAVORITES_ACTIONS_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SEGMENT_KEYBOARD,
	SEARCH_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import (
	add_new_user_message, select_events_message, choose_sandbox_message,
	place_new_order_message, select_search_options_message
)
from bot.constants.patterns import (
	ADD_FAVOURITE_PATTERN, REMOVE_FAVOURITE_PATTERN, DESIGNER_ORDERS_PATTERN, PLACED_DESIGNER_ORDERS_PATTERN,
	OUTSOURCER_ACTIVE_ORDERS_PATTERN, DONE_ORDERS_PATTERN, USER_FEEDBACK_PATTERN, NEW_DESIGNER_ORDER_PATTERN
)
from bot.constants.static import (
	CAT_GROUP_DATA
)
from bot.entities import TGMessage
from bot.handlers.common import (
	load_cat_users, load_user, load_orders, generate_users_list,
	edit_or_reply_message, show_user_orders,
	prepare_current_section, add_section, update_section, get_section,
	go_back_section, update_favourites, generate_categories_list
)
from bot.handlers.details import show_user_card_message
from bot.handlers.order import new_order_callback
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_markup, match_query, fetch_user_data, send_action, update_text_by_keyword, get_key_values,
	find_obj_in_dict
)


async def main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция обработки сообщений в главном разделе """

	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text
	messages = [update.message]
	menu_markup = back_menu
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
			reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
			messages.append(reply_message)

			inline_markup = await generate_categories_list(update.message, context, groups=1)
			if not inline_markup:
				return section["state"]

			inline_message = await update.message.reply_text("🗃 Категории исполнителей:", reply_markup=inline_markup)
			messages.append(inline_message)

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
		cat_group=2 if state == MenuState.SUPPLIERS_REGISTER else 1
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

	# Подраздел - НОВЫЙ ЗАКАЗ, если это Дизайнер
	if match_query(NEW_DESIGNER_ORDER_PATTERN, update.message.text) and priority_group == Group.DESIGNER:
		return await new_order_callback(update, context)

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
		update_section(context, messages=section["messages"] + messages)

	else:
		return await go_back_section(update, context)

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
	""" Функция подбора поставщиков и исполнителей по критериям """

	section = await prepare_current_section(context, leave_messages=True)
	query_message = section.get("query_message") or update.message.text
	state = MenuState.USERS_SEARCH
	callback = users_search_choice
	menu_markup = generate_reply_markup([SEARCH_KEYBOARD, BACK_KEYBOARD + TO_TOP_KEYBOARD], one_time_keyboard=False)
	title = f'*{str(state).upper()}*'
	reply_message = await update.message.reply_text(title, reply_markup=menu_markup)
	inline_message = await select_search_options_message(update.message, cat_group=section.get("cat_group", 2))

	add_section(
		context,
		state=state,
		query_message=query_message,
		messages=[update.message, reply_message, inline_message],
		reply_markup=menu_markup,
		callback=callback,
		cat_group=section.get("cat_group", 2)
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
		# TODO: [task 3]: реализовать добавление рекомендованного пользователя
		message = await add_new_user_message(query.message, category=selected_cat)
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
		context,
		text=modified_text,
		message=user_details_message.message_id,
		return_only_id=False
	)
	section["messages"].insert(1, TGMessage.create_message(message))

	temp_messages = context.chat_data.get("temp_messages", {})
	await edit_or_reply_message(
		context,
		text=f'✅ Рейтинг был изменен!\nСпасибо за Ваше участие',
		message=temp_messages.get("user_segment"),
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



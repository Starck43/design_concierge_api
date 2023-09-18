from typing import Optional

from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.constants.common import ORDER_RELATED_USERS_TITLE, ORDER_STATUS
from bot.constants.keyboards import (
	SUPPLIERS_REGISTER_KEYBOARD, USER_DETAILS_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD,
	DESIGNER_SERVICES_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SEGMENT_KEYBOARD, DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD,
	FAVORITE_KEYBOARD, DESIGNER_SERVICES_ORDER_KEYBOARD, ORDER_EXECUTOR_KEYBOARD, ORDER_RESPOND_KEYBOARD,
	OUTSOURCER_SERVICES_KEYBOARD, ORDER_ACTIONS_KEYBOARD, DESIGNER_SERVICES_ORDERS_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import (
	select_events_message, send_unknown_question_message, choose_sandbox_message,
	show_after_set_segment_message, success_save_rating_message, offer_to_save_rating_message,
	show_detail_rating_message, yourself_rate_warning_message, show_categories_message,
	add_new_user_message, empty_data_message, place_new_order_message,
	show_inline_message, show_order_related_users_message
)
from bot.constants.patterns import (
	USER_RATE_PATTERN, ADD_FAVOURITE_PATTERN, REMOVE_FAVOURITE_PATTERN, DESIGNER_ORDERS_PATTERN,
	PLACED_DESIGNER_ORDERS_PATTERN, OUTSOURCER_ACTIVE_ORDERS_PATTERN, DONE_ORDERS_PATTERN
)
from bot.handlers.common import (
	go_back, get_menu_item, delete_messages_by_key, update_ratings, check_required_user_group_rating, load_cat_users,
	load_categories, load_user, get_user_rating_data, load_orders, update_user_data, add_menu_item,
	build_inline_username_buttons, check_user_in_groups, rates_to_string, update_order,
	edit_last_message, search_message_by_data, update_menu_item, get_order_status, show_user_orders
)
from bot.handlers.details import show_user_details
from bot.handlers.questionnaire import show_user_rating_messages
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_keyboard, match_message_text, fetch_user_data, send_action, find_obj_in_list, format_output_text,
	update_text_by_keyword, get_key_values, generate_inline_keyboard, get_formatted_date, extract_fields
)


async def main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Обработчик Главного меню
	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]
	user_groups = Group.get_enum(user_details["groups"])
	is_outsourcer = Group.OUTSOURCER in user_groups
	chat_data = context.chat_data

	state, message, inline_message, menu_markup, _ = get_menu_item(context)
	message_text = update.message.text

	# Раздел - РЕЕСТР ПОСТАВЩИКОВ
	if match_message_text(str(MenuState.SUPPLIERS_REGISTER), message_text) and priority_group in [
		Group.DESIGNER, Group.SUPPLIER
	]:
		state = MenuState.SUPPLIERS_REGISTER
		menu_markup = back_menu
		if priority_group == Group.DESIGNER:
			menu_markup = generate_reply_keyboard(SUPPLIERS_REGISTER_KEYBOARD, is_persistent=True)

		if "supplier_categories" not in chat_data or not chat_data["supplier_categories"]:
			# Получим список поставщиков для добавления в реестр
			chat_data["supplier_categories"] = await load_categories(update.message, context, group=2)
			if not chat_data["supplier_categories"]:
				return await go_back(update, context, -1)

		title = str(state).upper()

		message = await update.message.reply_text(
			text=f'*{title}*',
			reply_markup=menu_markup,
		)
		# выведем список категорий поставщиков
		inline_message = await show_categories_message(update.message, chat_data["supplier_categories"])

	# Раздел - БИРЖА УСЛУГ
	elif match_message_text(str(MenuState.SERVICES), message_text) and priority_group in [
		Group.DESIGNER, Group.OUTSOURCER
	]:
		state = MenuState.SERVICES

		# если пользователь состоит в группе Аутсорсер
		if priority_group == Group.OUTSOURCER:
			keyboard = OUTSOURCER_SERVICES_KEYBOARD
			menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)

			# получение списка всех активных заказов с сервера для категорий текущего пользователя
			cat_ids = get_key_values(user_details["categories"], "id")
			params = {"categories": cat_ids, "active": "true", "status": 1}
			orders = await load_orders(update.message, context, params=params)
			user_id = user_details["id"]

			message, inline_message = await show_user_orders(
				update.message,
				orders=orders,
				user_id=user_id,
				user_role="receiver",
				reply_markup=menu_markup
			)

		# если пользователь в группе Дизайнер
		else:
			keyboard = DESIGNER_SERVICES_KEYBOARD
			if is_outsourcer:
				keyboard = DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD

			menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)
			title = str(state).upper()
			subtitle = "Выберите категорию:"
			message = await update.message.reply_text(
				f'__{title}__',
				reply_markup=menu_markup,
			)

			if not chat_data.get("outsourcer_categories"):
				# Получим категории для аутсорсеров
				chat_data["outsourcer_categories"] = await load_categories(update.message, context, group=1)
				if not chat_data["outsourcer_categories"]:
					return await go_back(update, context, -1)

			# выведем список категорий аутсорсеров
			inline_message = await show_categories_message(update.message, chat_data["outsourcer_categories"], subtitle)

	# Раздел - СОБЫТИЯ
	elif match_message_text(str(MenuState.DESIGNER_EVENTS), message_text) and priority_group in [
		Group.DESIGNER, Group.OUTSOURCER
	]:
		state = MenuState.DESIGNER_EVENTS
		title = str(state).upper()
		menu_markup = back_menu
		message = await update.message.reply_text(
			f'__{title}__',
			reply_markup=menu_markup
		)
		inline_message = await select_events_message(update.message)

	# Раздел - БАРАХОЛКА (купить/продать/поболтать)
	elif match_message_text(str(MenuState.DESIGNER_SANDBOX), message_text) and priority_group in [
		Group.DESIGNER, Group.OUTSOURCER
	]:
		state = MenuState.DESIGNER_SANDBOX
		title = str(state).upper()
		message = await update.message.reply_text(
			f'__{title}__\n',
			reply_markup=menu_markup
		)
		# TODO: [task 4]:
		#  создать логику добавления в группы телеграм после регистрации и повесить на кнопки ссылки для перехода
		inline_message = await choose_sandbox_message(update.message)

	else:
		await send_unknown_question_message(update.message)

	add_menu_item(context, state, message, inline_message, menu_markup)

	return state or MenuState.START


async def orders_group_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция отображения заказов дизайнера на Бирже услуг """

	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]
	user_groups = Group.get_enum(user_details["groups"])
	is_outsourcer = Group.OUTSOURCER in user_groups
	message_text = update.message.text.lower()

	_, message, inline_message, _, _ = get_menu_item(context)
	await delete_messages_by_key(context, inline_message)
	state = MenuState.ORDERS
	menu_markup = back_menu

	# Подраздел - МОИ ЗАКАЗЫ
	if match_message_text(DESIGNER_ORDERS_PATTERN, message_text) and priority_group == Group.DESIGNER:
		# если это Дизайнер
		menu_markup = generate_reply_keyboard(DESIGNER_SERVICES_ORDERS_KEYBOARD, is_persistent=True)
		params = {"owner_id": user_details["id"], "status": [0, 1]}
		orders = await load_orders(update.message, context, params=params)
		message, inline_message = await show_user_orders(
			update.message,
			orders,
			user_role="creator",
			reply_markup=menu_markup
		)

		if not orders:
			inline_message = await place_new_order_message(message)

	# Подраздел - ВСЕ ЗАКАЗЫ
	elif match_message_text(PLACED_DESIGNER_ORDERS_PATTERN, message_text) and priority_group == Group.DESIGNER:
		if is_outsourcer:
			# если это Дизайнер и Аутсорсер, то получим все активные заказы из категорий пользователя
			cat_ids = get_key_values(user_details["categories"], "id")
			params = {"categories": cat_ids, "active": "true", "status": 1}
			orders = await load_orders(update.message, context, params=params)
			user_id = user_details["id"]
			message, inline_message = await show_user_orders(
				update.message,
				orders=orders,
				user_role="receiver",
				user_id=user_id
			)

		else:
			# если это только Дизайнер, то получим все активные и непросроченные заказы из всех категорий
			params = {"active": "true", "status": 1}
			orders = await load_orders(update.message, context, params=params)
			user_id = user_details["id"]
			message, inline_message = await show_user_orders(
				update.message,
				orders=orders,
				user_role="viewer",
				user_id=user_id
			)

	# Подраздел - ВЗЯТЫЕ В РАБОТУ ЗАКАЗЫ
	elif match_message_text(OUTSOURCER_ACTIVE_ORDERS_PATTERN, message_text) and is_outsourcer:
		# если это Аутсорсер, то получим все активные заказы для исполнителя с его id
		params = {"executor_id": user_details["id"], "status": 1}
		orders = await load_orders(update.message, context, params=params)
		message, inline_message = await show_user_orders(
			update.message,
			orders,
			title="Заказы в работе",
			user_role="executor"
		)

	# Подраздел - ЗАВЕРШЕННЫЕ ЗАКАЗЫ
	elif match_message_text(DONE_ORDERS_PATTERN, message_text) and is_outsourcer:
		# если это Аутсорсер, то получим все завершенные  заказы для исполнителя с его id
		params = {"executor_id": user_details["id"], "status": 2}
		orders = await load_orders(update.message, context, params=params)
		message, inline_message = await show_user_orders(
			update.message,
			orders,
			title="Выполненные заказы",
			user_role="executor"
		)

	else:
		await send_unknown_question_message(update.message)

	add_menu_item(context, state, message, inline_message, menu_markup)

	return state


async def designer_orders_group_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция отображения архивных заказов дизайнера на Бирже услуг """

	chat_data = context.chat_data
	user_details = context.user_data["details"]
	priority_group = context.user_data["priority_group"]
	message_text = update.message.text
	chat_data.setdefault("last_message_ids", [])

	state, _, _, menu_markup, _ = get_menu_item(context)

	# Подраздел - АРХИВНЫЕ ЗАКАЗЫ
	if match_message_text(DONE_ORDERS_PATTERN, message_text) and priority_group == Group.DESIGNER:
		params = {"owner_id": user_details["id"], "status": 2}
		orders = await load_orders(update.message, context, params=params)

		if orders:
			message, inline_message = await show_user_orders(
				update.message,
				orders,
				title=message_text,
				user_role="creator",
			)

			last_message_ids = chat_data["last_message_ids"]
			last_message_ids.append(message)
			last_message_ids += inline_message

		else:
			message = await update.message.reply_text(f'❕Список пустой.', reply_markup=back_menu)
			context.chat_data["last_message_id"] = message.message_id

	else:
		await send_unknown_question_message(update.message)
		return state

	return state


async def suppliers_search_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Функция поиска поставщиков
	chat_data = context.chat_data

	_, message, inline_message, _, _ = get_menu_item(context)
	await delete_messages_by_key(context, message)
	await delete_messages_by_key(context, inline_message)

	state = MenuState.SUPPLIERS_SEARCH
	menu_markup = back_menu
	title = str(state).upper()

	# TODO: [task 2]: Разработать механизм поиска поставщика в таблице User по критериям
	message = await update.message.reply_text(
		f'__{title}__\n',
		reply_markup=menu_markup,
	)

	inline_message = await update.message.reply_text(
		f'Выберите критерии поиска:\n'
		f'[кнопки]\n'
		f'[кнопки]'
	)

	add_menu_item(context, state, message, inline_message, menu_markup)

	return state


async def user_details_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_id = context.user_data["details"]["user_id"]
	chat_data = context.chat_data
	selected_user = chat_data["selected_user"]
	_, _, _, menu_markup, _ = get_menu_item(context)

	message_text = update.message.text
	state = MenuState.USER_DETAILS
	message = None

	# Подраздел - ОБНОВИТЬ РЕЙТИНГ
	if match_message_text(USER_RATE_PATTERN, message_text):
		message = await update.message.reply_text(
			f'*{selected_user["name"] or selected_user["username"]}*',
			reply_markup=menu_markup
		)

		# вывод рейтинга
		if context.bot_data.get("rating_questions"):
			rating_title = "Оцените все критерии поставщика:"
			rates = selected_user.get("related_designer_rating", {})
			chat_data["user_ratings"] = [{"receiver_id": rates["receiver_id"]}]
			rates_list = []

			for key, val in rates.items():
				if val and key != "receiver_id":
					rates_list.append(val)
					chat_data["user_ratings"][0].update({key: val})

			related_designer_rating = f'⭐{round(sum(rates_list) / len(rates_list), 1)}' if rates_list else ""
			if related_designer_rating:
				rating_title = format_output_text(
					rating_title + "\n" + "_Ваш текущий средний рейтинг_",
					related_designer_rating,
					value_tag="_"
				)

			await show_user_rating_messages(update.message, context, title=rating_title)

		chat_data["saved_submit_rating_message"] = await offer_to_save_rating_message(update.message)
		chat_data["last_message_ids"] = [chat_data["saved_submit_rating_message"].message_id]

	# Подраздел - ИЗБРАННОЕ
	elif match_message_text(ADD_FAVOURITE_PATTERN, message_text):
		res = await fetch_user_data(user_id, f'/favourites/{selected_user["id"]}', method="POST")
		if res["status_code"] in [200, 201]:
			keyboard = USER_DETAILS_KEYBOARD
			keyboard[0][1] = FAVORITE_KEYBOARD[1]
			menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)
			chat_data["menu"][-1]["markup"] = menu_markup
			chat_data["selected_user"]["in_favourite"] = True
			name = res["data"]["supplier_name"]
			message = await update.message.reply_text(
				f'{name.upper()} добавлен(а) в избранное!',
				reply_markup=menu_markup
			)

	elif match_message_text(REMOVE_FAVOURITE_PATTERN, message_text):
		res = await fetch_user_data(user_id, f'/favourites/{selected_user["id"]}', method="DELETE")
		if res["status_code"] == 204:
			keyboard = USER_DETAILS_KEYBOARD.copy()
			keyboard[0][1] = FAVORITE_KEYBOARD[0]
			menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)
			chat_data["menu"][-1]["markup"] = menu_markup
			chat_data["selected_user"]["in_favourite"] = False
			name = selected_user["name"] or selected_user["username"]
			message = await update.message.reply_text(
				f'{name.upper()} удален(а) из избранного!',
				reply_markup=menu_markup
			)

	else:
		await send_unknown_question_message(update.message)

	saved_state, _ = find_obj_in_list(chat_data["menu"], {"state": state})
	if not saved_state:
		add_menu_item(context, state, message, None, menu_markup)

	return state


@send_action(ChatAction.TYPING)
async def select_users_in_category(
		update: Update,
		context: ContextTypes.DEFAULT_TYPE,
		is_supplier_register: bool
) -> str:
	""" Вспомогательная функция загрузки и отображения списка пользователей в категории по cat_id
		is_supplier_register - раздел, в котором отображать контент: Реестр или Биржа  
	"""
	query = update.callback_query

	await query.answer()
	cat_id = query.data.lstrip("category_")
	user_data = context.user_data
	priority_group = user_data["priority_group"]
	chat_data = context.chat_data

	state, message, inline_message, _, _ = get_menu_item(context)
	menu_markup = back_menu

	users = await load_cat_users(query.message, context, cat_id)
	inline_markup = build_inline_username_buttons(users)
	if inline_markup is None:
		return await go_back(update, context, -1)

	selected_cat, _ = find_obj_in_list(
		chat_data["supplier_categories" if is_supplier_register else "outsourcer_categories"],
		{"id": int(cat_id)}
	)

	chat_data["selected_cat"] = selected_cat
	category_name = selected_cat["name"].upper()
	title = f'➡️ Категория *{category_name}*'
	subtitle = "Поставщики:" if is_supplier_register else "Поставщики услуг:"

	await query.message.delete()
	message = await query.message.reply_text(
		text=title,
		reply_markup=menu_markup,
	)

	inline_message = await query.message.reply_text(
		text=subtitle,
		reply_markup=inline_markup
	)

	if priority_group == Group.DESIGNER:
		if is_supplier_register:
			keyboard = SUPPLIERS_REGISTER_KEYBOARD

		elif check_user_in_groups(user_data["groups"], "DO"):
			keyboard = DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD

		else:
			keyboard = DESIGNER_SERVICES_KEYBOARD

		menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)
		message = await place_new_order_message(query.message, category_name)
		chat_data["last_message_id"] = message.message_id

	add_menu_item(context, state, message, inline_message, menu_markup)

	return state


async def select_suppliers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Отображение списка пользователей из группы SUPPLIER в разделе: Реестр поставщиков -> Категория """
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data

	state = await select_users_in_category(update, context, is_supplier_register=True)

	# TODO: [task 3]: реализовать добавление рекомендованного пользователя
	message = await add_new_user_message(query.message, category=chat_data["selected_cat"])
	chat_data["last_message_id"] = message.message_id
	return state


async def select_outsourcers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Отображение списка пользователей из группы DESIGNER,OUTSOURCER в разделе: Биржа услуг -> Категория """
	state = await select_users_in_category(update, context, is_supplier_register=False)
	return state


async def recommend_new_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Добавление нового пользователя для текущей группы
	query = update.callback_query

	await query.answer()
	state, message, inline_message, _, _ = get_menu_item(context)
	menu_markup = back_menu

	await delete_messages_by_key(context, message)
	await delete_messages_by_key(context, inline_message)
	await query.message.delete()

	# TODO: [task 3]:
	#  Необходимо продолжить реализацию добавления рекомендованного пользователя и вынести логику в отдельный файл
	#  Использовать логику в registration.py

	message = await query.message.reply_text(
		text='Как называется компания, которую Вы рекомендуете?',
		reply_markup=menu_markup
	)

	add_menu_item(context, state, message)

	return state


@send_action(ChatAction.TYPING)
async def show_user_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк вывода на экран подробной информации о пользователе по его id """
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data
	chat_data.setdefault("suppliers", {})
	supplier_id = int(query.data.lstrip("user_"))
	supplier = context.chat_data.get("supplier", {}).get(supplier_id, None)
	designer_id = context.user_data["details"]["id"]
	priority_group = context.user_data["priority_group"]

	state = MenuState.USER_DETAILS
	menu_markup = back_menu
	message = None

	# удалим последнее сообщение с предложением добавить компанию в разделе списка поставщиков
	await delete_messages_by_key(context, "last_massage_id")

	if not supplier:
		data, message = await load_user(query.message, context, user_id=supplier_id, designer_id=designer_id)
		if data is None:
			return await go_back(update, context, -1)
		else:
			# TODO: Добавить механизм очистки редко используемых поставщиков
			data["name"] = data.get("name") or data.get("username")
			chat_data["suppliers"].update({supplier_id: data})

	chat_data["selected_user"] = chat_data["suppliers"][supplier_id]  # обязательно сохранять в selected_user

	if priority_group == Group.DESIGNER and supplier_id != designer_id:
		keyboard = USER_DETAILS_KEYBOARD

		in_favourite = chat_data["selected_user"].get("in_favourite")
		if in_favourite:
			keyboard[0][1] = FAVORITE_KEYBOARD[1]

		menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)

	add_menu_item(context, state, message, None, menu_markup)

	await query.message.delete()  # удалим список поставщиков
	await delete_messages_by_key(context, "last_message_id")
	await show_user_details(query, context)

	return state


@send_action(ChatAction.TYPING)
async def save_supplier_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Сохранение рейтинга поставщика
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data
	designer_id = context.user_data["details"]["id"]
	selected_user_id = context.chat_data["selected_user"]["id"]
	saved_rating_message: Message = chat_data.get("saved_rating_message", None)
	saved_submit_rating_message = chat_data.get("saved_submit_rating_message", saved_rating_message)

	await delete_messages_by_key(context, "last_message_id")

	is_required = await check_required_user_group_rating(query.message, context)
	if not is_required or selected_user_id == designer_id:

		if is_required is None or selected_user_id == designer_id:
			await query.message.delete()
			if saved_rating_message:
				await saved_rating_message.reply_text(saved_rating_message.text)

			if is_required is None:
				message = await empty_data_message(query.message)
				chat_data["error"] = "Данные поставщика отсутствуют или не найдены вопросы для анкетирования"
			else:
				message = await yourself_rate_warning_message(saved_submit_rating_message)
			chat_data["last_message_id"] = message.message_id

		else:
			res = await update_ratings(query.message, context)
			if res:
				rated_user = res[0]
				# выведем сообщение вместо кнопки сохранения рейтинга
				await success_save_rating_message(saved_submit_rating_message, user_data=rated_user)

				# получим обновленные данные с сервера
				user_data = await update_user_data(query.message, context, user_id=rated_user["id"])
				if user_data:
					questions, rates = get_user_rating_data(context, user=user_data)
					rating_text = rates_to_string(rates, questions, rate_value=8)

					# выведем сообщение с обновленным рейтингом
					saved_rating_message = await show_detail_rating_message(query.message, rating_text)
					chat_data["last_message_id"] = saved_rating_message.message_id

				else:
					# если обновленные данные не удалось получить с сервера, то удалим кнопку и выведем сохраненный рейтинг
					await query.message.delete()
					if saved_rating_message:
						await saved_rating_message.reply_text(saved_rating_message.text)

		chat_data.pop("user_ratings", None)
		chat_data.pop("saved_submit_rating_message", None)
		await delete_messages_by_key(context, "last_message_ids")


async def select_supplier_segment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор сегмента поставщика
	query = update.callback_query

	await query.answer()
	segment = int(query.data.lstrip("segment_"))
	user_id = context.chat_data["selected_user"]["id"]
	# сохраним изменения пользователя с обновленным сегментом
	res = await fetch_user_data(user_id, data={"segment": segment}, method="PATCH")
	if res["data"]:
		context.chat_data["selected_user"]["segment"] = segment
		context.chat_data["suppliers"][user_id].update({"segment": segment})

		saved_message: Message = context.chat_data.get("saved_details_message")
		if saved_message:
			edited_segment_text = update_text_by_keyword(
				text=saved_message.text_markdown,
				keyword="Сегмент",
				replacement=f'`Сегмент`: 🎯 _{SEGMENT_KEYBOARD[segment][0]}_'
			)
			await saved_message.edit_text(edited_segment_text)

		await show_after_set_segment_message(query.message, segment)


async def select_events_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор события
	query = update.callback_query

	await query.answer()
	event_type_id = int(query.data.lstrip("event_type_"))
	chat_data = context.chat_data

	state = MenuState.DESIGNER_EVENTS
	menu_markup = generate_reply_keyboard([BACK_KEYBOARD, TO_TOP_KEYBOARD], share_location=True, is_persistent=True)

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
		message = await send_unknown_question_message(query.message)

	add_menu_item(context, state, message, None, menu_markup)

	return state


async def select_sandbox_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор барахолки/песочницы
	query = update.callback_query

	await query.answer()
	sandbox_type_id = int(query.data.lstrip("sandbox_type_"))
	chat_data = context.chat_data

	state = MenuState.DESIGNER_SANDBOX
	menu_markup = back_menu

	if sandbox_type_id:
		message = await query.message.reply_text(
			f'Перейдем в группу "{DESIGNER_SANDBOX_KEYBOARD[sandbox_type_id]}"\n',
			reply_markup=menu_markup,
		)

	else:
		message = await send_unknown_question_message(query.message)

	add_menu_item(context, state, message, None, menu_markup)

	return state


async def place_designer_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк размещения заказа на бирже """
	# TODO: [task 1]: Реализовать ввод данных о заказе: Заголовок, Детальное описание, Дата выполнения и категория
	#  категорию не предлагать для выбора, если пользователь уже находится внутри категории и там начал Новый заказ

	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data
	state, _, _, _, _ = get_menu_item(context)

	message = await query.message.reply_text(
		f'Как назовем задачу?',
		reply_markup=back_menu,
	)

	add_menu_item(context, state, message)

	return state


async def respond_designer_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк добавления откликнувшегося аутсорсера на заказ дизайнера на бирже услуг """
	# TODO: [task 1]: Реализовать api для добавления пользователя в модель Order.responding_users
	#  менять текст кнопки, если отменяется действие и приходит успешный ответ по api

	query = update.callback_query

	await query.answer()
	message_id = query.message.message_id
	message_text = query.message.text_markdown
	order_id = int(query.data.lstrip("respond_order_"))
	chat_data = context.chat_data

	# Обновляем выбранное сообщение
	button_text = ORDER_RESPOND_KEYBOARD[1]
	button = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, callback_data=query.data)]])
	await context.bot.edit_message_text(
		text=f'{message_text}',
		chat_id=chat_data.get("chat_id"),
		message_id=message_id,
		reply_markup=button
	)


async def show_order_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк вывода детальной информации по заказу """
	# TODO: [task 1]: Реализовать у reply клавиатуры кнопки управления заказом (см. тех задание для Дизайнеров)
	#  менять ORDER_STATUS в зависимости от условий

	query = update.callback_query

	await query.answer()
	order_id = int(query.data.lstrip("order_"))
	chat_data = context.chat_data
	state, message, inline_message, _, _ = get_menu_item(context)

	await delete_messages_by_key(context, chat_data.get("last_message_ids"))
	await delete_messages_by_key(context, inline_message)
	await delete_messages_by_key(context, message)

	order = await load_orders(update.message, context, order_id=order_id)
	if not order:
		return await go_back(update, context, -1)

	order_status = order["status"]
	order_price = f'{order["price"]}₽' if order["price"] else "по договоренности"
	user_is_owner = order["owner"] == context.user_data["details"]["id"]
	# user_is_executor = order["executor"] == context.user_data["details"]["id"]
	date_string, expire_date, current_date = get_formatted_date(order["expire_date"])
	inline_messages = []
	action_buttons = []

	if user_is_owner:
		reply_keyboard = DESIGNER_SERVICES_ORDER_KEYBOARD.copy()

		# если нет исполнителя
		if not order['executor']:
			# заказ не завершен и срок исполнения не истек или дата бессрочная
			if order["status"] < 2 and (not expire_date or current_date <= expire_date):
				action_buttons.append(
					InlineKeyboardButton(
						ORDER_ACTIONS_KEYBOARD[order["status"]],
						callback_data=f'order_{order["id"]}__status_{"0" if order["status"] == 1 else "1"}'
					)
				)
		# если выбран исполнитель
		else:
			if order["status"] == 2:
				reply_keyboard[0].pop(0)  # удалим кнопку "Изменить" у клавиатуры если заказ завершен

			else:
				reply_keyboard.pop(0)  # удалим кнопки "Изменить" и "Удалить" у клавиатуры

				if order["status"] == 1:
					action_buttons.append(
						InlineKeyboardButton(ORDER_ACTIONS_KEYBOARD[2], callback_data=f'order_{order["id"]}__status_2')
					)

		menu_markup = generate_reply_keyboard(reply_keyboard, is_persistent=True)

	else:
		menu_markup = back_menu

	message = await query.message.reply_text(
		f'*{order["title"]}*',
		reply_markup=menu_markup
	)

	inline_markup = InlineKeyboardMarkup([action_buttons])
	await show_inline_message(
		query.message,
		f'`{order["description"]}`\n'
		f'{" / ".join(extract_fields(order["categories"], "name")).upper()}\n\n'
		f'{format_output_text("Стоимость заказа", order_price, value_tag="*")}'
		f'{format_output_text("Срок реализации", date_string if date_string else "бессрочно", value_tag="*")}\n'
		f'Статус: *{ORDER_STATUS[order_status]}*',
		inline_markup=inline_markup,
		inline_messages=inline_messages
	)

	# отобразим исполнителя или всех претендентов, которые откликнулись на заказ дизайнера
	if user_is_owner and order["status"] > 0:
		await show_order_related_users_message(query.message, order, inline_messages)

	add_menu_item(context, state, message, inline_messages, menu_markup)

	return state


async def change_order_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк смены статуса заказа для создателя """
	# TODO: [task 1]: При смене статуса менять инлайн кнопку с query_data и выполнять api запрос на изменение статуса
	#  надо обновлять данные inline messages у предыдущего состояния, если поменялся статус
	query = update.callback_query

	await query.answer()
	query_data = query.data.split('__')
	if len(query_data) < 2:
		return None

	order_id = int(query_data[0].lstrip("order_"))
	status = int(query_data[1].lstrip("status_"))
	order = context.chat_data["orders"][order_id]
	order_status, date_string = get_order_status(order)
	_, _, prev_inline_messages, _, _ = get_menu_item(context, -2)

	order = await update_order(query.message, context, order_id, data={"status": status})
	if order:
		order_status_text = ORDER_STATUS[status]
		if status == 2:
			markup = None
			for message in prev_inline_messages:
				if search_message_by_data(message, substring=f'order_{order_id}'):
					prev_inline_messages.remove(message)
					break

		else:
			# TODO: [task 1]: Уведомить в сообщении что заказ был снят
			for index, message in enumerate(prev_inline_messages):
				if search_message_by_data(message, substring=f'order_{order_id}'):
					message_text = update_text_by_keyword(message.text_markdown, "статус:", f'статус: *{order_status}*')
					# prev_inline_messages[index] = message
					break

			if status == 0:
				_, _, inline_messages, _, _ = get_menu_item(context)
				for message in inline_messages:
					if search_message_by_data(message, substring="user_"):
						await delete_messages_by_key(context, message)
			else:
				pass

			buttons = [
				InlineKeyboardButton(
					ORDER_ACTIONS_KEYBOARD[status],
					callback_data=f'order_{order["id"]}__status_{"0" if status == 1 else "1"}'
				)
			]
			markup = InlineKeyboardMarkup([buttons])

		await query.message.edit_text(
			update_text_by_keyword(query.message.text_markdown, "Статус:", f'Статус: *{order_status_text}*'),
			reply_markup=markup
		)

		# обновим сообщения из предыдущего уровня меню
		update_menu_item(context, inline_messages=prev_inline_messages, index=-2)


async def select_order_executor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк выбора и снятия дизайнером исполнителя заказа """

	query = update.callback_query

	await query.answer()
	query_data = query.data.split('__')
	if len(query_data) < 2:
		return
	order_id = int(query_data[0].lstrip("order_"))
	executor_id = int(query_data[1].lstrip("executor_"))
	is_selected = True if len(query_data) > 2 else False
	_, _, inline_messages, _, _ = get_menu_item(context)

	order = context.chat_data["orders"][order_id]
	if order["status"] == 0:
		await edit_last_message(query, context, "🚫 Операция недоступна если заказ не активирован!")
		return

	if order["status"] == 2:
		await edit_last_message(query, context, "🚫 Операция недоступна если заказ завершен!")
		return

	# выбор исполнителя
	if not is_selected:
		# сохранение изменяемых данных заказа
		order = await update_order(query.message, context, order_id, data={"executor": executor_id})
		if not order:
			return

		order_buttons = generate_inline_keyboard(
			[[ORDER_EXECUTOR_KEYBOARD[0], ORDER_EXECUTOR_KEYBOARD[2]]],
			callback_data=query.data + "__selected"
		)
		# обновим кнопку после выбора исполнителя
		await query.message.edit_reply_markup(order_buttons)

		# изменение сообщения с заголовком и удаление с экрана оставшихся претендентов
		for i, message in enumerate(inline_messages):
			if i == 0:
				buttons = [
					InlineKeyboardButton(ORDER_ACTIONS_KEYBOARD[2], callback_data=f'order_{order["id"]}__status_2')
				]
				await message.edit_reply_markup(InlineKeyboardMarkup([buttons]))

			elif i == 1:
				await message.edit_text(
					f'_{ORDER_RELATED_USERS_TITLE[0] if is_selected else ORDER_RELATED_USERS_TITLE[1]}:_',
				)

			elif search_message_by_data(message, substring="user") != query.message.message_id:
				await delete_messages_by_key(context, message)

	# отказ от исполнителя
	else:
		# TODO: добавить появление кнопок у сообщения с описанием заказа inline_message.reply_markup
		# сохранение изменяемых данных заказа с пустым значением executor и удалим из претендентов выбранного пользователя
		order = await update_order(query.message, context, order_id, params={"clear_executor": executor_id})
		if not order:
			return

		inline_message = inline_messages.pop(0)
		# добавление кнопки Приостановить заказ в сообщении с описанием
		buttons = [
			InlineKeyboardButton(ORDER_ACTIONS_KEYBOARD[1], callback_data=f'order_{order["id"]}__status_0')
		]
		await inline_message.edit_reply_markup(InlineKeyboardMarkup([buttons]))
		await delete_messages_by_key(context, inline_messages)
		inline_messages = [inline_message]
		await show_order_related_users_message(query.message, order, inline_messages)
		context.chat_data["menu"][-1]["inline_message"] = inline_messages

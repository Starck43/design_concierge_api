from typing import Optional

from telegram import Update, Message
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	SUPPLIERS_REGISTER_KEYBOARD, USER_DETAILS_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD,
	DESIGNER_SERVICES_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SEGMENT_KEYBOARD, DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD,
	FAVORITE_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import (
	select_events_message, send_unknown_question_message, choose_sandbox_message,
	show_after_set_segment_message, success_save_rating_message, offer_to_save_rating_message,
	show_detail_rating_message, yourself_rate_warning_message, show_categories_message,
	show_designer_active_orders_message, add_new_user_message, empty_data_message
)
from bot.constants.patterns import USER_RATE_PATTERN, ADD_FAVOURITE_PATTERN, REMOVE_FAVOURITE_PATTERN, EVENTS_PATTERN, \
	SANDBOX_PATTERN
from bot.handlers.common import (
	go_back, get_menu_item, delete_messages_by_key, update_ratings, check_required_user_group_rating, load_cat_users,
	load_categories, load_user, get_user_rating_data, load_orders, is_outsourcer, update_user_data, build_menu_item
)
from bot.handlers.details import user_details
from bot.handlers.questionnaire import show_user_rating_messages
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_keyboard, match_message_text, fetch_user_data, send_action, find_obj_in_list, format_output_text,
	replace_or_add_string, rates_to_string
)


async def main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Обработчик Главного меню для группы Дизайнеры (0)
	group = context.user_data["group"]
	chat_data = context.chat_data
	state, message, inline_message, menu_markup, _ = get_menu_item(context)
	message_text = update.message.text.lower()

	# Раздел - РЕЕСТР ПОСТАВЩИКОВ
	if group in [
		Group.DESIGNER, Group.SUPPLIER
	] and match_message_text(str(MenuState.SUPPLIERS_REGISTER), message_text):
		state = MenuState.SUPPLIERS_REGISTER
		if group == Group.DESIGNER:
			menu_markup = generate_reply_keyboard(SUPPLIERS_REGISTER_KEYBOARD, is_persistent=True)
		else:
			menu_markup = back_menu

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
	elif group in [
		Group.DESIGNER, Group.OUTSOURCER
	] and match_message_text(str(MenuState.OUTSOURCER_SERVICES), message_text):
		state = MenuState.OUTSOURCER_SERVICES

		if group == Group.DESIGNER:
			keyboard = DESIGNER_SERVICES_KEYBOARD
			if is_outsourcer(context):
				# TODO: [task 1]:
				#  создать логику отображения списка заказов дизайнеров через нажатие на кнопку "Все заказы"
				keyboard = DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD

			menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)
			title = str(state).upper()

			message = await update.message.reply_text(
				f'__{title}__',
				reply_markup=menu_markup,
			)

			if "outsourcer_categories" not in chat_data or not chat_data["outsourcer_categories"]:
				# Получим список аутсорсеров
				chat_data["outsourcer_categories"] = await load_categories(update.message, context, group=1)
				if not chat_data["outsourcer_categories"]:
					return await go_back(update, context, -1)

			# выведем список категорий аутсорсеров
			inline_message = await show_categories_message(update.message, chat_data["outsourcer_categories"])

		else:
			menu_markup = back_menu
			# если пользователь только в группе Аутсорсер
			# TODO: [task 1]: создать логику показа заказов дизайнеров
			orders = await load_orders(update.message, context)
			message, inline_message = await show_designer_active_orders_message(update.message, orders)

	# Раздел - СОБЫТИЯ
	elif group in [
		Group.DESIGNER, Group.OUTSOURCER
	] and match_message_text(EVENTS_PATTERN, message_text):
		state = MenuState.DESIGNER_EVENTS
		title = str(state).upper()
		menu_markup = back_menu
		message = await update.message.reply_text(
			f'__{title}__',
			reply_markup=menu_markup
		)
		inline_message = await select_events_message(update.message)

	# Раздел - БАРАХОЛКА (купить/продать/поболтать)
	elif group in [
		Group.DESIGNER, Group.OUTSOURCER
	] and match_message_text(SANDBOX_PATTERN, message_text):
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

	menu_item = build_menu_item(state, message, inline_message, menu_markup)
	chat_data["menu"].append(menu_item)

	return state or MenuState.START


async def designer_active_orders_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Функция отображения списка всех активных заказов для группы 0 и 1
	chat_data = context.chat_data

	_, _, inline_message, _, _ = get_menu_item(context)
	await delete_messages_by_key(context, inline_message)  # удалим с экрана список категорий

	state = MenuState.ORDERS
	menu_markup = back_menu

	orders = await load_orders(update.message, context)
	message, inline_message = await show_designer_active_orders_message(update.message, orders)

	menu_item = build_menu_item(state, message, inline_message, menu_markup)
	chat_data["menu"].append(menu_item)

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

	menu_item = build_menu_item(state, message, inline_message, menu_markup)
	chat_data["menu"].append(menu_item)

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
			keyboard = USER_DETAILS_KEYBOARD
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
		menu_item = build_menu_item(state, message, None, menu_markup)
		chat_data["menu"].append(menu_item)

	return state


@send_action(ChatAction.TYPING)
async def select_users_in_category(
		update: Update,
		context: ContextTypes.DEFAULT_TYPE,
		is_supplier_register: bool
) -> str:
	query = update.callback_query

	await query.answer()
	cat_id = query.data.lstrip("category_")
	group = context.user_data["group"]
	chat_data = context.chat_data

	state, message, inline_message, _, _ = get_menu_item(context)
	menu_markup = back_menu

	button_list = await load_cat_users(query.message, context, cat_id)
	if button_list is None:
		return await go_back(update, context, -1)

	if group == Group.DESIGNER:
		if is_supplier_register:
			keyboard = SUPPLIERS_REGISTER_KEYBOARD
		else:
			keyboard = DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD if is_outsourcer(
				context) else DESIGNER_SERVICES_KEYBOARD

		menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)

	selected_cat, _ = find_obj_in_list(
		chat_data["supplier_categories" if is_supplier_register else "outsourcer_categories"],
		{"id": int(cat_id)}
	)

	chat_data["selected_cat"] = selected_cat
	category_name = selected_cat["name"].upper()
	title = f'➡️ Категория *{category_name}*'
	subtitle = "Список поставщиков:" if is_supplier_register else "Список поставщиков услуг:"

	await query.message.delete()
	message = await query.message.reply_text(
		text=title,
		reply_markup=menu_markup,
	)
	inline_message = await query.message.reply_text(
		text=subtitle,
		reply_markup=button_list
	)

	menu_item = build_menu_item(state, message, inline_message, menu_markup)
	chat_data["menu"].append(menu_item)

	return state


async def select_suppliers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор поставщиков в категории в разделе Реестр поставщиков
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data

	state = await select_users_in_category(update, context, is_supplier_register=True)

	# [task 3]: реализовать добавление рекомендованного пользователя
	message = await add_new_user_message(query.message, category=chat_data["selected_cat"])
	chat_data["last_message_id"] = message.message_id
	return state


async def select_outsourcers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор аутсорсеров в категории в разделе Биржа услуг
	state = await select_users_in_category(update, context, is_supplier_register=False)
	return state


async def add_new_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Добавление нового пользователя для текущей группы
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data
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

	menu_item = build_menu_item(state, message, None, menu_markup)
	chat_data["menu"].append(menu_item)

	return state


@send_action(ChatAction.TYPING)
async def select_user_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор поставщика через callback_data "user_{id}"
	query = update.callback_query

	await query.answer()
	supplier_id = int(query.data.lstrip("user_"))
	chat_data = context.chat_data
	chat_data.setdefault("suppliers", {})
	supplier = context.chat_data.get("supplier", {}).get(supplier_id, None)
	designer_id = context.user_data["details"]["id"]
	group = context.user_data["group"]

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
			user_name = data.get("name", None)
			if user_name is None:
				data["name"] = data["username"]
			chat_data["suppliers"].update({supplier_id: data})

	chat_data["selected_user"] = chat_data["suppliers"][supplier_id]  # обязательно сохранять в selected_user

	if group == Group.DESIGNER and supplier_id != designer_id:
		keyboard = USER_DETAILS_KEYBOARD
		in_favourite = chat_data["selected_user"].get("in_favourite")
		if in_favourite:
			keyboard[0][1] = FAVORITE_KEYBOARD[1]
		menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)

	menu_item = build_menu_item(state, message, None, menu_markup)
	chat_data["menu"].append(menu_item)

	await query.message.delete()  # удалим список поставщиков
	await delete_messages_by_key(context, "last_message_id")
	await user_details(query, context)

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
				chat_data[
					"error"] = "Данные выбранного поставщика отсутствуют или нет сохраненных вопросов для рейтинга."
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
			edited_segment_text = replace_or_add_string(
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

	menu_item = build_menu_item(state, message, None, menu_markup)
	chat_data["menu"].append(menu_item)

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

	menu_item = build_menu_item(state, message, None, menu_markup)
	chat_data["menu"].append(menu_item)

	return state


async def place_designer_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Разместить заказ на бирже
	query = update.callback_query

	await query.answer()
	order_id = query.data
	chat_data = context.chat_data

	state = MenuState.OUTSOURCER_SERVICES
	menu_markup = generate_reply_keyboard(DESIGNER_SERVICES_KEYBOARD, is_persistent=True)

	if order_id:
		message = await query.message.reply_text(
			f'Необходимо выбрать параметры для размещения...',
			reply_markup=menu_markup,
		)

	else:
		message = await send_unknown_question_message(query.message)

	menu_item = build_menu_item(state, message, None, menu_markup)
	chat_data["menu"].append(menu_item)

	return state

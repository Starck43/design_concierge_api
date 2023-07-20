import re
from typing import Optional

from telegram import Update, Message
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	SUPPLIERS_REGISTER_KEYBOARD, SUPPLIER_DETAILS_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD,
	DESIGNER_EXCHANGE_KEYBOARD, DESIGNER_EVENTS_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SEGMENT_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import (
	select_events_message, place_exchange_order_message, send_unknown_question_message, choose_sandbox_message,
	show_after_set_segment_message, success_save_rating_message, offer_to_save_rating_message,
	show_rating_title_message, yourself_rate_warning_message, show_categories_message
)
from bot.handlers.common import (
	go_back, get_state_menu, delete_messages_by_key, update_ratings, check_required_user_group_rating, load_cat_users,
	load_categories, load_user, get_user_rating_data
)
from bot.handlers.details import user_details
from bot.handlers.questionnaire import show_user_rating_messages
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_keyboard, generate_inline_keyboard, fetch_user_data, find_obj_in_list, send_action,
	extract_fields, format_output_text, replace_or_add_string, rating_to_string
)


async def main_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Функция выбора реестра поставщиков
	group = context.user_data["group"]
	chat_data = context.chat_data
	chat_data.pop("sub_state", None)
	message_text = update.message.text.lower()
	state, message, inline_message, menu_markup, _ = get_state_menu(context)

	# Раздел - РЕЕСТР ПОСТАВЩИКОВ
	if group in [Group.DESIGNER, Group.SUPPLIER] and re.search(str(MenuState.SUPPLIERS_REGISTER), message_text, re.I):
		state = MenuState.SUPPLIERS_REGISTER
		if group == Group.DESIGNER:
			menu_markup = generate_reply_keyboard(SUPPLIERS_REGISTER_KEYBOARD, is_persistent=True)
		else:
			menu_markup = back_menu

		if "categories" not in chat_data or not chat_data["categories"]:
			# Получим список поставщиков для добавления в реестр
			chat_data["categories"] = await load_categories(update.message, context, group=2)
			if not chat_data["categories"]:
				return await go_back(update, context, -1)

		title = str(state).upper()

		message = await update.message.reply_text(
			text=f'*{title}*',
			reply_markup=menu_markup,
		)
		# выведем список категорий поставщиков
		inline_message = await show_categories_message(update.message, chat_data["categories"])
		chat_data["last_message_id"] = inline_message.message_id

	# Раздел - БИРЖА УСЛУГ
	elif group in [Group.DESIGNER, Group.OUTSOURCER] and re.search(str(MenuState.DESIGNER_EXCHANGE), message_text, re.I):
		state = MenuState.DESIGNER_EXCHANGE
		title = str(state).upper()
		menu_markup = generate_reply_keyboard(DESIGNER_EXCHANGE_KEYBOARD, is_persistent=True)
		message = await update.message.reply_text(
			f'__{title}__',
			reply_markup=menu_markup,
		)

		if group == Group.DESIGNER:
			if "outsourcer_categories" not in chat_data or not chat_data["outsourcer_categories"]:
				# Получим список аутсорсеров для добавления в реестр
				chat_data["outsourcer_categories"] = await load_categories(update.message, context, group=1)
				if not chat_data["outsourcer_categories"]:
					return await go_back(update, context, -1)

			# выведем список категорий поставщиков
			inline_message = await show_categories_message(update.message, chat_data["outsourcer_categories"])
			chat_data["last_message_id"] = inline_message.message_id

		# выведем кнопку для создания заявки
		inline_message = await place_exchange_order_message(update.message)
		chat_data["last_message_id"] = inline_message.message_id

	elif group in [Group.DESIGNER, Group.OUTSOURCER] and re.search(str(MenuState.DESIGNER_EVENTS), message_text, re.I):
		state = MenuState.DESIGNER_EVENTS
		title = str(state).upper()
		menu_markup = back_menu
		message = await update.message.reply_text(
			f'__{title}__',
			reply_markup=menu_markup
		)

		inline_message = await select_events_message(update.message)

	elif group in [Group.DESIGNER, Group.OUTSOURCER] and re.search(str(MenuState.DESIGNER_SANDBOX), message_text, re.I):
		state = MenuState.DESIGNER_SANDBOX
		title = str(state).upper()
		message = await update.message.reply_text(
			f'__{title}__\n',
			reply_markup=menu_markup
		)

		inline_message = await choose_sandbox_message(update.message)

	else:
		message = None
		await send_unknown_question_message(update.message)

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": inline_message,
		"markup": menu_markup,
		"inline_markup": None,
	})

	return state or MenuState.START


async def supplier_details_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	group = context.user_data["group"]
	chat_data = context.chat_data
	chat_data["sub_state"] = ""
	message_text = update.message.text.lower()
	state = MenuState.SUPPLIER_DETAILS
	if group == Group.DESIGNER:
		menu_markup = generate_reply_keyboard(SUPPLIER_DETAILS_KEYBOARD, is_persistent=True)
	else:
		menu_markup = back_menu

	if message_text == str(MenuState.SUPPLIER_SEARCH).lower() and message_text != chat_data["sub_state"]:
		message = await update.message.reply_text(
			f'__Подбор поставщика__\n'
			f'Выбор условий поиска (в разработке)',
			reply_markup=menu_markup,
		)

	elif message_text == str(MenuState.SUPPLIER_RATE).lower() and message_text != chat_data["sub_state"]:
		supplier = chat_data.get("selected_user", {})
		if not supplier:
			return state

		message = await update.message.reply_text(
			f'*{supplier["username"]}*',
			reply_markup=menu_markup
		)

		# вывод рейтинга
		if context.bot_data.get("rating_questions"):
			rates = supplier.get("designer_rating", {})
			chat_data["user_ratings"] = [{"receiver_id": rates["receiver_id"]}]
			rates_list = []
			for key, val in rates.items():
				if val and key != "receiver_id":
					rates_list.append(val)
					chat_data["user_ratings"][0].update({key: val})

			designer_rating = f'⭐{round(sum(rates_list) / len(rates_list), 1)}' if rates_list else ""
			if designer_rating:
				rating_title = format_output_text("`Ваша текущая оценка`", designer_rating,
				                                  default_value="Новый рейтинг", value_tag="_")
			else:
				rating_title = "Оцените все критерии поставщика:"

			await show_user_rating_messages(update.message, context, title=rating_title)

		chat_data["saved_submit_rating_message"] = await offer_to_save_rating_message(update.message)

	elif message_text != chat_data["sub_state"]:
		message = None

	else:
		message = None
		await send_unknown_question_message(update.message)

	chat_data["sub_state"] = message_text
	last_state, _ = find_obj_in_list(chat_data["menu"], {"state": state})
	# сохраним одно состояние для всех подсостояний sub_state
	if not last_state:
		chat_data["menu"].append({
			"state": state,
			"message": message,
			"inline_message": None,
			"markup": menu_markup,
			"inline_markup": None,
		})

	return state


@send_action(ChatAction.TYPING)
async def select_suppliers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор категории поставщиков
	query = update.callback_query

	await query.answer()
	cat_id = query.data.lstrip("category_")
	group = context.user_data["group"]
	chat_data = context.chat_data

	suppliers_list_buttons = await load_cat_users(query.message, context, cat_id)
	if suppliers_list_buttons is None:
		return await go_back(update, context, -1)

	state = MenuState.SUPPLIERS_REGISTER
	if group == Group.DESIGNER:
		menu_markup = generate_reply_keyboard(SUPPLIERS_REGISTER_KEYBOARD, is_persistent=True)
	else:
		menu_markup = back_menu

	selected_cat, _ = find_obj_in_list(chat_data["categories"], {"id": int(cat_id)})
	chat_data["selected_cat"] = selected_cat

	title = f'➡️ Раздел *{selected_cat["name"].upper()}*'
	subtitle = "Список поставщиков:"

	await query.message.delete()  # удалим кнопки выбора категорий
	message = await query.message.reply_text(
		text=title,
		reply_markup=menu_markup,
	)

	# формируем инлайн кнопки поставщиков
	inline_message = await query.message.reply_text(
		text=subtitle,
		reply_markup=suppliers_list_buttons
	)

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": inline_message,
		"markup": menu_markup,
		"inline_markup": None,
	})

	return state


@send_action(ChatAction.TYPING)
async def select_supplier_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор поставщика через callback_data "supplier_{id}"
	query = update.callback_query

	await query.answer()
	supplier_id = int(query.data.lstrip("supplier_"))
	chat_data = context.chat_data
	chat_data.setdefault("suppliers", {})
	supplier = context.chat_data.get("supplier", {}).get(supplier_id, None)
	designer_id = context.user_data["details"]["id"]
	group = context.user_data["group"]

	state = MenuState.SUPPLIER_DETAILS
	if group == Group.DESIGNER:
		keyboard = SUPPLIERS_REGISTER_KEYBOARD if supplier_id == designer_id else SUPPLIER_DETAILS_KEYBOARD
		menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)
	else:
		menu_markup = back_menu

	if not supplier:
		data = await load_user(query.message, context, user_id=supplier_id, designer_id=designer_id)
		if data is None:
			return await go_back(update, context, -1)
		else:
			# TODO: Добавить механизм очистки редко используемых поставщиков
			chat_data["suppliers"].update({supplier_id: data})

	chat_data["selected_user"] = chat_data["suppliers"][supplier_id]  # обязательно сохранять в selected_user

	chat_data["menu"].append({
		"state": state,
		"message": None,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": None,
	})

	await query.message.delete()  # удалим кнопки выбора поставщика
	await user_details(query, context)

	return state


@send_action(ChatAction.TYPING)
async def save_supplier_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Сохранение рейтинга поставщика
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data
	designer_id = context.user_data["details"]["id"]
	user_id = context.user_data["details"]["user_id"]
	saved_submit_rating_message = chat_data.get("saved_submit_rating_message", chat_data["saved_rating_message"])

	if user_id == designer_id:
		await yourself_rate_warning_message(saved_submit_rating_message)

	if not await check_required_user_group_rating(query.message, context):
		await delete_messages_by_key(context, "last_message_id")

		data = await update_ratings(query.message, context, user_id=user_id, data=chat_data["user_ratings"])
		if data:
			user = data[0]
			await success_save_rating_message(saved_submit_rating_message, user_data=user)

			# получаем и обновляем сохраненные данные поставщиков
			res = await fetch_user_data(user["id"], params={"related_user": designer_id})
			selected_user = res["data"]
			if selected_user:
				chat_data["selected_user"] = selected_user
				chat_data["suppliers"].update({user["id"]: res["data"]})

				# удалим всех поставщиков из сохраненных в cat_users
				cat_users = chat_data.get("cat_users", {})
				cat_ids = extract_fields(selected_user["categories"], "id")
				[cat_users[cat_id].clear() for cat_id in cat_ids if cat_id in cat_users]

				# обновим сохраненное состояние со списком поставщиков через inline_markup в menu
				selected_cat = chat_data.get("selected_cat", {})
				updated_reply_markup = await load_cat_users(query.message, context, selected_cat.get("id"))
				if updated_reply_markup:
					prev_menu = chat_data["menu"][-2]
					prev_menu["inline_markup"] = updated_reply_markup

				_, _, avg_rating_text = get_user_rating_data(context, selected_user)

				# выведем сообщение с обновленным рейтингом
				message = await show_rating_title_message(query.message, avg_rating_text)
				chat_data["last_message_id"] = message.message_id

		chat_data.pop("user_ratings", None)
		await delete_messages_by_key(context, "once_message_ids")


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
			text = replace_or_add_string(
				text=saved_message.text_markdown,
				keyword="Сегмент",
				replacement=f'`Сегмент`: 🎯 _{SEGMENT_KEYBOARD[segment][0]}_'
			)
			await saved_message.edit_text(text)

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

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": None,
	})

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

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": None,
	})

	return state


async def place_exchange_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Разместить заявку на бирже
	query = update.callback_query

	await query.answer()
	order_id = query.data
	chat_data = context.chat_data

	state = MenuState.DESIGNER_EXCHANGE
	menu_markup = generate_reply_keyboard(DESIGNER_EXCHANGE_KEYBOARD, is_persistent=True)

	if order_id:
		message = await query.message.reply_text(
			f'Необходимо выбрать параметры для размещения...',
			reply_markup=menu_markup,
		)

	else:
		message = await send_unknown_question_message(query.message)

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": None,
	})

	return state

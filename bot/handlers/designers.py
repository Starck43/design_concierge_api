import re
from typing import Optional

from telegram import Update, Message
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	SUPPLIERS_REGISTER_KEYBOARD, USER_DETAILS_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD,
	DESIGNER_SERVICES_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SEGMENT_KEYBOARD
)
from bot.constants.menus import back_menu
from bot.constants.messages import (
	select_events_message, show_designer_order_message, send_unknown_question_message, choose_sandbox_message,
	show_after_set_segment_message, success_save_rating_message, offer_to_save_rating_message,
	show_rating_title_message, yourself_rate_warning_message, show_categories_message
)
from bot.constants.patterns import USER_RATE_PATTERN, USER_FEEDBACK_PATTERN
from bot.handlers.common import (
	go_back, get_state_menu, delete_messages_by_key, update_ratings, check_required_user_group_rating, load_cat_users,
	load_categories, load_user, get_user_rating_data
)
from bot.handlers.details import user_details
from bot.handlers.questionnaire import show_user_rating_messages
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_keyboard, fetch_user_data, send_action, find_obj_in_list, extract_fields, format_output_text,
	replace_or_add_string, match_message_text
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
	elif group in [Group.DESIGNER, Group.OUTSOURCER] and re.search(str(MenuState.OUTSOURCER_SERVICES), message_text,
	                                                               re.I):
		state = MenuState.OUTSOURCER_SERVICES
		title = str(state).upper()
		message = await update.message.reply_text(
			f'__{title}__',
			reply_markup=menu_markup,
		)

		if group == Group.DESIGNER:
			keyboard = DESIGNER_SERVICES_KEYBOARD

			if "outsourcer_categories" not in chat_data or not chat_data["outsourcer_categories"]:
				# Получим список аутсорсеров
				chat_data["outsourcer_categories"] = await load_categories(update.message, context, group=1)
				if not chat_data["outsourcer_categories"]:
					return await go_back(update, context, -1)

			# выведем список категорий аутсорсеров
			inline_message = await show_categories_message(update.message, chat_data["outsourcer_categories"])

		else:
			# [task 1]: вывести inline список активных заказов дизайнеров
			keyboard = DESIGNER_SERVICES_KEYBOARD
			del keyboard[0][2]
			inline_message = await update.message.reply_text(
				f'Текущие заказы:'
			)

		menu_markup = generate_reply_keyboard(keyboard, is_persistent=True)

	# Раздел - СОБЫТИЯ
	elif group in [Group.DESIGNER, Group.OUTSOURCER] and re.search(str(MenuState.DESIGNER_EVENTS), message_text, re.I):
		state = MenuState.DESIGNER_EVENTS
		title = str(state).upper()
		menu_markup = back_menu
		message = await update.message.reply_text(
			f'__{title}__',
			reply_markup=menu_markup
		)
		inline_message = await select_events_message(update.message)

	# Раздел - БАРАХОЛКА
	elif group in [Group.DESIGNER, Group.OUTSOURCER] and re.search(str(MenuState.DESIGNER_SANDBOX), message_text, re.I):
		state = MenuState.DESIGNER_SANDBOX
		title = str(state).upper()
		message = await update.message.reply_text(
			f'__{title}__\n',
			reply_markup=menu_markup
		)
		inline_message = await choose_sandbox_message(update.message)

	else:
		await send_unknown_question_message(update.message)

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": inline_message,
		"markup": menu_markup,
		"inline_markup": None,
	})

	return state or MenuState.START


async def suppliers_search_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Функция поиска поставщиков
	chat_data = context.chat_data
	state = MenuState.SUPPLIERS_SEARCH
	title = str(state).upper()
	menu_markup = back_menu

	# TODO: Разработать механизм поиска поставщика в таблице User по критериям
	message = await update.message.reply_text(
		f'__{title}__\n'
		f'Выберите критерии поиска:\n'
		f'[кнопки]',
		reply_markup=menu_markup,
	)

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": None,
	})

	return state


async def user_details_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	group = context.user_data["group"]
	chat_data = context.chat_data
	chat_data["sub_state"] = ""
	selected_user = chat_data["selected_user"]
	# selected_user_group = Group.get_enum(max(selected_user["groups"]))

	message_text = update.message.text
	state = MenuState.USER_DETAILS

	if group == Group.DESIGNER:
		menu_markup = generate_reply_keyboard(USER_DETAILS_KEYBOARD, is_persistent=True)
	else:
		menu_markup = back_menu

	# Подраздел - ОБНОВИТЬ РЕЙТИНГ
	if match_message_text(USER_RATE_PATTERN, message_text):
		if chat_data["sub_state"] == "feedback_state":
			return

		chat_data["sub_state"] = "rating_state"
		message = await update.message.reply_text(
			f'*{selected_user["name"]}*',
			reply_markup=menu_markup
		)

		# вывод рейтинга
		if context.bot_data.get("rating_questions"):
			rates = selected_user.get("designer_rating", {})
			chat_data["user_ratings"] = [{"receiver_id": rates["receiver_id"]}]
			rates_list = []
			for key, val in rates.items():
				if val and key != "receiver_id":
					rates_list.append(val)
					chat_data["user_ratings"][0].update({key: val})

			designer_rating = f'⭐{round(sum(rates_list) / len(rates_list), 1)}' if rates_list else ""
			if designer_rating:
				rating_title = format_output_text(
					"`Ваша текущая оценка`",
					designer_rating,
					default_value="Новый рейтинг",
					value_tag="_"
				)
			else:
				rating_title = "Оцените все критерии поставщика:"

			await show_user_rating_messages(update.message, context, title=rating_title)

		chat_data["saved_submit_rating_message"] = await offer_to_save_rating_message(update.message)

	# Подраздел - ОТЗЫВ
	elif match_message_text(USER_FEEDBACK_PATTERN, message_text):
		if chat_data["sub_state"] == "feedback_state":
			return

		chat_data["sub_state"] = "feedback_state"
		message = await update.message.reply_text(
			f'*Напишите отзыв о поставщике:\n'
			f'{selected_user["name"].upper()}*',
		)

	elif chat_data["sub_state"] == "feedback_state":
		await update.message.delete()
		message = await update.message.reply_text(
			f'{selected_user["name"].upper()}\n'
			f'Отзыв успешно отправлен!\n',
			reply_markup=menu_markup
		)

	else:
		message = None
		await send_unknown_question_message(update.message)

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
async def select_outsourcers_in_cat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Выбор категории аутсорсеров
	query = update.callback_query

	await query.answer()
	cat_id = query.data.lstrip("category_")
	group = context.user_data["group"]
	chat_data = context.chat_data
	state, message, inline_message, menu_markup, _ = get_state_menu(context)

	outsourcer_list_buttons = await load_cat_users(query.message, context, cat_id)
	if outsourcer_list_buttons is None:
		return await go_back(update, context, -1)

	if group == Group.DESIGNER:
		menu_markup = generate_reply_keyboard(DESIGNER_SERVICES_KEYBOARD, is_persistent=True)
	else:
		menu_markup = back_menu

	selected_cat, _ = find_obj_in_list(chat_data["outsourcer_categories"], {"id": int(cat_id)})
	chat_data["selected_cat"] = selected_cat

	title = f'➡️ Категория *{selected_cat["name"].upper()}*'
	subtitle = "Список аутсорсеров:"

	await query.message.delete()
	message = await query.message.reply_text(
		text=title,
		reply_markup=menu_markup,
	)

	# формируем инлайн кнопки аутсорсеров в текущей категории
	inline_message = await query.message.reply_text(
		text=subtitle,
		reply_markup=outsourcer_list_buttons
	)

	if group == Group.DESIGNER:
		# выведем кнопку для создания заказа в текущей категории
		order_message = await show_designer_order_message(query.message, category=selected_cat["name"])
		# сохраним id инлайн сообщения, чтобы при возврате в меню оно удалилось
		chat_data["last_message_id"] = order_message.message_id

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": inline_message,
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
	state, message, inline_message, menu_markup, _ = get_state_menu(context)

	supplier_list_buttons = await load_cat_users(query.message, context, cat_id)
	if supplier_list_buttons is None:
		return await go_back(update, context, -1)

	if group == Group.DESIGNER:
		menu_markup = generate_reply_keyboard(SUPPLIERS_REGISTER_KEYBOARD, is_persistent=True)
	else:
		menu_markup = back_menu

	selected_cat, _ = find_obj_in_list(chat_data["supplier_categories"], {"id": int(cat_id)})
	chat_data["selected_cat"] = selected_cat

	title = f'➡️ Категория *{selected_cat["name"].upper()}*'
	subtitle = "Список поставщиков:"

	await query.message.delete()
	message = await query.message.reply_text(
		text=title,
		reply_markup=menu_markup,
	)

	# формируем инлайн кнопки поставщиков
	inline_message = await query.message.reply_text(
		text=subtitle,
		reply_markup=supplier_list_buttons
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
	if group == Group.DESIGNER and supplier_id != designer_id:
		menu_markup = generate_reply_keyboard(USER_DETAILS_KEYBOARD, is_persistent=True)
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
	user_id = context.user_data["details"]["user_id"]
	saved_submit_rating_message = chat_data.get("saved_submit_rating_message", chat_data["saved_rating_message"])

	if user_id == designer_id:
		await yourself_rate_warning_message(saved_submit_rating_message)

	if not await check_required_user_group_rating(query.message, context):
		await delete_messages_by_key(context, "last_message_id")

		data = await update_ratings(query.message, context, user_id=user_id, data=chat_data["user_ratings"])
		if data:
			updated_user = data[0]
			await success_save_rating_message(saved_submit_rating_message, user_data=updated_user)

			# получаем и обновляем сохраненные данные поставщиков
			res = await fetch_user_data(updated_user["id"], params={"related_user": designer_id})
			selected_user = res["data"]
			if selected_user:
				chat_data["selected_user"] = selected_user
				chat_data["suppliers"].update({updated_user["id"]: res["data"]})

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
		await delete_messages_by_key(context, "saved_message_ids")


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

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": None,
	})

	return state

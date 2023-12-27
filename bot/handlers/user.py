from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID
from bot.constants.keyboards import REG_GROUP_KEYBOARD, SEGMENT_KEYBOARD
from bot.constants.menus import back_menu, continue_menu, cancel_menu
from bot.constants.messages import select_user_group_message, offer_to_select_segment_message, confirm_region_message
from bot.constants.patterns import CONTINUE_PATTERN, CANCEL_PATTERN
from bot.handlers.common import get_section, prepare_current_section, add_section, generate_categories_list, \
	edit_or_reply_message, delete_messages_by_key, send_error_to_admin, regenerate_inline_keyboard, load_regions, \
	go_back_section, send_message_to
from bot.states.main import MenuState
from bot.utils import match_query, fetch_user_data, format_output_text, extract_fields, fuzzy_compare, \
	dict_to_formatted_text


async def recommend_user_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция обработки сообщений при добавлении данных рекомендованного пользователя """

	# TODO: исправить нюанс при возврате назад на первом вопросе
	chat_data = context.chat_data
	section = get_section(context)
	query_message = update.message.text

	if match_query(CANCEL_PATTERN, query_message):
		return await go_back_section(update, context, message_text="🚫 Операция прервана!")

	state = section["state"]
	messages = []
	local_data = context.chat_data.setdefault("local_data", {})
	field_name = local_data.setdefault("user_field_name", {})
	selected_groups = local_data.get("selected_groups", [])
	selected_categories = local_data.get("selected_categories", {})
	selected_segment = local_data.get("selected_segment")
	no_selected_groups = field_name == "group" and not selected_groups
	no_selected_categories = field_name == "categories" and not selected_categories
	is_continue = match_query(CONTINUE_PATTERN, query_message)

	if is_continue:
		await update.message.delete()
	else:
		section["messages"].append(update.message.message_id)

	if field_name == "categories" and selected_categories:
		local_data["user_data"]["categories"] = list(selected_categories.keys())
		categories = extract_fields(selected_categories.values(), field_names="name")
		text = format_output_text("☑️ Сферы деятельности", categories, tag="*")
		await edit_or_reply_message(context, text, message=section["messages"][-1])

	elif field_name == "segment" and selected_segment:
		local_data["user_data"][field_name] = int(selected_segment)
		text = f'☑️ Сегмент: *{SEGMENT_KEYBOARD[selected_segment]}*'
		await edit_or_reply_message(context, text, message=section["messages"][-1])

	if not is_continue and field_name in ["group", "categories"] or is_continue and (
			no_selected_categories or no_selected_groups
	):
		text = "Необходимо выбрать вариант из списка и нажать *Продолжить*"
		chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			text=text,
			message_type="warn",
			reply_markup=continue_menu
		)
		return state

	elif field_name == "name":
		local_data["user_data"] = {field_name: query_message}
		local_data["user_field_name"] = "main_region"

		# если регионы не загрузились, то выведем название и пропустим этап ввода региона
		if not chat_data["region_list"]:
			text = f'☑️ *{query_message}*'
			local_data["user_data"]["main_region"] = None
		else:
			text = 'Укажите основной регион в котором работает компания:'

		message = await update.message.reply_text(text=text, reply_markup=cancel_menu)
		messages.append(message.message_id)

	elif field_name == "main_region" and not local_data["user_data"].get(field_name) and chat_data["region_list"]:
		if is_continue:
			found_region = local_data.get("found_region")
			local_data["user_data"]["main_region"] = found_region["id"] if found_region else None

		else:
			found_region, c, _ = fuzzy_compare(query_message, chat_data["region_list"], "name", 0.3)
			if not found_region:
				text = f'Регион с названием *{query_message}* не найден!\n' \
				       f'Введите корректное название региона или нажмите *Продолжить*'
				message_id = await edit_or_reply_message(
					context,
					text=text,
					message=update.message.message_id,
					message_type="warn",
					reply_markup=continue_menu
				)
				messages.append(message_id)

			elif c > 0.8:
				local_data["user_data"][field_name] = found_region["id"]
				message = await update.message.reply_text(f'☑️ *{found_region["name"]}*', reply_markup=continue_menu)
				messages.append(message.message_id)

			else:
				local_data["found_region"] = found_region
				title = f'{found_region["name"].upper()}, все верно?'
				await confirm_region_message(context, title)  # подтвердим что правильно найден в таблице регион

	if field_name == "main_region" and "main_region" in local_data["user_data"]:
		chat_data.pop("region_list", None)
		text = "Чем занимается компания?"
		message_id = await select_user_group_message(
			update.message,
			text=text,
			groups_only=[1, 2],
			button_type="radiobutton",
		)
		messages.append(message_id)
		local_data["user_field_name"] = "group"

	elif field_name == "group" and selected_groups:
		# TODO: постараться найти общее с кодом в регистрации и вынести в отдельную функцию
		group_name_list = REG_GROUP_KEYBOARD.copy()
		group = selected_groups[0]
		message_id = await edit_or_reply_message(
			context,
			text=f'☑️ *{group_name_list[group]}*',
			message=section["messages"][-1],
			reply_markup=continue_menu
		)
		messages.append(message_id)

		inline_markup = await generate_categories_list(
			update.message,
			context,
			groups=selected_groups,
			show_all=True,
			button_type="checkbox"
		)
		text = f'Отметьте ее сферы деятельности:'
		message = await update.message.reply_text(text, reply_markup=inline_markup)
		messages.append(message.message_id)
		local_data["user_field_name"] = "categories"

	elif field_name == "categories" and 2 in selected_groups:
		local_data["user_field_name"] = "segment"
		text = "В каком сегменте она работает?\n"
		message = await offer_to_select_segment_message(update.message, title=text)
		messages.append(message.message_id)
		text = "Если не уверены, то нажмите *Продолжить*"
		message = await update.message.reply_text(text, reply_markup=continue_menu)
		messages.append(message.message_id)

	elif field_name in ["categories", "segment"]:
		local_data["user_field_name"] = "address"
		message = await update.message.reply_text("Укажите адрес, если знаете", reply_markup=continue_menu)
		messages.append(message.message_id)

	elif field_name == "address":
		local_data["user_field_name"] = "phone"
		message = await update.message.reply_text("Укажите телефон, если знаете", reply_markup=continue_menu)
		messages.append(message.message_id)
		if not is_continue:
			local_data["user_data"][field_name] = query_message

	elif field_name == "phone":
		if not is_continue:
			local_data["user_data"][field_name] = query_message
		local_data["user_data"]["access"] = -1
		if not local_data["user_data"].get("main_region"):
			local_data["user_data"].pop("main_region", None)

		res = await fetch_user_data(endpoint='/create/', data=local_data["user_data"], method='POST')
		if res["status_code"] == 201:
			text = "После успешной проверки пользователь появится в списках.\nСпасибо за Вашу рекомендацию!"
			category_list = extract_fields(list(selected_categories.values()), field_names="name")
			categories = format_output_text("в категориях", category_list)
			await send_message_to(
				context,
				user_id=ADMIN_CHAT_ID,
				text=f'Рекомендован новый пользователь:\n{res["name"]}\nID: {res["id"]}\n{categories}',
				from_name=context.user_data["details"]["name"],
				from_username=context.user_data["details"]["username"]
			)
		else:
			text = "Произошла ошибка на сервере!"
			res.setdefault("request_body", local_data["user_data"])
			await send_error_to_admin(update.message, context, error=res, text=text)
			text += f'\nПриносим свои извинения. Будем разбираться'

		return await go_back_section(update, context, message_text=text)

	section["messages"].extend(messages)
	await delete_messages_by_key(context, "warn_message_id")

	return state


async def recommend_new_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Добавление нового пользователя для текущей группы
	query = update.callback_query
	await query.answer()

	local_data = context.chat_data.setdefault("local_data", {})
	section = await prepare_current_section(context, keep_messages=True)
	query_data = section.get("query_message") or query.data
	# TODO: [task 3]: Доработать с учетом добавления рекомендации, находясь в текущей категории
	menu_markup = back_menu
	state = MenuState.RECOMMEND_USER
	# callback = recommend_new_user_callback

	context.chat_data["region_list"], _ = await load_regions(update.message, context)
	local_data["user_field_name"] = "name"
	title = "Как называется компания, которую Вы рекомендуете?"
	message = await query.message.reply_text(text=title, reply_markup=menu_markup)

	add_section(
		context,
		state=state,
		messages=[message],
		reply_markup=menu_markup,
		query_message=query_data,
		save_full_messages=False
	)

	return state


async def confirm_user_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк подтверждения найденного региона """

	query = update.callback_query
	await query.answer()

	button_data = query.data.lstrip("choose_region_")
	local_data = context.chat_data.setdefault("local_data", {})
	found_region = local_data["found_region"]
	section = get_section(context)
	await query.message.delete()

	if button_data == 'yes':
		text = f'☑️ *{found_region["name"]}*'
	else:
		local_data["found_region"].clear()
		text = "Тогда введите другое название или нажмите *Продолжить*"

	message = await query.message.reply_text(text, reply_markup=continue_menu)
	section["messages"].append(message.message_id)


async def select_user_segment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк выбора сегмента пользователя """

	query = update.callback_query
	await query.answer()

	segment_index = int(query.data.lstrip("segment_"))
	local_data = context.chat_data.setdefault("local_data", {})
	local_data["selected_segment"] = segment_index
	await regenerate_inline_keyboard(query.message, active_value=query.data, button_type="radiobutton")

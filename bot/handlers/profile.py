from typing import Optional

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from telegram import Update
from telegram.ext import ContextTypes

from bot.constants.menus import profile_menu, back_menu, cancel_menu
from bot.constants.keyboards import (
	FAVORITES_KEYBOARD, MODIFY_KEYBOARD, CANCEL_KEYBOARD, SAVE_KEYBOARD, BACK_KEYBOARD, TARIFF_KEYBOARD
)
from bot.constants.patterns import (
	TARIFF_PATTERN, FAVOURITE_PATTERN, SETTINGS_PATTERN, SUPPORT_PATTERN, BACK_PATTERN, CANCEL_PATTERN, SAVE_PATTERN
)
from bot.constants.static import EXCLUDED_GROUP_FIELDS
from bot.handlers.common import (
	edit_or_reply_message, prepare_current_section, add_section, go_back_section, generate_users_list,
	load_favourites, load_user_field_names, generate_categories_list, load_regions, get_section, select_region,
	delete_messages_by_key, show_chat_group_links
)
from bot.handlers.details import show_user_card_message
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	generate_reply_markup, generate_inline_markup, update_inline_markup, match_query, extract_fields,
	format_output_text, fetch_user_data, list_to_dict, remove_button_from_keyboard, add_button_to_keyboard,
	is_phone_number, format_phone_number
)


async def profile_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	user = user_data["details"]
	priority_group = user_data["priority_group"]

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text

	state = MenuState.PROFILE
	keyboard = profile_menu[priority_group.value]
	menu_markup = generate_reply_markup(keyboard)
	profile_markup = generate_inline_markup(MODIFY_KEYBOARD, callback_data="profile_modify")
	title = f'{"💠 " if user["user_id"] else ""}{state}\n'
	title += f'*{user["name"].upper()}*\n'
	reply_message = await update.message.reply_text(title, reply_markup=menu_markup)
	inline_message = await show_user_card_message(context, user=user, reply_markup=profile_markup, show_all=True)

	await show_chat_group_links(update, context, hide_joined_groups=True)

	add_section(
		context,
		state=state,
		query_message=query_message,
		messages=[update.message, reply_message, inline_message],
		reply_markup=menu_markup,
	)

	return state


async def profile_sections_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Раздел выбора подразделов 'Мой профиль' """

	user_data = context.user_data
	access = user_data["details"].get("access", 0)

	chat_data = context.chat_data
	section = await prepare_current_section(context, keep_messages=True)
	query_message = section.get("query_message") or update.message.text
	callback = profile_sections_choice
	menu_markup = back_menu
	tariff = TARIFF_KEYBOARD[access]
	messages = [update.message]

	# Подраздел - ИЗБРАННОЕ
	# TODO: объединять по группам категорий [1, 2]
	if match_query(FAVOURITE_PATTERN, query_message):
		state = MenuState.FAVOURITES
		title = FAVORITES_KEYBOARD[0].upper()
		message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)

		users, error_text = await load_favourites(update.message, context)
		if not users:
			if not error_text:
				error_text = "Список избранного пуст!"
			inline_message = await update.message.reply_text(error_text, reply_markup=menu_markup)

		else:
			subtitle = "Список поставщиков:"
			inline_markup = generate_users_list(users)
			inline_message = await update.message.reply_text(subtitle, reply_markup=inline_markup)

		messages.extend([message, inline_message])

	# Подраздел - ТАРИФЫ
	elif match_query(TARIFF_PATTERN, query_message):
		state = MenuState.TARIFF_CHANGE
		inline_markup = generate_inline_markup(TARIFF_KEYBOARD, callback_data_prefix="tariff_", vertical=True)

		reply_message = await edit_or_reply_message(
			context,
			text=f'*Текущий тариф*: `{tariff.upper()}`',
			message=chat_data.get("last_message_id"),
			reply_markup=menu_markup
		)

		inline_message = await update.message.reply_text(f'Выберите тариф:', reply_markup=inline_markup)
		messages.extend([reply_message, inline_message])

	# Подраздел - НАПИСАТЬ В ПОДДЕРЖКУ
	elif match_query(SUPPORT_PATTERN, query_message):
		state = MenuState.SUPPORT
		title = str(state).upper()
		context.chat_data["local_data"] = {'message_for_admin': {"chat_id": update.effective_chat.id, "question": ""}}
		reply_message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		inline_message = await update.message.reply_text(f'Задайте свой вопрос')
		messages.extend([reply_message, inline_message])

	# Подраздел - НАСТРОЙКИ
	elif match_query(SETTINGS_PATTERN, query_message):
		# TODO: реализовать настройки пользователя
		state = MenuState.SETTINGS
		message = await update.message.reply_text(
			f'_В стадии реализации..._',
			reply_markup=menu_markup
		)
		messages.append(message)

	else:
		return await go_back_section(update, context)

	add_section(
		context,
		state,
		query_message=query_message,
		messages=messages,
		reply_markup=menu_markup,
		save_full_messages=False,
		callback=callback
	)

	return state


async def modify_user_field_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция обработки сообщений при изменения данных текущего пользователя """

	chat_data = context.chat_data
	section = get_section(context)
	if update.message:
		query_message = update.message.text
		section["messages"].append(update.message.message_id)
	else:
		query_message = ""

	state = section["state"]
	user_details = context.user_data["details"]
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	local_data = chat_data["local_data"]
	current_field: dict = local_data.get("current_field")

	field_name = current_field.get("name")
	field_title = current_field.get("title")
	field_value = query_message or current_field.get("value")

	if match_query(CANCEL_PATTERN, query_message):
		await update.message.delete()
		if isinstance(user_details[field_name], list):
			await delete_messages_by_key(context, last_message_ids.get(field_name))
			await delete_messages_by_key(context, "last_message_ids")
			local_data[f"selected_{field_name}"] = list_to_dict(user_details[field_name], "id", *["name"])

		chat_data["last_message_id"] = await edit_or_reply_message(
			context,
			text=f'Действие отменено!',
			message=chat_data.get("last_message_id"),
			delete_before_reply=True,
			message_type="info",
			reply_markup=section["reply_markup"]
		)
		current_field.clear()
		return state

	elif match_query(BACK_PATTERN, query_message):
		await delete_messages_by_key(context, "last_message_id")
		message = section["cancel_message_data"]
		await show_user_card_message(
			context,
			user=user_details,
			message_id=message["message_id"],
			reply_markup=message["inline_markup"],
			show_all=True
		)
		return await go_back_section(update, context, message_text=message["message_text"])

	elif query_message and not current_field:
		context.chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			text="Выберите из списка данные для изменения!",
			message=context.chat_data.get("warn_message_id"),
			delete_before_reply=True,
			message_type="warn",
			reply_markup=section["reply_markup"]
		)
		return state

	if field_name == "categories":
		if match_query(SAVE_PATTERN, query_message):
			await update.message.delete()
			selected_categories = chat_data["local_data"]["selected_categories"]
			field_data = list(selected_categories.keys())
			field_value = extract_fields(selected_categories.values(), field_names="name")
		else:
			context.chat_data["warn_message_id"] = await edit_or_reply_message(
				context,
				text="Выберите виды деятельности из списка или нажмите на *Сохранить*!",
				message=context.chat_data.get("warn_message_id"),
				delete_before_reply=True,
				message_type="warn",
				reply_markup=section["save_reply_markup"]
			)
			return state

	elif field_name == "main_region":
		# получим объект региона по введенному названию
		if query_message:
			found_region = await select_region(context, region_name=query_message, reply_markup=section["reply_markup"])
			if found_region:
				await add_user_region(update, context, found_region)
			else:
				return state

		field_value = "\n" + current_field.get("value")
		field_data = current_field.get("data")

	elif field_name == "regions":
		selected_regions = local_data.setdefault("selected_regions", {})

		if match_query(SAVE_PATTERN, query_message):
			await update.message.delete()
			field_data = list(selected_regions.keys())
			field_value = extract_fields(selected_regions.values(), field_names="name")

		else:
			# получим объект региона по введенному названию
			if query_message:
				found_region = await select_region(
					context,
					region_name=query_message,
					reply_markup=section["reply_markup"]
				)
				if found_region:
					await add_user_region(update, context, found_region)
				else:
					return state

			selected_region_id = current_field.get("data")
			main_region_id = user_details.get("main_region", {}).get("id")
			warning_text = None
			if selected_regions.get(selected_region_id):
				warning_text = "Регион с таким названием уже есть в Вашем списке!"
			elif selected_region_id == main_region_id:
				warning_text = "Регион с таким названием уже указан как основной!"

			if warning_text:
				context.chat_data["warn_message_id"] = await edit_or_reply_message(
					context,
					text=warning_text,
					message=context.chat_data.get("warn_message_id"),
					delete_before_reply=True,
					message_type="warn",
					reply_markup=section["save_reply_markup"]
				)
			else:
				# сохраним регион в selected_regions для выявления уже существующих регионов
				selected_regions[selected_region_id] = {"name": current_field["value"]}
				message = chat_data.get("temp_messages", {}).get("regions", None)

				regions_inline_markup = message.reply_markup if message else None
				# добавим кнопку к клавиатуре со списком регионов в temp_messages["regions"]
				reply_markup = add_button_to_keyboard(
					regions_inline_markup,
					text=f'{current_field["value"]} ✖️',
					callback_data=f'region_{current_field["data"]}'
				)

				if message:
					await message.edit_reply_markup(reply_markup)

				else:
					message = await update.message.reply_text(f'🖊 Текущие регионы:', reply_markup=reply_markup)
					last_message_ids[field_name] = message.message_id
					# сохраним чтобы можно было обновлять список текущих регионов в сообщении
					chat_data["temp_messages"] = {"regions": message}

				chat_data["last_message_id"] = await edit_or_reply_message(
					context,
					text=f'Регион *{current_field["value"]}* был добавлен!',
					message=chat_data.get("last_message_id"),
					delete_before_reply=True,
					reply_markup=section["save_reply_markup"]
				)
			return state

	elif field_name == "phone":
		if is_phone_number(query_message):
			query_message = format_phone_number(query_message)
			field_value = "\n" + query_message
			field_data = query_message

		else:
			context.chat_data["warn_message_id"] = await edit_or_reply_message(
				context,
				text="Некорректный номер телефона!",
				message=context.chat_data.get("warn_message_id"),
				delete_before_reply=True,
				message_type="warn",
				reply_markup=section["reply_markup"]
			)
			return state

	elif field_name == "email":
		try:
			validate_email(query_message)
			field_value = "\n" + field_value
			field_data = query_message

		except ValidationError:
			context.chat_data["warn_message_id"] = await edit_or_reply_message(
				context,
				text="Некорректный адрес почтового ящика!",
				message=context.chat_data.get("warn_message_id"),
				delete_before_reply=True,
				message_type="warn",
				reply_markup=section["reply_markup"]
			)
			return state

	else:  # если нужно сохранить введенный текст в строке
		field_value = "\n" + field_value
		field_data = query_message

	# обновим данные пользователя на сервере
	user_id = context.user_data["details"]["id"]
	res = await fetch_user_data(user_id=user_id, data={field_name: field_data}, method='PATCH')
	if res["data"]:
		context.user_data["details"] = res["data"]
		text = format_output_text(f'☑️ *{field_title}* _({"изменено" if field_data else "удалено"})_', field_value, tag="`")
		last_message_ids[field_name] = await edit_or_reply_message(
			context,
			text=text,
			message=last_message_ids.get(field_name),
			delete_before_reply=True,
			reply_markup=section["reply_markup"]
		)
		current_field.clear()

	else:
		context.chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			text="Ошибка сохранения нового значения!\nОбратитесь в техподдержку",
			message=context.chat_data.get("warn_message_id"),
			delete_before_reply=True,
			message_type="error",
			reply_markup=section["reply_markup"]
		)

	return state


async def add_user_region(update: Update, context: ContextTypes.DEFAULT_TYPE, new_region: dict) -> Optional[str]:
	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})

	local_data["current_field"].update({
		"value": new_region["name"],
		"data": new_region["id"]
	})
	if not update.message:
		return await modify_user_field_choice(update, context)


async def modify_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Колбэк перехода в режим изменения профиля после нажатия на инлайн кнопку карточки пользователя """

	query = update.callback_query
	await query.answer()

	fields = await load_user_field_names(update.message, context)
	priority_group = context.user_data["priority_group"]

	if not fields or priority_group == Group.UNCATEGORIZED:
		if not fields:
			text = "❗ Изменение профиля было прервано!"
		else:
			text = f'❗️ У Вас не указана сфера деятельности! Обратитесь к администратору'

		context.chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			text=text,
			message=context.chat_data.get("warn_message_id"),
			message_type="warn"
		)
		return

	query_data = query.data
	mode = query_data.lstrip("profile_")
	section = await prepare_current_section(context, keep_messages=True)
	menu_markup = generate_reply_markup(BACK_KEYBOARD)
	state = MenuState.MODIFY_PROFILE

	if mode == "cancel":
		# TODO: очистить все необходимые данные перед выходом из режима редактирования профиля
		await query.edit_message_reply_markup(section["cancel_message_data"]["inline_markup"])
		return await go_back_section(update, context, section["cancel_message_data"]["message_text"])

	profile_markup = generate_inline_markup(CANCEL_KEYBOARD, callback_data="profile_cancel")
	await query.edit_message_reply_markup(profile_markup)

	profile_fields = fields.copy()

	for field_name in EXCLUDED_GROUP_FIELDS[priority_group.value]:
		profile_fields.pop(field_name, None)

	inline_markup = generate_inline_markup(
		list(profile_fields.values()),
		callback_data=list(profile_fields.keys()),
		callback_data_prefix="modify_field_",
		vertical=True
	)

	# проверим последнее сохраненное сообщение в текущем разделе.
	# Если это id, то будем считать что это сообщение было добавлено после отмены изменения профиля и его удалим
	last_message = section["messages"][-1] if isinstance(section["messages"][-1], int) else None
	reply_message = await edit_or_reply_message(
		context,
		"Что будем изменять?",
		message=last_message,
		return_message_id=False,
		delete_before_reply=True,
		reply_markup=menu_markup
	)
	inline_message = await query.message.reply_text("Выберите данные из списка:", reply_markup=inline_markup)

	cancel_message_data = {
		"inline_markup": generate_inline_markup(MODIFY_KEYBOARD, callback_data="profile_modify"),
		"message_id": query.message.message_id,
		"message_text": "Вышли из режима редактирования!"
	}

	add_section(
		context,
		state,
		query_message=query_data,
		messages=[reply_message, inline_message],
		reply_markup=menu_markup,
		keep_messages=False,
		save_reply_markup=generate_reply_markup([SAVE_KEYBOARD]),
		cancel_message_data=cancel_message_data
		# callback=callback
	)

	return state


async def remove_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк удаления региона из спика дополнительных регионов """

	query = update.callback_query
	await query.answer()

	region_id = int(query.data.lstrip("region_"))
	section = get_section(context)
	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})

	removed_region = local_data["selected_regions"].pop(region_id, None)
	inline_markup = remove_button_from_keyboard(query.message.reply_markup, query.data)
	message = await query.message.edit_reply_markup(inline_markup)
	chat_data["temp_messages"] = {"regions": message}

	chat_data["last_message_id"] = await edit_or_reply_message(
		context,
		text=f'Регион *{removed_region["name"]}* был удален!',
		message=chat_data.get("last_message_id"),
		delete_before_reply=True,
		reply_markup=section["save_reply_markup"]
	)


async def modify_user_data_fields_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк изменения полей данных пользователя """

	query = update.callback_query
	await query.answer()

	field_name = query.data.split("modify_field_")[-1]
	section = get_section(context)
	user_details = context.user_data["details"]
	chat_data = context.chat_data
	local_data = context.chat_data.setdefault("local_data", {})
	last_message_ids = context.chat_data.setdefault("last_message_ids", {})
	inline_markup = None
	is_error = False

	fields = await load_user_field_names(update.message, context)
	title = fields.get(field_name)
	if not title:
		is_error = True
		text = "Поле недоступно для изменения!\nОбратитесь в техподдержку"

	else:
		# инициируем объект с текущим полем для изменения
		local_data["current_field"] = {"name": field_name, "title": title, "value": None}
		text = f'*{title}* _(текущее)_:'

		if field_name == "categories":
			local_data["selected_categories"] = list_to_dict(user_details["categories"], "id", *["name"])
			cat_ids = list(local_data["selected_categories"].keys())
			inline_markup = await generate_categories_list(
				update.message,
				context,
				groups=user_details["groups"],
				show_all=True,
				checked_ids=cat_ids,
				button_type="checkbox"
			)
			text = title

		elif field_name == "main_region":
			chat_data["region_list"], _ = await load_regions(query.message, context)
			if not chat_data["region_list"]:
				is_error = True
				text = "Не удалось загрузить базу регионов!\nОбратитесь в техподдержку"
			else:
				value = user_details[field_name].get("name")
				text += f'\n`{value}`' if value else "_ пусто_"

		elif field_name == "regions":
			chat_data["region_list"], _ = await load_regions(query.message, context)
			if not chat_data["region_list"]:
				is_error = True
				text = "Не удалось загрузить базу регионов!\nОбратитесь в техподдержку"

			else:
				text = ""
				if user_details["regions"]:
					text = "Текущие регионы"
					local_data["selected_regions"] = list_to_dict(user_details["regions"], "id", *["name"])
					inline_markup = generate_inline_markup(
						user_details["regions"],
						item_key="name",
						callback_data="id",
						item_prefix="✖️",
						callback_data_prefix="region_"
					)

		else:
			value = user_details[field_name]
			text += f'\n`{value}`' if value else " _пусто_"

	if not is_error:
		if text:
			message = await edit_or_reply_message(
				context,
				text=f'🖊 {text}:',
				message=last_message_ids.get(field_name),
				return_message_id=False,
				delete_before_reply=True,
				reply_markup=inline_markup
			)
			last_message_ids[field_name] = message.message_id
		else:
			message = None

		if field_name == "categories":
			chat_data["last_message_id"] = await edit_or_reply_message(
				context,
				text=f'Измените список и нажмите *Сохранить*',
				message=chat_data.get("last_message_id"),
				delete_before_reply=True,
				message_type="info",
				reply_markup=section["save_reply_markup"]
			)

		elif field_name == "regions":
			chat_data["temp_messages"] = {"regions": message}  # сохраним чтобы можно было добавить инлайн кнопку
			if not user_details["regions"]:
				text = "Введите дополнительные регионы"
			else:
				text = "Выбирайте из списка те регионы, которые нужно удалить или добавьте новые"

			chat_data["last_message_id"] = await edit_or_reply_message(
				context,
				text=text + ", а затем нажмите *Сохранить*",
				message=chat_data.get("last_message_id"),
				delete_before_reply=True,
				message_type="info",
				reply_markup=cancel_menu
			)

		else:
			chat_data["last_message_id"] = await edit_or_reply_message(
				context,
				text=f'Введите новое значение:',
				message=chat_data.get("last_message_id"),
				delete_before_reply=True,
				reply_markup=cancel_menu
			)

	else:
		context.chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			text=text,
			message=context.chat_data.get("warn_message_id"),
			delete_before_reply=True,
			message_type="error"
		)


async def choose_tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Функция изменения тарифа пользователя """
	query = update.callback_query

	await query.answer()
	button_data = int(query.data.lstrip("tariff_"))
	tariff = TARIFF_KEYBOARD[button_data]
	current_access = context.user_data["details"]["access"]

	if current_access == button_data:
		text = f'ℹ️ Тариф *{tariff.upper()}* уже используется!\nВыберите другой тариф'
	elif button_data == 0:
		text = f'✅ Выбран тариф *{tariff.upper()}*\n_Для перехода на этот тариф оплата не требуется._'
	else:
		text = f'✅ Выбран тариф *{tariff.upper()}*\n_Для перехода на этот тариф необходимо внести оплату._'

	keyboard = query.message.reply_markup.inline_keyboard
	updated_keyboard = update_inline_markup(keyboard, active_value=query.data, button_type='radiobutton')
	await query.message.edit_text(text=text, reply_markup=updated_keyboard)

	# сохраним предварительно выбранный тариф и id сообщения во временную переменную. Очищать после подтверждения
	context.chat_data["selected_tariff"] = button_data

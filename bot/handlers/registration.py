import random
from typing import Optional, Union

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from bot.bot_settings import CHANNEL_ID
from bot.constants.keyboards import SEGMENT_KEYBOARD, CANCEL_REG_KEYBOARD, CONTINUE_KEYBOARD
from bot.constants.menus import cancel_reg_menu, continue_reg_menu
from bot.constants.messages import (
	not_found_region_message, add_region_warn_message, interrupt_reg_message,
	confirm_region_message, input_regions_message,
	submit_reg_data_message, success_registration_message, offer_to_cancel_action_message,
	offer_to_select_segment_message, offer_to_input_address_message, restricted_registration_message,
	send_unknown_question_message, incorrect_socials_warn_message, continue_reg_message, repeat_input_phone_message,
	share_files_message
)
from bot.constants.patterns import DONE_PATTERN, CONTINUE_PATTERN
from bot.handlers.common import (
	send_error_to_admin, delete_messages_by_key, catch_server_error, create_registration_link,
	edit_or_reply_message, load_categories, set_priority_group, invite_user_to_chat, generate_categories_list,
	regenerate_inline_keyboard
)
from bot.logger import log
from bot.sms import SMSTransport
from bot.states.group import Group
from bot.states.registration import RegState
from bot.utils import (
	fuzzy_compare, extract_numbers, sub_years, extract_fields,
	format_output_text, fetch_user_data, format_phone_number, generate_reply_markup,
	calculate_years_of_work, match_query
)


async def generate_reg_data_report(message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
	user_details = context.user_data["details"]

	title_name = "Название организации" if 2 in context.chat_data["selected_groups"] else "Полное название"
	category_list = extract_fields(list(user_details.get("categories", {}).values()), field_names="name")
	regions: dict = user_details["regions"]
	main_region_name = regions.pop(user_details["main_region"])
	region_list = list(regions.values())
	years_of_work = calculate_years_of_work(user_details.get("work_experience", None), absolute_value=True)
	segment = SEGMENT_KEYBOARD[user_details.get("segment")] if user_details.get("segment") else ""

	await message.reply_text(
		f'*Регистрация почти завершена!*\n'
		f'_Проверьте Ваши данные и подтвердите регистрацию._\n'
		f'{format_output_text(title_name, user_details.get("name"), tag="`")}'
		f'{format_output_text("Имя пользователя", user_details.get("username"), tag="`")}'
		f'{format_output_text("Сферы деятельности", category_list, default_value="<не указано>", tag="`")}'
		f'{format_output_text("Основной регион", main_region_name, tag="`")}'
		f'{format_output_text("Другие регионы", region_list, tag="`")}'
		f'{format_output_text("Стаж работы", years_of_work, default_value="<не указано>", tag="`")}'
		f'{format_output_text("Сегмент", segment, tag="`")}'
		f'{format_output_text("Адрес", user_details.get("address"), tag="`")}'
		f'{format_output_text("Сайт или соцсеть", user_details.get("socials_url"), default_value="<не указано>", tag="`")}',
		reply_markup=ReplyKeyboardRemove()
	)


async def cancel_registration_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	message = await offer_to_cancel_action_message(update.message)
	context.chat_data["last_message_id"] = message.message_id

	return context.chat_data.get("reg_state")


async def end_registration(update: Union[Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE):
	user_data = context.user_data
	user_details = user_data.get("details")

	chat_data = context.chat_data
	current_status = chat_data.get("status")
	message_text = update.message.text
	await delete_messages_by_key(context, "last_message_id")

	error = chat_data.get("error")
	if error:
		await send_error_to_admin(update.message, context, text=error)
		await create_registration_link(update.message, context)

	if current_status == 'cancel_registration' or match_query(DONE_PATTERN, message_text):
		log.info(f'User {user_details["username"]} (ID:{user_details["user_id"]}) interrupted registration.')

		await interrupt_reg_message(update.message)

	elif current_status == "approve_registration" and (
			match_query(CONTINUE_PATTERN, message_text) or
			message_text == chat_data["verification_code"]
	):
		# сохранение данных пользователя на сервер
		token = user_data.get('token', None)
		headers = {'Authorization': 'Token {}'.format(token)} if token else None

		# TODO: Добавить сегмент для поставщиков из группы 2
		user_details.update({
			"categories": [int(category) for category in user_details["categories"].keys()],
			"main_region": int(user_details["main_region"]),
			"regions": [int(region) for region in user_details["regions"].keys()],
			"business_start_year": sub_years(int(user_details.get("work_experience", 0)))
		})
		if user_details.get("work_experience"):
			user_details["business_start_year"] = sub_years(int(user_details["work_experience"]))
		user_details.pop("work_experience", None)

		res = await fetch_user_data('/create/', headers=headers, method='POST', data=user_details)

		if res.get('status_code', None) == 201:
			log.info(f'User {user_details["username"]} (ID:{user_details["user_id"]}) has been registered.')
			chat_data["status"] = "registered"

			if user_data["priority_group"] == Group.DESIGNER and not user_details.get("socials_url"):
				user = update.effective_user if update.message else update.from_user
				log.info(f"Access restricted for user {user.full_name} (ID:{user.id}).")

				await restricted_registration_message(update.message)
				await share_files_message(
					update.message,
					"Вы можете прикрепить и отправить нам файлы сейчас или в любое удобное время."
				)

			else:
				await success_registration_message(update.message)

			await invite_user_to_chat(update, user_details["user_id"], chat_id=CHANNEL_ID)

		else:
			await catch_server_error(update.message, context, error=res)

	else:
		await update.message.reply_text(
			"Введен неверный смс код!\n"
			"Пожалуйста, повторите ввод:",
			reply_markup=cancel_reg_menu
		)
		return chat_data["reg_state"]

	chat_data.clear()

	return ConversationHandler.END


async def introduce_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	selected_groups = chat_data.get("selected_groups")

	if match_query(CONTINUE_PATTERN, update.message.text):
		if not selected_groups:
			chat_data["last_message_id"] = await edit_or_reply_message(
				context,
				text="Отметьте направления Вашей деятельности:",
				message=chat_data.get("last_message_id"),
				message_type="info",
				reply_markup=continue_reg_menu
			)

		elif 2 in selected_groups and len(selected_groups) > 1:
			chat_data["last_message_id"] = await edit_or_reply_message(
				context,
				text="Поставщик не может быть зарегистрирован одновременно с другими группами.\n",
				message=chat_data.get("last_message_id"),
				message_type="warn",
				reply_markup=continue_reg_menu
			)

		else:
			# загрузим список всех категорий для выбранных групп
			categories = await load_categories(update.message, context, groups=selected_groups, exclude_empty=False)

			if not categories:
				return RegState.DONE

			if 2 in selected_groups:
				title = "*Укажите название Вашей организации*"
			else:
				title = "*Укажите название студии или свое ФИО*"
			await update.message.reply_text(title, reply_markup=cancel_reg_menu)

			chat_data["reg_state"] = RegState.INPUT_NAME

	else:
		chat_data["last_message_id"] = await edit_or_reply_message(
			context,
			text="Отметьте направления Вашей деятельности.\n",
			message=chat_data.get("last_message_id"),
			message_type="info",
			reply_markup=continue_reg_menu
		)

	return chat_data["reg_state"]


async def name_choice(update: Union[Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	if not update.message:
		query = update.callback_query
		await query.answer()
		message_text = query.data
		user = query.from_user

	else:
		message_text = update.message.text
		user = update.effective_user
		query = update

	user_details = context.user_data["details"]
	chat_data = context.chat_data

	# TODO: [task 7]: Добавить сюда проверку близкого пересечения с username в БД, у кого нет сохраненного user_id
	if not user_details.get("name"):
		user_details["name"] = message_text
		await delete_messages_by_key(context, "last_message_id")
		await update.message.reply_text("*Придумайте свое имя пользователя*", reply_markup=cancel_reg_menu)

		# Создаем список кнопок из существующих имен Телеграм
		buttons = []
		unique_button_texts = {}
		button_names = ["first_name", "full_name", "username"]
		for button_name in button_names:
			button_text = getattr(user, button_name, None)
			if button_text:
				# Проверяем, есть ли уже кнопка с таким текстом в словаре
				if button_text not in unique_button_texts:
					# Если нет, создаем новую кнопку и добавляем ее в словарь
					button = InlineKeyboardButton(button_text, callback_data=button_name)
					unique_button_texts[button_text] = button
					buttons.append([button])

		message = await query.message.reply_text(
			"или выберите из Ваших данных:",
			reply_markup=InlineKeyboardMarkup(buttons),
		)
		chat_data["last_message_id"] = message.message_id  # Сохраним для изменения сообщения после продолжения

	elif not user_details.get("username"):
		user_details["username"] = chat_data.get("username", message_text)
		title = f'👋 Приятно познакомиться, *{user_details["username"]}!*\n'
		await edit_or_reply_message(
			context,
			text=title,
			message=chat_data.get("last_message_id"),
			reply_markup=continue_reg_menu
		)

		inline_markup = await generate_categories_list(query.message, context, button_type="checkbox")
		subtitle = f'*Теперь отметьте категории, в которых Вы представлены:*'
		message = await query.message.reply_text(subtitle, reply_markup=inline_markup)
		chat_data["last_message_id"] = message.message_id  # Сохраним для изменения сообщения после продолжения
		chat_data["reg_state"] = RegState.SELECT_CATEGORIES

	return chat_data["reg_state"]


async def categories_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data

	if match_query(CONTINUE_PATTERN, update.message.text):
		local_data = chat_data.get("local_data", {})

		if local_data.get("selected_categories", {}):
			user_details = context.user_data["details"]
			user_details["categories"] = local_data.pop("selected_categories", {})
			set_priority_group(context)

			categories = extract_fields(user_details["categories"].values(), field_names="name")
			text = format_output_text("☑️ Отмеченные категории", categories, tag="`")
			message_id = await edit_or_reply_message(context, text, message=chat_data.get("last_message_id"))
			chat_data["last_message_id"] = message_id

			await update.message.reply_text("Стаж/опыт работы?", reply_markup=continue_reg_menu)
			chat_data["reg_state"] = RegState.INPUT_WORK_EXPERIENCE

		else:
			text = "Можно только выбирать из списка!"
			await edit_or_reply_message(context, text=text, message_type="warn", lifetime=3)

	else:
		chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			text="Необходимо выбрать вариант из списка!",
			message_type="warn",
			reply_markup=continue_reg_menu
		)

	return chat_data["reg_state"]


async def work_experience_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_details = context.user_data["details"]
	chat_data = context.chat_data
	years = extract_numbers(update.message.text)[0]
	await delete_messages_by_key(context, "warn_message_id")

	if match_query(CONTINUE_PATTERN, update.message.text) or years:
		user_details["work_experience"] = years

		# выведем сообщение с вводом основного региона
		chat_data["last_message_id"] = await input_regions_message(update.message, status="main")
		user_details.setdefault("main_region", None)
		user_details.setdefault("regions", {})
		chat_data["reg_state"] = RegState.SELECT_REGIONS

	else:
		await update.message.delete()
		text = "Ответ должен обязательно содержать число!"
		await edit_or_reply_message(context, text=text, message_type="warn", lifetime=2)

	return chat_data["reg_state"]


async def regions_choice(update: Union[Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	if not update.message:
		query = update.callback_query
		await query.answer()
		update = query

	user_details = context.user_data["details"]
	chat_data = context.chat_data
	await delete_messages_by_key(context, "warn_message_id")

	if match_query(CONTINUE_PATTERN, update.message.text):
		if not user_details["regions"]:
			await edit_or_reply_message(context, 'Необходимо указать основной регион!', message_type="warn", lifetime=2)

		else:
			# await delete_messages_by_key(context, "last_message_id")
			chat_data.pop("selected_geolocation", None)
			chat_data.pop("region_list", None)
			chat_data.pop("new_region", None)

			if context.user_data["priority_group"] == Group.DESIGNER:
				title = "🌐 Укажите свой сайт/соцсеть или другой ресурс, где можно увидеть ваши проекты"
			else:
				title = "🌐 Укажите свой рабочий сайт если имеется"

			message = await update.message.reply_text(title, reply_markup=continue_reg_menu)
			context.chat_data["last_message_id"] = message.message_id
			chat_data["reg_state"] = RegState.SELECT_SOCIALS

	# если введен текст в строке с названием региона или нажата кнопка поделиться текущей геопозицией
	else:
		region_name = update.message.text
		# if region_name:
		# 	await update.message.delete()

		geolocation = context.user_data.get("geolocation")
		# если была выбрана геопозиция и ей еще не воспользовались
		if geolocation and not chat_data.get("selected_geolocation"):
			region_name = geolocation.get("region")

		if not region_name:
			return chat_data["reg_state"]

		# получим объект региона по выбранному названию региона
		found_region, c, _ = fuzzy_compare(region_name, chat_data["region_list"], "name", 0.3)
		if not found_region:
			chat_data["warn_message_id"] = await not_found_region_message(update.message, text=region_name)
			return chat_data["reg_state"]

		region_name = found_region["name"]
		# если введенное название региона близко похоже на то что есть в общем перечне, то предложим подтвердить
		if c < 0.8:
			chat_data["new_region"] = found_region
			if geolocation and not chat_data["selected_geolocation"]:
				title = "Определился регион"
			else:
				title = "Вы имели ввиду"

			title += f' *{region_name.upper()}*, все верно?'
			chat_data["last_message_id"] = await confirm_region_message(update.message, title)

		else:
			# сохраним статус разового использования геолокации
			if geolocation:
				chat_data["selected_geolocation"] = True
			await add_user_region(update, context, found_region)

	return chat_data["reg_state"]


async def add_user_region(update: [Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE, new_region: dict):
	user_details = context.user_data["details"]
	regions = user_details.setdefault("regions", {})
	chat_data = context.chat_data
	if not new_region:
		return

	region_id = new_region["id"]
	region_name = new_region["name"]
	if user_details['regions'].get(region_id):
		chat_data["warn_message_id"] = await add_region_warn_message(update.message, text=region_name.upper())
		return

	regions[region_id] = region_name  # добавим объект в список регионов пользователя
	text = f'☑️ *{region_name.upper()}* _добавлен{" как основной регион" if not user_details["main_region"] else ""}!_'
	await edit_or_reply_message(
		context,
		text=text,
		message=chat_data.get("last_message_id"),
		reply_markup=continue_reg_menu
	)

	if not user_details["main_region"]:  # если еще не добавляли основной регион
		user_details["main_region"] = region_id

		# выведем сообщение о доп регионах
		await input_regions_message(
			update.message,
			status="additional",
			reply_markup=continue_reg_menu if chat_data.get("selected_geolocation") else None
		)


async def socials_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	user_data = context.user_data
	message_text = update.message.text.lower()
	is_continue = match_query(CONTINUE_PATTERN, message_text)

	if is_continue or message_text.startswith("http"):
		if not is_continue:
			user_data["details"]["socials_url"] = message_text

		elif user_data["priority_group"] == Group.DESIGNER:
			user_data["details"]["access"] = -1

		if user_data["priority_group"] == Group.SUPPLIER:
			# выберем свой сегмент
			message = await offer_to_select_segment_message(update.message)
			chat_data["last_message_id"] = message.message_id
			chat_data["reg_state"] = RegState.SELECT_SEGMENT

		else:
			return await verify_reg_data_choice(update, context)

	else:
		await incorrect_socials_warn_message(update.message)

	return chat_data["reg_state"]


async def segment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	if not update.message:
		query = update.callback_query
		await query.answer()
		message_text = "Продолжить"
	else:
		query = update
		message_text = update.message.text

	user_details = context.user_data["details"]

	if user_details.get("segment") is None:
		text = "Необходимо выбрать сегмент!"
		await edit_or_reply_message(context, text=text, message_type="warn", lifetime=2)

	elif match_query(CONTINUE_PATTERN, message_text):
		await offer_to_input_address_message(query.message)
		context.chat_data["reg_state"] = RegState.SELECT_ADDRESS

	return context.chat_data["reg_state"]


async def address_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	message_text = update.message.text

	if not match_query(CONTINUE_PATTERN, message_text):
		context.user_data["details"]["address"] = message_text

	return await verify_reg_data_choice(update, context)


async def verify_reg_data_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	await generate_reg_data_report(update.message, context)
	await submit_reg_data_message(update.message)
	context.chat_data["reg_state"] = RegState.VERIFICATION

	return context.chat_data["reg_state"]


async def input_phone(update: [Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE) -> str:
	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	chat_data = context.chat_data
	user_data = context.user_data
	await delete_messages_by_key(context, "warn_message_id")

	if not update.message:
		inline_markup = generate_reply_markup(CANCEL_REG_KEYBOARD, share_contact=True)
		text = "Для верификации введенных данных укажите номер телефона или поделитесь контактом в Телеграм"
		chat_data["last_message_id"] = await edit_or_reply_message(
			context,
			text=text,
			message=chat_data.get("last_message_id"),
			message_type="info",
			reply_markup=inline_markup
		)

	elif not user_data["details"].get("phone"):
		contact = update.message.contact
		phone_number = contact.phone_number if contact else update.message.text
		phone = format_phone_number(phone_number)
		if contact:
			await continue_reg_message(update.message)
			chat_data["reg_state"] = RegState.SUBMIT_REGISTRATION
			return chat_data["reg_state"]

		await delete_messages_by_key(context, "last_message_id")

		if phone:
			user_data["details"]["phone"] = phone
			await update.message.delete()
			await update.message.reply_text(f'☑️ +{phone}', reply_markup=cancel_reg_menu)
			# отправим смс на указанный номер
			sms = SMSTransport()
			chat_data["verification_code"] = str(random.randint(1000, 9999))

			res = await sms.send(
				body=f'Код для подтверждения регистрации: {chat_data["verification_code"]}',
				to=phone,
			)

			if res.error:
				user = update.effective_user
				log.info(
					f'Error in sms sending occurred! Code: {res.status_code}. User: {user.full_name} (ID: {user.id})')
				user_data["details"]["access"] = -1
				message = await continue_reg_message(update.message)

			else:
				title = "Введите полученный код из смс:"
				message = await update.message.reply_text(title, reply_markup=cancel_reg_menu)
				await repeat_input_phone_message(update.message)

			chat_data["reg_state"] = RegState.SUBMIT_REGISTRATION

		else:
			message = await send_unknown_question_message(
				query.message,
				context,
				text="⚠️ Введен некорректный номер телефона! Повторите еще раз",
				reply_markup=cancel_reg_menu
			)
			user_data["details"]["phone"] = ""

		chat_data["last_message_id"] = message.message_id

	return chat_data["reg_state"]


async def update_location_in_reg_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Обработчик после нажатия на кнопку поделиться геопозицией """

	geolocation = context.user_data.get("geolocation", {})
	if geolocation.get("region"):
		return await regions_choice(update, context)

	else:
		context.chat_data["last_message_id"] = await edit_or_reply_message(
			context,
			text="Не удалось определить местоположение.\nВведите регион самостоятельно!",
			message_type="error",
			reply_markup=continue_reg_menu
		)

	return context.chat_data["reg_state"]


async def select_user_group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк выбора группы и добавления в глобальный список selected_groups """

	query = update.callback_query
	await query.answer()

	reg_group = int(query.data)
	selected_groups = context.chat_data.setdefault("selected_groups", [])
	if reg_group in selected_groups:
		selected_groups.pop(selected_groups.index(reg_group))
	else:
		selected_groups.append(reg_group)

	await regenerate_inline_keyboard(query.message, active_value=query.data, button_type="checkbox")


async def choose_telegram_username_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	context.chat_data["username"] = update.effective_user[query.data]

	return await name_choice(update, context)


async def confirm_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк подтверждения автоматически предложенного региона """

	query = update.callback_query
	await query.answer()

	button_data = query.data.lstrip("choose_region_")
	geolocation = context.user_data.get("geolocation")
	chat_data = context.chat_data

	if button_data == 'yes':
		await add_user_region(query, context, chat_data["new_region"])
		if geolocation:
			chat_data["selected_geolocation"] = True

	else:
		await query.edit_message_text("Хорошо. Тогда введите название самостоятельно.")
		if geolocation:
			context.user_data["geolocation"].clear()

	chat_data["new_region"].clear()


async def choose_segment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	segment = int(query.data.lstrip("segment_"))
	user_data = context.user_data
	user_data["details"]["segment"] = segment
	# await query.message.delete()
	await delete_messages_by_key(context, "warn_message_id")

	await query.message.edit_text(
		f'*Ваш сегмент:*\n'
		f'☑️ _{SEGMENT_KEYBOARD[segment]}_',
		reply_markup=None
	)

	return await segment_choice(update, context)


async def interrupt_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	if query.data == 'yes':
		context.chat_data["status"] = "cancel_registration"
		# await query.message.delete()
		return await end_registration(query, context)

	else:
		await query.message.edit_text("Хорошо!😌\nТогда продолжим регистрацию...")


async def approve_verification_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	context.chat_data["status"] = query.data + "_registration"
	await query.message.delete()

	if query.data == "approve":
		return await input_phone(update, context)
	else:
		return await end_registration(update, context)


async def repeat_input_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	query = update.callback_query
	await query.answer()

	context.user_data["details"]["phone"] = ""
	chat_data = context.chat_data
	text = "*Введите номер телефона*"
	chat_data["last_message_id"] = await edit_or_reply_message(context, text, message=chat_data.get("last_message_id"))
	chat_data["reg_state"] = RegState.VERIFICATION

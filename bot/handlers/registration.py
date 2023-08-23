import random
import re
from typing import Optional, Union

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, ReplyKeyboardRemove
from telegram.ext import ExtBot, ContextTypes, ConversationHandler

from bot.bot_settings import CHANNEL_ID
from bot.constants.keyboards import SEGMENT_KEYBOARD, CANCEL_REG_KEYBOARD
from bot.constants.menus import cancel_reg_menu, continue_reg_menu
from bot.constants.messages import (
	only_in_list_warn_message, show_categories_message, required_category_warn_message, confirm_region_message,
	not_found_region_message, added_new_region_message, region_selected_warn_message, interrupt_reg_message,
	not_detected_region_message, show_additional_regions_message, not_validated_warn_message,
	show_main_region_message, submit_reg_data_message, success_registration_message, offer_to_cancel_action_message,
	offer_to_select_segment_message, offer_to_input_address_message,
	required_region_warn_message, update_top_regions_message, offer_to_input_socials_message,
	incorrect_socials_warn_message, continue_reg_message, verify_by_sms_message, restricted_registration_message,
	share_files_message
)
from bot.constants.patterns import DONE_PATTERN, CONTINUE_PATTERN
from bot.handlers.common import (
	send_error_to_admin, delete_messages_by_key, catch_server_error, create_registration_link,
	edit_last_message, load_categories, set_priority_group, invite_user_to_chat
)
from bot.logger import log
from bot.sms import SMSTransport
from bot.states.group import Group
from bot.states.registration import RegState
from bot.utils import (
	find_obj_in_list, update_inline_keyboard, fuzzy_compare, extract_numbers, sub_years, extract_fields,
	format_output_text, fetch_user_data, remove_item_from_list, format_phone_number, generate_reply_keyboard,
	calculate_years_of_work, match_message_text
)


async def generate_reg_data_report(message: Message, context: ContextTypes.DEFAULT_TYPE) -> None:
	user_details = context.user_data["details"]

	title_name = "`Название организации`" if context.chat_data["reg_group"] == 1 else "`Вас зовут`"
	category_list = extract_fields(list(user_details.get("categories", {}).values()), field_names="name")
	main_region = user_details["main_region"]
	regions = user_details["regions"]
	main_region_name = regions.pop(main_region)  # необходимо перед сохранением удалить основной регион из общего списка
	region_list = list(regions.values())
	years_of_work = calculate_years_of_work(user_details.get("work_experience", None), absolute_value=True)
	segment = SEGMENT_KEYBOARD[user_details.get("segment")] if user_details.get("segment") else ""

	await message.reply_text(
		f'🏁 *Регистрация почти завершена!*\n'
		f'_Проверьте Ваши данные и подтвердите регистрацию._\n'
		f'{format_output_text(title_name, user_details.get("name"), value_tag="_")}'
		f'{format_output_text("`Имя пользователя`", user_details.get("username"), value_tag="_")}'
		f'{format_output_text("`Сферы деятельности`", category_list, default_value="<не указано>", value_tag="_")}'
		f'{format_output_text("`Основной регион`", main_region_name, value_tag="_")}'
		f'{format_output_text("`Другие регионы`", region_list, value_tag="_")}'
		f'{format_output_text("`Стаж работы`", years_of_work, default_value="<не указано>", value_tag="_")}'
		f'{format_output_text("`Сегмент`", segment, value_tag="_")}'
		f'{format_output_text("`Адрес`", user_details.get("address"), value_tag="_")}'
		f'{format_output_text("`Сайт или соцсеть`", user_details.get("socials_url"), default_value="<не указано>", value_tag="_")}',
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

	if current_status == 'cancel_registration' or match_message_text(DONE_PATTERN, message_text):
		log.info(f'User {user_details["username"]} (ID:{user_details["user_id"]}) interrupted registration.')

		await interrupt_reg_message(update.message)

	elif current_status == "approve_registration" and (
			match_message_text(CONTINUE_PATTERN, message_text) or
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

			if user_data["group"] == Group.DESIGNER and not user_details.get("socials_url"):
				user = update.from_user
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
			await catch_server_error(update.message, context, error_data=res)

	else:
		await update.message.reply_text(
			"Введен неверный смс код!\n"
			"Пожалуйста, повторите ввод:",
			reply_markup=cancel_reg_menu
		)
		return chat_data["reg_state"]

	chat_data.clear()

	return ConversationHandler.END


async def name_choice(update: Union[Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	user_data = context.user_data
	user_details = user_data["details"]

	if not update.message:
		query = update.callback_query
		await query.answer()
		message_text = query.data
		user = query.from_user

	else:
		message_text = update.message.text
		user = update.effective_user
		query = update

	# TODO: Добавить сюда проверку близкого пересечения с username в БД, у кого нет сохраненного user_id
	if not user_details.get("name"):
		user_details["name"] = message_text

		await update.message.reply_text(
			"*Укажите имя пользователя:*",
			reply_markup=cancel_reg_menu,
		)

		name_buttons = InlineKeyboardMarkup([
			[InlineKeyboardButton(user.first_name, callback_data="first_name")],
			[InlineKeyboardButton(user.full_name, callback_data="full_name")],
			[InlineKeyboardButton(user.username, callback_data="username")],
		])
		message = await query.message.reply_text(
			"Или выберите имя из предложенных вариантов:",
			reply_markup=name_buttons,
		)
		chat_data["last_message_id"] = message.message_id  # Сохраним для изменения сообщения после продолжения

	elif not user_details.get("username"):
		user_details["username"] = chat_data.get("username", message_text)
		await edit_last_message(update, context, text=f'☑️ {user_details["username"]}')

		await query.message.reply_text(
			f'Приятно познакомиться, *{user_details["username"]}!*\n'
			f'Теперь отметьте сферы деятельности и нажмите *Продолжить*',
			reply_markup=continue_reg_menu,
		)

		message = await show_categories_message(query.message, chat_data["categories"])
		chat_data["last_message_id"] = message.message_id  # Сохраним для изменения сообщения после продолжения
		chat_data["reg_state"] = RegState.SELECT_CATEGORIES

	return chat_data["reg_state"]


async def categories_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	user_data = context.user_data
	user_details = user_data["details"]

	if match_message_text(CONTINUE_PATTERN, update.message.text):
		chat_data.pop("categories", None)

		category_list = user_details.get("categories", {}).values()
		if category_list:
			set_priority_group(context)

			await show_categories_message(update.message, category_list, message_id=chat_data["last_message_id"])
			await update.message.reply_text(
				"Стаж/опыт работы?",
				reply_markup=continue_reg_menu,
			)
			chat_data["reg_state"] = RegState.INPUT_WORK_EXPERIENCE

		else:
			message = await required_category_warn_message(update.message)
			chat_data["warn_message_id"] = message.message_id

		return chat_data["reg_state"]

	else:
		message = await only_in_list_warn_message(update.message)
		chat_data["warn_message_id"] = message.message_id

	return chat_data["reg_state"]


async def work_experience_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	user_data = context.user_data
	user_details = user_data["details"]

	years = extract_numbers(update.message.text)[0]

	if match_message_text(CONTINUE_PATTERN, update.message.text) or years:
		user_details["work_experience"] = years

		message = await show_main_region_message(update.message)
		chat_data["last_message_id"] = message.message_id
		chat_data["reg_state"] = RegState.SELECT_REGIONS
	else:
		await update.message.delete()
		message = await not_validated_warn_message(update.message)
		chat_data["warn_message_id"] = message.message_id

	return chat_data["reg_state"]


async def regions_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	if not update.message:
		query = update.callback_query
		await query.answer()
		update = query

	chat_data = context.chat_data
	user_data = context.user_data

	user_details = user_data["details"]
	user_details.setdefault("main_region", None)
	user_details.setdefault("regions", {})
	await delete_messages_by_key(context, "warn_message_id")

	if match_message_text(CONTINUE_PATTERN, update.message.text):
		if not user_details["regions"]:
			message = await required_region_warn_message(update.message)
			chat_data["warn_message_id"] = message.message_id

		else:
			await delete_messages_by_key(context, "last_message_id")
			chat_data.pop("selected_regions_message", None)
			chat_data.pop("selected_location", None)
			chat_data.pop("all_regions", None)
			chat_data.pop("new_region", None)

			if user_data["group"] == Group.DESIGNER:
				await offer_to_input_socials_message(update.message)
			else:
				await offer_to_input_socials_message(
					update.message,
					text="Укажите свой сайт, если есть, или нажмите _Продолжить_:"
				)

			chat_data["reg_state"] = RegState.SELECT_SOCIALS

	else:
		location = chat_data.get("geolocation")
		if location and isinstance(location.get("region"), str):
			chat_data["selected_location"] = location

		else:
			chat_data.pop("selected_location", None)
			location = update.message.text
			await update.message.delete()

		region, c, i = fuzzy_compare(location, chat_data["all_regions"], "name", 0.5)

		if chat_data.get("selected_location") and region:
			chat_data["selected_location"] = region
			chat_data["selected_location"]["country"] = region.get("country", {})
			await confirm_region_message(update.message, f'Определился регион *{region["name"].upper()}*')
			return chat_data["reg_state"]

		elif c > 0.9:
			chat_data["new_region"] = region
			region_id = region["id"]
			if user_details['regions'].get(region_id):
				message = await region_selected_warn_message(update.message, text=region["name"].upper())
				chat_data["warn_message_id"] = message.message_id

			else:
				user_details["regions"][region_id] = region["name"]
				# удалим из топ списка регион, который совпадает с выбранным основным регионом
				remove_item_from_list(chat_data["top_regions"], "id", region_id)

			if not user_details["main_region"]:
				user_details["main_region"] = region_id
				await delete_messages_by_key(context, "last_message_id")
				await show_additional_regions_message(update.message)

			await update_top_regions_message(context)
			await added_new_region_message(update.message, region["name"])

		elif region:
			await confirm_region_message(update.message, f'Вы имели ввиду *{region["name"].upper()}*')
			chat_data["new_region"] = region

		else:
			message = await not_found_region_message(update.message, text=location)
			chat_data["warn_message_id"] = message.message_id

	return chat_data["reg_state"]


async def socials_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	user_data = context.user_data
	message_text = update.message.text
	is_continue = match_message_text(CONTINUE_PATTERN, message_text)

	if is_continue or message_text.startswith("http"):
		group = user_data["group"]
		if not is_continue:
			user_data["details"]["socials_url"] = message_text

		elif group == Group.DESIGNER:
			user_data["details"]["access"] = -1

		if group == Group.SUPPLIER:
			message = await offer_to_select_segment_message(update.message)
			chat_data["last_message_id"] = message.message_id
			chat_data["reg_state"] = RegState.SELECT_SEGMENT

		else:
			return await verify_reg_data_choice(update, context)

	else:
		await incorrect_socials_warn_message(update.message)

	return chat_data["reg_state"]


async def segment_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	user_data = context.user_data
	user_details = user_data["details"]

	if not update.message:
		query = update.callback_query
		await query.answer()
		message_text = "Продолжить"
	else:
		query = update
		message_text = update.message.text

	if not user_details.get("segment"):
		await delete_messages_by_key(context, "warn_message_id")

		text = "⚠️ Необходимо выбрать сегмент!"
		message = await not_validated_warn_message(query.message, text=text)
		chat_data["warn_message_id"] = message.message_id

	elif match_message_text(CONTINUE_PATTERN, message_text):
		await offer_to_input_address_message(query.message)
		chat_data["reg_state"] = RegState.SELECT_ADDRESS

	return chat_data["reg_state"]


async def address_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	message_text = update.message.text

	if not match_message_text(CONTINUE_PATTERN, message_text):
		context.user_data["details"]["address"] = message_text

	return await verify_reg_data_choice(update, context)


async def verify_reg_data_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data

	await generate_reg_data_report(update.message, context)
	await submit_reg_data_message(update.message)
	chat_data["reg_state"] = RegState.VERIFICATION

	return chat_data["reg_state"]


async def input_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	chat_data = context.chat_data
	user_data = context.user_data

	if not update.message:
		reply_menu = generate_reply_keyboard(CANCEL_REG_KEYBOARD, share_contact=True)
		await context.bot.send_message(
			chat_id=chat_data["chat_id"],
			text="Для верификации введенных данных укажите номер телефона или поделитесь контактом в Телеграм:",
			reply_markup=reply_menu,
		)

	elif not user_data["details"].get("phone"):
		contact = update.message.contact
		phone_number = contact.phone_number if contact else update.message.text
		phone = format_phone_number(phone_number)
		if contact:
			await continue_reg_message(update.message, text="Нажмите _Продолжить_, чтобы завершить регистрацию.")
			chat_data["reg_state"] = RegState.SUBMIT_REGISTRATION
			return chat_data["reg_state"]

		await delete_messages_by_key(context, "last_message_id")

		if phone:
			user_data["details"]["phone"] = phone
			await update.message.delete()
			await update.message.reply_text(
				f'☑️ +{phone}',
				reply_markup=cancel_reg_menu,
			)
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
				await continue_reg_message(update.message)

			else:
				message = await verify_by_sms_message(update.message)
				chat_data["last_message_id"] = message.message_id

			chat_data["reg_state"] = RegState.SUBMIT_REGISTRATION

		else:
			message = await update.message.reply_text(
				"⚠️ Введен некорректный номер телефона!\n"
				"Пожалуйста, повторите ввод:",
				reply_markup=cancel_reg_menu,
			)
			user_data["details"]["phone"] = ""
			chat_data["last_message_id"] = message.message_id

	return chat_data["reg_state"]


async def update_location_in_reg_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Обработчик после нажатия на кнопку поделиться геопозицией
	geolocation = context.chat_data.get("geolocation", None)

	if geolocation.get("region", ""):
		await regions_choice(update, context)
	else:
		await not_detected_region_message(update.message)

	return context.chat_data["reg_state"]


async def introduce_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	query = update.callback_query

	await query.answer()
	reg_group = int(query.data)
	chat_data = context.chat_data
	chat_data["reg_group"] = reg_group
	chat_data["reg_state"] = RegState.INPUT_NAME

	if reg_group == 0:
		groups = [0, 1]
		title = "*Напишите в строке Ваше имя и фамилию:*"
	else:
		groups = 2
		title = "*Напишите название Вашей организации:*"

	# загрузим список категорий для выбранной группы
	chat_data["categories"] = await load_categories(query.message, context, group=groups, related_users=None)
	if not chat_data["categories"]:
		return RegState.DONE

	await query.message.reply_text(
		text=title,
		reply_markup=cancel_reg_menu,
	)

	return chat_data["reg_state"]


async def choose_telegram_username_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	context.chat_data["username"] = update.effective_user[query.data]

	return await name_choice(update, context)


async def choose_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Обработчик нажатий на inline кнопки выбора категорий
	query = update.callback_query

	await query.answer()
	cat_id = query.data.lstrip("category_")
	user_data = context.user_data
	user_details = user_data["details"]

	chat_data = context.chat_data
	categories = chat_data.get("categories", [])

	await delete_messages_by_key(context, "warn_message_id")

	# Обновляем категории
	active_category, _ = find_obj_in_list(categories, {"id": int(cat_id)})
	if active_category:
		if user_details.setdefault("categories", {}).get(cat_id):
			del user_details["categories"][cat_id]
		else:
			user_details["categories"][cat_id] = {
				"name": active_category["name"],
				"group": active_category["group"]
			}
		keyboard = query.message.reply_markup.inline_keyboard
		updated_keyboard = update_inline_keyboard(keyboard, active_value=query.data, button_type="checkbox")
		await query.edit_message_reply_markup(updated_keyboard)

	return chat_data["reg_state"]


async def confirm_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	query = update.callback_query

	await query.answer()
	button_data = query.data.lstrip("choose_region_")
	chat_data = context.chat_data
	user_data = context.user_data
	user_details = user_data.get("details", {})

	await delete_messages_by_key(context, "warn_message_id")

	if "selected_location" in chat_data:
		if button_data == 'yes':
			chat_data["geolocation"].update({"region": chat_data["selected_location"]})
		else:
			chat_data["geolocation"] = {}

	if button_data == 'no':
		await query.edit_message_text("Хорошо.\nТогда укажите другой регион:")
		chat_data["new_region"] = None

	if button_data == 'yes':
		# если еще не добавляли основной регион, то добавим
		chat_data["new_region"]: dict = chat_data.get("selected_location", chat_data["new_region"])
		new_region: dict = chat_data["new_region"]
		region_id = new_region["id"]
		region_text = new_region["name"]

		# если мы ввели основной регион
		if not user_details["main_region"]:
			user_details["main_region"] = region_id
			region_text += " (осн)"
			await delete_messages_by_key(context, "last_message_id")  # удалим сообщение для основного региона
			await show_additional_regions_message(query.message)  # выведем сообщение о доп регионах

		if user_details['regions'].get(region_id):
			message = await region_selected_warn_message(query.message, text=new_region["name"].upper())
			chat_data["warn_message_id"] = message.message_id

			return chat_data["reg_state"]

		else:
			# добавим выбранный регион в данные пользователя
			user_details["regions"][region_id] = new_region["name"]
			# отобразим на экране выбранный регион
			await added_new_region_message(query.message, text=region_text)

		# удалим из топ списка добавленный регион и обновим сообщение
		if remove_item_from_list(chat_data["top_regions"], "id", region_id):
			await update_top_regions_message(context)

		await query.message.delete()  # удалим текущее сообщение с кнопками yes/no
	# await added_new_region_message(query.message, new_region["name"])
	return chat_data["reg_state"]


async def choose_top_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	# Обработчик нажатия на inline кнопки популярных регионов
	query = update.callback_query

	await query.answer()
	region_id = query.data.lstrip("region_")
	user_data = context.user_data
	chat_data = context.chat_data

	user_details = user_data["details"]
	top_regions = chat_data.get("top_regions", [])

	region, index = find_obj_in_list(top_regions, {"id": int(region_id)})
	if region:
		await added_new_region_message(query.message, region["name"])
		user_details['regions'][region_id] = region["name"]
		del chat_data["top_regions"][index]
		await update_top_regions_message(context)

	return chat_data["reg_state"]


async def choose_segment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	segment = int(query.data.lstrip("segment_"))
	user_data = context.user_data
	user_data["details"]["segment"] = segment
	print(user_data["details"]["segment"])
	# await query.message.delete()
	await delete_messages_by_key(context, "warn_message_id")

	await query.message.edit_text(
		f'*Выбран сегмент:*\n'
		f'☑️ _{SEGMENT_KEYBOARD[segment]}_',
		reply_markup=None
	)

	return await segment_choice(update, context)


async def interrupt_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	button_data = query.data

	if button_data == 'yes':
		context.chat_data["status"] = "cancel_registration"
		# await query.message.delete()
		return await end_registration(query, context)

	else:
		await query.message.edit_text("Отлично!\nтогда продолжим регистрацию.")


async def approve_verification_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	context.chat_data["status"] = query.data + "_registration"
	await query.message.delete()

	if query.data == "approve":
		return await input_phone(update, context)
	else:
		return await end_registration(update, context)


async def repeat_input_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	context.user_data["details"]["phone"] = ""
	await edit_last_message(query, context, text="*Введите номер телефона:*")
	context.chat_data["reg_state"] = RegState.VERIFICATION

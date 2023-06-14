from typing import Dict, Optional, Union

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, KeyboardButton, \
	ReplyKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import CallbackContext, ExtBot, ContextTypes

from api.models import Group
from bot.bot_settings import CHANNEL_ID
from bot.constants.data import categories_list
from bot.constants.keyboards import REGISTRATION_KEYBOARD, CANCEL_REG_KEYBOARD, CONFIRM_KEYBOARD
from bot.constants.menus import cancel_reg_menu, continue_reg_menu, done_reg_menu
from bot.constants.messages import only_in_list_warn_message, check_list_message, require_check_list_message
from bot.constants.regions import ALL_REGIONS
from bot.handlers.utils import check_user_in_channel
from bot.logger import log
from bot.states.registration import RegState
from bot.utils import find_obj_in_list, update_inline_keyboard, generate_inline_keyboard, get_region_by_location, \
	fuzzy_compare, filter_list


def generate_registration_info(user_data: Dict) -> str:
	group = user_data.get("group", {})
	categories = user_data.get("categories", {}).values()
	regions = user_data.get("regions", {}).values()

	if group == Group.SUPPLIER.value:
		res_info = f'Название: <b>{user_data.get("username", "")}</b>\n' + \
		           f'Категории: <b>{"/".join(categories)}</b>\n' + \
		           f'Представлены в регионах: <b>{" / ".join(regions)}</b>\n' \
		           f'Лет на рынке: <b>{user_data.get("work_experience", "")}</b>\n'
	else:
		location = user_data.get("location")
		main_region = location if isinstance(location, str) else location.get("name")

		res_info = f'Ваше имя: <b>{user_data.get("username", "")}</b>\n' + \
		           f'Специализация: <b>{" / ".join(categories)}</b>\n' + \
		           f'Стаж работы: <b>{user_data.get("work_experience", "")}</b>\n' \
		           f'Представлены в регионах: <b>{" / ".join(regions)}</b>\n' \
		           f'Основной регион: <b>{main_region}</b>\n'

	return res_info


async def supplier_group_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	if not update.message:
		query = update.callback_query
		await query.answer()
		update = query
		message_text = ""
	else:
		message_text = update.message.text

	user_data = context.user_data
	user_details = user_data["details"]
	user_data["reg_state"] = RegState.SUPPLIER_GROUP_REGISTRATION
	done_state = user_data.get("state", None)

	print("supplier details: ", user_details)

	if done_state is None:
		user_data["cats"] = filter_list(categories_list, "group", 2)
		user_data["top_regions"] = filter_list(ALL_REGIONS, "in_top", 1)
		user_data["state"] = "collect_username"

		await update.message.reply_text(
			"*Введите название организации:*",
			reply_markup=cancel_reg_menu,
		)

	elif done_state == "collect_username":
		if "username" not in user_details:
			user_details["username"] = message_text

			await update.message.reply_text(
				f'Ваше название: *{message_text.upper()}* ☑️',
				reply_markup=continue_reg_menu,
			)
			
			message = await check_list_message(update.message, user_data["cats"])
			# Сохраним для изменения сообщения после продолжения
			context.bot_data["message_id"] = message.message_id

		elif "categories" not in user_details:
			await only_in_list_warn_message(update.message)

	elif done_state == "collect_categories":
		user_data["state"] = "collect_work_experience"
		await update.message.reply_text(
			"Сколько лет работаете на рынке?",
			reply_markup=cancel_reg_menu,
		)

	elif done_state == "collect_work_experience":
		user_details["work_experience"] = update.message.text

		if 'location' not in user_details:
			user_data["state"] = "collect_regions"
			user_details["location"] = None
			location_menu = ReplyKeyboardMarkup(
				[
					[KeyboardButton("📍 Поделиться местоположением", request_location=True)],
					CANCEL_REG_KEYBOARD,
				],
				resize_keyboard=True, one_time_keyboard=False
			)

			await update.message.reply_text(
				"*Введите регионы, в которых вы представлены:*\n",
				reply_markup=location_menu,
			)

			user_details["regions"] = {}
			top_regions = user_data["top_regions"]
			top_regions_buttons = generate_inline_keyboard(
				top_regions,
				item_key="name",
				callback_data="id",
				prefix_callback_name="region_"
			) if top_regions else None

			await update.message.reply_text(
				"Поделитесь местоположением, чтобы указать текущий регион\n"
				'или выберите из предложенных вариантов:\n',
				reply_markup=top_regions_buttons,
			)

	elif done_state == "collect_regions":
		# await update.message.delete()
		region, c, i = fuzzy_compare(update.message.text, ALL_REGIONS, "name", 0.5)
		if c > 0.9:
			region_id = region["id"]
			user_details["regions"][region_id] = region["name"]
			await update.message.reply_text(
				f'*{region["name"].upper()}* ☑️\n\n',
				reply_markup=continue_reg_menu,
			)
		elif region:
			buttons = generate_inline_keyboard([CONFIRM_KEYBOARD], callback_data=["yes", "no"])
			await update.message.reply_text(
				f'❔ Вы имели ввиду *{region["name"].upper()}*?\n',
				reply_markup=buttons,
			)
			context.bot_data["new_region"] = region
			#user_details["regions"][region_id] = region["name"]
		else:
			await update.message.reply_text(
				f"⚠️ Регион с таким названием не найден!\n"
				f"Повторите ввод.\n",
				reply_markup=continue_reg_menu,
			)

	elif done_state == "done":

		await update.message.reply_text(
			f'🏁 <b>Регистрация завершена!</b>\n\n'
			f'Проверьте и подтвердите Ваши данные через смс.\n\n'
			f'{generate_registration_info(user_details)}',
			reply_markup=done_reg_menu,
			parse_mode=ParseMode.HTML
		)
		return RegState.DONE

	else:
		# Если не в режиме сбора информации, отправляем сообщение об ошибке
		await update.message.reply_text("Ошибка ввода данных.")

	return RegState.SUPPLIER_GROUP_REGISTRATION


async def service_group_questions(update: Union[Update, CallbackQuery], context: ContextTypes.DEFAULT_TYPE) -> Optional[
	str]:
	if not update.message:
		query = update.callback_query
		await query.answer()
		update = query
		message_text = query.from_user.full_name
	else:
		message_text = update.message.text

	user_data = context.user_data
	user_details = user_data["details"]
	user_data["reg_state"] = RegState.SERVICE_GROUP_REGISTRATION
	done_state = user_data.get("state", None)
	user = update.message.chat

	if done_state is None:
		user_data["cats"] = filter_list(categories_list, "group", [0, 1])
		user_data["top_regions"] = filter_list(ALL_REGIONS, "in_top", 1)
		user_data["state"] = "collect_username"
		await update.message.reply_text(
			"*Как к Вам обращаться?*",
			reply_markup=cancel_reg_menu,
		)

		name_buttons = InlineKeyboardMarkup([
			[InlineKeyboardButton(user.first_name, callback_data="first_name")],
			[InlineKeyboardButton(user.full_name, callback_data="full_name")],
			[InlineKeyboardButton(user.username, callback_data="username")],
		])
		await update.message.reply_text(
			"*Введите свое имя для обращения к Вам\n"
			"или выберите из предложенных вариантов ⬇️:",
			reply_markup=name_buttons,
		)

	elif done_state == "collect_username" and user_data["cats"]:
		# Сохраняем имя пользователя
		if "username" not in user_details:
			user_details["username"] = message_text

		if "categories" not in user_details:
			user_details["categories"] = {}
			await update.message.reply_text(
				f'Приятно познакомиться, *{user_details["username"]}*\n'
				"*Кого Вы представляете?*",
				reply_markup=continue_reg_menu,
			)
			categories_buttons = generate_inline_keyboard(
				user_data["cats"],
				item_key="name",
				callback_data="id",
				vertical=True
			)
			message = await update.message.reply_text(
				'Отметьте те категории, в которых Вы представлены:\n'
				'и нажмите *Продолжить* ⬇️\n',
				reply_markup=categories_buttons,
			)
			context.bot_data["message_id"] = message.message_id

		else:
			await only_in_list_warn_message(update.message)

	elif done_state == "collect_categories":
		user_data["state"] = "collect_work_experience"
		await update.message.reply_text(
			"Укажите стаж работы?",
			reply_markup=cancel_reg_menu,
		)

	elif done_state == "collect_work_experience":
		user_details["work_experience"] = update.message.text

		await update.message.reply_text(
			f'Лет на рынке: *{user_details["work_experience"]}* ☑️',
		)

		if 'location' not in user_details:
			user_data["state"] = "collect_location"
			user_details["location"] = None
			location_menu = ReplyKeyboardMarkup(
				[
					[KeyboardButton("📍 Поделиться местоположением", request_location=True)],
					CANCEL_REG_KEYBOARD,
				],
				resize_keyboard=True, one_time_keyboard=False
			)
			await update.message.reply_text(
				"*Укажите свой рабочий регион*\n"
				"или поделитесь своим местоположением:",
				reply_markup=location_menu,
			)

	elif done_state == "collect_location":
		# Сохраняем регион, если введен вручную
		if not user_details["location"]:
			region, c, i = fuzzy_compare(update.message.text, ALL_REGIONS, "name", 0.5)
			print("location fuzzy search:", region, c, i)

			if c > 0.9:
				user_details["location"] = region
			elif region:
				buttons = generate_inline_keyboard([CONFIRM_KEYBOARD], callback_data=["yes", "no"])
				await update.message.delete()
				# TODO: Вынести общую часть кода с вопросом yes-no в отдельную функцию
				await update.message.reply_text(
					f'❔ Вы имели ввиду *{region["name"].upper()}*?\n',
					reply_markup=buttons,
				)
				user_details["location"] = region

			else:
				# TODO: Вынести общую часть кода здесь и ниже в отдельную функцию
				await update.message.reply_text(
					f"⚠️ Регион с таким названием не найден!\n"
					f"Повторите ввод.\n",
					reply_markup=cancel_reg_menu,
				)
		else:
			context.user_data["state"] = "collect_regions"
			top_regions = user_data["top_regions"]

			if isinstance(user_details["location"], str):
				region, c, _ = fuzzy_compare(update.message.text, ALL_REGIONS, "name", 0.5)
				if region:
					user_details["location"] = region
				else:
					user_details["regions"] = {}

			if isinstance(user_details["location"], dict):
				location_id = user_details["location"]["id"]
				location_name: str = user_details["location"]["name"]
				user_details["regions"][location_id] = location_name
			else:
				location_name = user_details["location"]

			await update.message.reply_text(
				f'Рабочий регион:\n*{location_name.upper()}* ☑️',
				reply_markup=continue_reg_menu,
			)

			buttons = generate_inline_keyboard(
				top_regions,
				item_key="name",
				callback_data="id",
				prefix_callback_name="region_"
			) if top_regions else None

			await update.message.reply_text(
				'Если работаете в других регионах, то можете указать их или выбрать из списка ниже.\n'
				'После ввода нажмите *Продолжить* ⬇️\n\n',
				reply_markup=buttons,
			)

	elif done_state == "collect_regions":
		await update.message.delete()
		region, c, i = fuzzy_compare(update.message.text, ALL_REGIONS, "name", 0.5)
		if c > 0.9:
			region_id = region["id"]
			user_details["regions"][region_id] = region["name"]
			await update.message.reply_text(
				f'*{region["name"].upper()}* ☑️\n\n',
				reply_markup=continue_reg_menu,
				parse_mode=ParseMode.MARKDOWN,
			)

		elif region:
			buttons = generate_inline_keyboard([CONFIRM_KEYBOARD], callback_data=["yes", "no"])
			await update.message.reply_text(
				f'❔ Вы имели ввиду *{region["name"].upper()}*?\n',
				reply_markup=buttons,
			)
			region_id = region["id"]
			context.bot_data["region_id"] = region_id
			user_details["regions"][region_id] = region["name"]
		else:
			await update.message.reply_text(
				f"⚠️ Регион с таким названием не найден!\n"
				f"Повторите ввод.\n",
				reply_markup=continue_reg_menu,
			)

	elif done_state == "done":
		await update.message.reply_text(
			f'🏁 <b>Регистрация завершена!</b>\n\n'
			f'Проверьте и подтвердите Ваши данные через смс.\n\n'
			f'{generate_registration_info(user_details)}',
			reply_markup=done_reg_menu,
			parse_mode=ParseMode.HTML
		)
		return RegState.DONE

	else:
		# Если не в режиме сбора информации, отправляем сообщение об ошибке
		await update.message.reply_text("Ошибка ввода данных.")

	return RegState.SERVICE_GROUP_REGISTRATION


# Функция обработки сообщений после нажатия на Продолжить
async def continue_reg_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_data = context.user_data
	user_details = user_data.get("details", {})
	done_state = user_data.get("state", None)
	reg_state = user_data.get("reg_state", RegState.USER_GROUP_CHOOSING)
	print("continue click:", done_state)

	if done_state == "collect_username":
		await update.message.delete()

		cats: Dict = user_details.get("categories", {})
		if cats:
			user_data["state"] = "collect_categories"

			await context.bot.edit_message_text(
				'*Категории:*\n'
				"- " + "☑️\n- ".join(cats.values()) + " ☑️\n",
				chat_id=update.message.chat_id,
				message_id=context.bot_data["message_id"],
			)

		else:
			await require_check_list_message(update.message)
			return reg_state

	if done_state == "collect_regions":
		user_data["state"] = "done"

	if reg_state == RegState.SERVICE_GROUP_REGISTRATION:
		return await service_group_questions(update, context)
	elif reg_state == RegState.SUPPLIER_GROUP_REGISTRATION:
		return await supplier_group_questions(update, context)
	else:
		return reg_state


async def choose_username_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	user_data = context.user_data
	if "username" not in user_data["details"]:
		await query.answer()
		user_data = context.user_data
		user_details = user_data.get("details", {})
		user_details["username"] = update.effective_user[query.data]
		await query.message.edit_text(user_details["username"] + " ☑️")

	return await service_group_questions(update, context)


# Обработчик нажатий на inline кнопки выбора категорий
async def choose_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	query = update.callback_query
	await query.answer()
	button_data = query.data
	user_data = context.user_data
	user_details = user_data.get("details", {})
	reg_state = user_data.get("reg_state", RegState.USER_GROUP_CHOOSING)
	cats = user_data.get("cats", [])

	# Обновляем категории
	category, _ = find_obj_in_list(cats, "id", int(button_data))
	if category:
		selected_id = str(category["id"])
		selected_name = category["name"]
		selected_group = category["group"]
		# Сохраняем наименьший номер группы для Group. В начале сравним с большим числом
		user_details["group"] = min(selected_group, user_details.get("group", 100))
		if user_details.setdefault("categories", {}).get(selected_id):
			del user_details["categories"][selected_id]
		else:
			user_details["categories"][selected_id] = selected_name

		keyboard = query.message.reply_markup.inline_keyboard
		updated_keyboard = update_inline_keyboard(keyboard, active_value=button_data, button_type="checkbox")

		await query.edit_message_text(
			f"{query.message.text}",
			reply_markup=updated_keyboard,
		)

	return reg_state


# Обработчик нажатия на inline кнопки популярных регионов
async def choose_top_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	query = update.callback_query
	await query.answer()
	region_id = query.data.lstrip("region_")
	user_data = context.user_data
	user_details = user_data.get("details", {})
	top_regions = user_data.get("top_regions", [])
	reg_state = user_data.get("reg_state", RegState.USER_GROUP_CHOOSING)
	region, i = find_obj_in_list(top_regions, "id", region_id)

	if region:
		selected_name: str = region["name"]
		user_details["regions"][region_id] = selected_name
		del user_data["top_regions"][i]
		print(user_details["regions"], "\n", user_data["top_regions"])
		if user_data["top_regions"]:
			buttons = generate_inline_keyboard(
				user_data["top_regions"],
				item_key="name",
				callback_data="id",
				prefix_callback_name="region_"
			)
			await query.edit_message_reply_markup(buttons)

		await query.message.reply_text(
			f'*{selected_name.upper()}* ☑️\n',
			reply_markup=continue_reg_menu,
		)

	return reg_state


async def confirm_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	query = update.callback_query
	await query.answer()
	button_data = query.data
	user_data = context.user_data
	user_details = user_data.get("details", {})
	done_state = user_data.get("state", None)
	reg_state = user_data.get("reg_state", RegState.USER_GROUP_CHOOSING)
	if done_state == "collect_location":
		if button_data == 'no':
			user_details['location'] = None
			await query.edit_message_text("Укажите свой регион вручную")
		else:
			await query.message.delete()
			if reg_state == RegState.SERVICE_GROUP_REGISTRATION:
				return await service_group_questions(update, context)
			elif reg_state == RegState.SUPPLIER_GROUP_REGISTRATION:
				return await supplier_group_questions(update, context)

	if done_state == "collect_regions":
		print("collect_regions before yes no:", user_details['regions'])
		region_id: str = context.bot_data["new_region"]["id"]
		region_name: str = context.bot_data["new_region"]["name"]
		await query.delete_message()
		if button_data == 'yes':
			if user_details['regions'].get(region_id, False):
				message_text = f'*{region_name.upper()}* уже был выбран!\n'
			else:
				user_details['regions'][region_id] = region_name
				message_text = f'*{region_name.upper()}* ☑️\n\n'
		else:
			message_text = 'Введите другой регион.'

		if region_name is not None:
			await query.message.reply_text(
				message_text,
				reply_markup=continue_reg_menu,
			)

	return reg_state


async def get_location_callback(update: Update, context: CallbackContext) -> str:
	user_data = context.user_data
	user_details = user_data.get("details", {})
	reg_state = user_data["reg_state"]

	location = update.message.location
	# Локация получена
	if location is not None:
		user_details["location"] = await get_region_by_location(location.latitude, location.longitude)
		if user_details["location"]:
			log.info(f"User {update.effective_user.full_name} shared his location: {user_details['location']}")
			buttons = generate_inline_keyboard([CONFIRM_KEYBOARD], callback_data=["yes", "no"])
			await update.message.reply_text(
				f'Ваш регион *{user_details["location"].upper()}*, все верно?\n',
				reply_markup=buttons
			)
			if reg_state == RegState.SERVICE_GROUP_REGISTRATION:
				return await service_group_questions(update, context)
			elif reg_state == RegState.SUPPLIER_GROUP_REGISTRATION:
				return await supplier_group_questions(update, context)

		else:
			location = None

	if not location:
		await update.message.reply_text(
			"Не удалось определить местоположение.\n"
			"Введите регион вручную"
		)

	return reg_state


# @send_action(ChatAction.TYPING)
async def invite_user_to_channel(user: Dict, channel_id: int, bot_: ExtBot) -> bool:
	try:
		await bot_.send_chat_action(chat_id=channel_id, action=ChatAction.TYPING)
		invite_link = await bot_.export_chat_invite_link(chat_id=channel_id)

		# Проверяем, что пользователь еще не присоединен к каналу
		is_member = await check_user_in_channel(CHANNEL_ID, user["id"], bot_)
		if is_member:
			message_text = f'{user["username"]}, Вы уже присоединены к каналу!'
		else:
			message_text = f"Регистрация завершена! Присоединитесь к каналу по ссылке ниже"
			log.info(f'User {user["username"]} has been registered.')

		await bot_.send_message(
			chat_id=user["id"],
			text=message_text,
			reply_markup=InlineKeyboardMarkup([
				[InlineKeyboardButton(text='Ссылка на канал', url=invite_link, callback_data="has_joined")],
			])
		)

		# Добавляем задержку для завершения присоединения к каналу
		# await asyncio.sleep(2)

		return not is_member

	except TelegramError:
		await bot_.send_message(
			chat_id=user["id"],
			text="Регистрация завершена с ошибкой! Попробуйте пройти регистрацию заново.")
		return False


async def success_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	print("user is clicked on the link")


# Отзываем ссылку
# await revoke_invite_link(channel_id, invite_link, bot)


async def revoke_invite_link(channel_id: int, invite_link: str, bot_: ExtBot) -> None:
	await bot_.revoke_chat_invite_link(chat_id=channel_id, invite_link=invite_link)
	log.info(f"Link was revoked")


async def create_registration_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Отправляем сообщение с ссылкой для регистрации
	bot_username = context.bot.username
	invite_link = f"https://t.me/{bot_username}?start=register"
	reply_markup = InlineKeyboardMarkup(
		[[
			InlineKeyboardButton(
				REGISTRATION_KEYBOARD[0],
				url=invite_link,
				callback_data="has_joined"
			)
		]]
	)
	await update.message.reply_text("Перейдите по ссылке для регистрации", reply_markup=reply_markup)

	return invite_link


async def create_start_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Отправляем сообщение с ссылкой для начала диалога
	bot_username = context.bot.username
	context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
	invite_link = f"https://t.me/{bot_username}?start=start"
	reply_markup = InlineKeyboardMarkup(
		[[
			InlineKeyboardButton(
				"Перейти в Консьерж Сервис",
				url=invite_link
			)
		]]
	)
	await update.message.reply_text("Нажмите на кнопку для продолжения", reply_markup=reply_markup)

	return invite_link

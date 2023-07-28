import re
from typing import Optional

from telegram import Update, Message
from telegram.ext import ContextTypes

from bot.constants.common import TARIFF_LIST, PROFILE_FIELD_SET
from bot.constants.menus import profile_menu, continue_menu, back_menu
from bot.constants.patterns import TARIFF_PATTERN
from bot.handlers.common import edit_last_message, get_state_menu, delete_messages_by_key
from bot.handlers.details import user_details
from bot.states.main import MenuState
from bot.utils import generate_reply_keyboard, generate_inline_keyboard, update_inline_keyboard


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	user_group = user_data["group"].value
	keyboard = profile_menu[user_group]

	chat_data = context.chat_data
	chat_data["selected_user"] = user_data["details"]

	menu_markup = generate_reply_keyboard(keyboard)
	state = MenuState.PROFILE
	title = f'{str(state)}\n*{user_data["details"]["username"].upper()}*'
	edit_profile_markup = generate_inline_keyboard(["📝 Редактировать данные"], callback_data="edit_user_details")

	chat_data["menu"].append({
		"state": state,
		"message": None,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": edit_profile_markup
	})
	# Вывод сообщений с данными пользователя
	message = await user_details(update, context, title=title, show_all=True)
	chat_data["menu"][-1].update({
		"message": message,
		"inline_message" : chat_data.get("saved_details_message", None)
	})
	return state


async def profile_options_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Раздел выбора тарифа """
	user_data = context.user_data
	access = user_data["details"].get("access", 0)
	chat_data = context.chat_data
	message_text = update.message.text
	tariff = TARIFF_LIST[access]
	state, message, inline_message, menu_markup, _ = get_state_menu(context)

	await delete_messages_by_key(context, "saved_details_message")
	await delete_messages_by_key(context, "last_message_id")

	if re.search(TARIFF_PATTERN, message_text, re.I):
		state = MenuState.TARIFF_CHANGE
		message = await update.message.reply_text(
			f'Текущий тариф: *{tariff.upper()}*',
			reply_markup=back_menu
		)

		edit_buttons = generate_inline_keyboard(
			TARIFF_LIST,
			prefix_callback_name="tariff_",
			vertical=True
		)
		inline_message = await edit_last_message(
			update,
			context,
			text=f'Для перехода на другой тариф нажмите соответствующую кнопку',
			reply_markup=edit_buttons
		)

	chat_data["menu"].append({
		"state": state,
		"message": message,
		"inline_message": inline_message,
		"markup": back_menu,
		"inline_markup": None
	})
	chat_data["last_message_ids"] = [inline_message.message_id]

	return state


async def edit_user_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Раздел изменения данных пользователя """
	query = update.callback_query

	await query.answer()
	fields = context.bot_data.get("user_field_names")
	user_data = context.user_data
	group = user_data.get("group")

	if not fields or not group:
		await query.message.reply_text(
			f"Ошибка получения списка полей пользователя для группы {group}!",
		)
		return

	field_keys = []
	field_names = []
	for key in PROFILE_FIELD_SET[group.value]:
		value = fields.get(key)
		if value:
			field_keys.append(key)
			field_names.append(value)

	field_buttons = generate_inline_keyboard(
		[field_names],
		callback_data=[field_keys],
		prefix_callback_name="edit_field_",
		vertical=True
	)

	await edit_last_message(query, context, "Выберите поле для изменения:", field_buttons)


async def edit_details_fields_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Функция изменения полей данных пользователя """
	# После изменения надо проверить поле groups и изменить user_data["group] = max(user_data["details"]["groups"])
	query = update.callback_query

	await query.answer()
	field_name = query.data.lstrip("edit_field_")
	bot_data = context.bot_data
	fields = bot_data.get("user_field_names")

	title = fields.get(field_name)
	if title:
		await query.message.reply_text(
			f"🖊 {title}:",
		)
	# TODO: Требуется реализация логики обновления данных по каждому полю


async def choose_tariff_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Функция изменения тарифа пользователя """
	query = update.callback_query

	await query.answer()
	button_data = int(query.data.lstrip("tariff_"))
	tariff = TARIFF_LIST[button_data]
	updated_keyboard = update_inline_keyboard(
		query.message.reply_markup.inline_keyboard,
		active_value=query.data,
		# button_type='radiobutton'
	)
	current_access = context.user_data["details"]["access"]

	if current_access == button_data:
		text = f'ℹ️ Тариф *{tariff.upper()}* уже используется!\nВыберите другой тариф'
	elif button_data == 0:
		text = f'✅ Выбран тариф *{tariff.upper()}*\n_Для перехода на этот тариф оплата не требуется._'
	else:
		text = f'✅ Выбран тариф *{tariff.upper()}*\n_Для перехода на этот тариф необходимо внести оплату._'

	await query.message.edit_text(text=text, reply_markup=updated_keyboard)
	# сохраним предварительно выбранный тариф и id сообщения во временную переменную. Очищать после подтверждения
	context.chat_data["selected_tariff"] = button_data

import re
from typing import Optional

from telegram import Update, Message
from telegram.ext import ContextTypes

from bot.constants.common import TARIFF_LIST, PROFILE_FIELD_SET
from bot.constants.menus import profile_menu, continue_menu, back_menu
from bot.constants.messages import send_unknown_question_message
from bot.constants.patterns import TARIFF_PATTERN, FAVOURITE_PATTERN, SETTINGS_PATTERN
from bot.handlers.common import edit_last_message, get_menu_item, delete_messages_by_key, add_menu_item, \
	update_menu_item
from bot.handlers.details import show_user_details
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import generate_reply_keyboard, generate_inline_keyboard, update_inline_keyboard, match_message_text


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	priority_group = user_data["priority_group"].value
	keyboard = profile_menu[priority_group]

	chat_data = context.chat_data
	chat_data["selected_user"] = user_data["details"]

	menu_markup = generate_reply_keyboard(keyboard)
	state = MenuState.PROFILE
	title = f'{str(state)}\n*{user_data["details"]["username"].upper()}*'
	edit_profile_markup = generate_inline_keyboard(["📝 Редактировать данные"], callback_data="edit_user_details")

	add_menu_item(context, state, None, None, menu_markup, edit_profile_markup)

	# Вывод сообщений с данными пользователя
	message = await show_user_details(update, context, title=title, show_all=True)
	update_menu_item(context, message=message, inline_messages=chat_data.get("saved_details_message"))

	return state


async def profile_options_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Раздел выбора тарифа """
	user_data = context.user_data
	access = user_data["details"].get("access", 0)
	chat_data = context.chat_data
	message_text = update.message.text
	tariff = TARIFF_LIST[access]
	menu_markup = back_menu
	inline_message = None

	await delete_messages_by_key(context, "saved_details_message")
	await delete_messages_by_key(context, "last_message_id")

	if match_message_text(TARIFF_PATTERN, message_text):
		state = MenuState.TARIFF_CHANGE
		message = await update.message.reply_text(
			f'Текущий тариф: *{tariff.upper()}*',
			reply_markup=menu_markup
		)

		edit_buttons = generate_inline_keyboard(
			TARIFF_LIST,
			callback_data_prefix="tariff_",
			vertical=True
		)
		inline_message = await edit_last_message(
			update,
			context,
			text=f'Для перехода на другой тариф нажмите соответствующую кнопку',
			reply_markup=edit_buttons
		)
		chat_data["last_message_ids"] = [inline_message.message_id]

	elif match_message_text(FAVOURITE_PATTERN, message_text):
		# TODO: [task 6]: реализовать отображение списка Избранное с кнопками для перехода к детальной информации пользователя
		state = MenuState.FAVOURITE_CHOICE
		message = await update.message.reply_text(
			f'*{str(state).upper()}*',
			reply_markup=back_menu
		)

	elif match_message_text(SETTINGS_PATTERN, message_text):
		# реализовать личных настроек пользователя
		state = MenuState.SETTINGS
		message = await update.message.reply_text(
			f'_в стадии реализации..._',
			reply_markup=back_menu
		)

	else:
		state, message, inline_message, menu_markup, _ = get_menu_item(context)
		await send_unknown_question_message(update.message)

	add_menu_item(context, state, message, inline_message, menu_markup)

	return state


async def edit_user_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк изменения полей данных пользователя """
	query = update.callback_query

	await query.answer()
	fields = context.bot_data.get("user_field_names")
	priority_group = context.user_data["priority_group"]

	if priority_group == Group.UNCATEGORIZED:
		await query.message.reply_text(
			f'⚠️ Принадлежность к какой-либо категории не установлена! Обратитесь к администратору'
		)
		return None

	if not fields:
		await query.message.reply_text(f'⚠️ Ошибка получения списка полей пользователя для группы {priority_group}!')
		return None

	field_keys = []
	field_names = []
	# TODO: доработать отображение данных в зависимости от group
	for key in PROFILE_FIELD_SET[priority_group.value]:
		value = fields.get(key)
		if value:
			field_keys.append(key)
			field_names.append(value)

	field_buttons = generate_inline_keyboard(
		[field_names],
		callback_data=[field_keys],
		callback_data_prefix="edit_field_",
		vertical=True
	)

	await edit_last_message(query, context, "Выберите поле для изменения:", field_buttons)


async def edit_details_fields_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Функция изменения полей данных пользователя """
	# TODO: [task 5]:
	#  Требуется реализация логики обновления данных по каждому полю из списка PROFILE_FIELD_SET

	query = update.callback_query

	await query.answer()
	field_name = query.data.lstrip("edit_field_")
	bot_data = context.bot_data
	fields = bot_data.get("user_field_names")

	title = fields.get(field_name)
	if title:
		await query.message.reply_text(f"🖊 {title}:")


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

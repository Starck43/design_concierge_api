from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.constants.keyboards import FAVORITES_KEYBOARD
from bot.constants.static import TARIFF_LIST, PROFILE_FIELD_SET
from bot.constants.menus import profile_menu, back_menu
from bot.constants.patterns import TARIFF_PATTERN, FAVOURITE_PATTERN, SETTINGS_PATTERN, SUPPORT_PATTERN
from bot.handlers.common import (
	edit_or_reply_message, prepare_current_section, add_section, go_back_section, build_inline_username_buttons,
	load_favourites
)
from bot.handlers.details import show_user_card_message
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import generate_reply_markup, generate_inline_markup, update_inline_keyboard, match_query


async def profile_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:

	user_data = context.user_data
	user = user_data["details"]
	priority_group = user_data["priority_group"]

	section = await prepare_current_section(context)
	query_message = section.get("query_message") or update.message.text

	state = MenuState.PROFILE
	keyboard = profile_menu[priority_group.value]
	menu_markup = generate_reply_markup(keyboard)
	edit_profile_markup = generate_inline_markup(["📝 Изменить"], callback_data="modify_user_details")
	title = f'{"✅ " if user["user_id"] else ""}{state}\n'
	title += f'*{user["username"].upper()}*\n'
	reply_message = await update.message.reply_text(title, reply_markup=menu_markup)

	inline_message = await show_user_card_message(
		update.message,
		context,
		user=user,
		reply_markup=edit_profile_markup,
		show_all=True
	)

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
	section = await prepare_current_section(context, leave_messages=True)
	query_message = section.get("query_message") or update.message.text
	# callback = profile_sections_choice
	menu_markup = back_menu
	tariff = TARIFF_LIST[access]
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
			inline_markup = build_inline_username_buttons(users)
			inline_message = await update.message.reply_text(subtitle, reply_markup=inline_markup)

		messages.extend([message, inline_message])

	# Подраздел - ТАРИФЫ
	elif match_query(TARIFF_PATTERN, query_message):
		state = MenuState.TARIFF_CHANGE
		inline_markup = generate_inline_markup(TARIFF_LIST, callback_data_prefix="tariff_", vertical=True)

		message = await edit_or_reply_message(
			update.message,
			text=f'*Текущий тариф*: `{tariff.upper()}`',
			message_id=chat_data.get("last_message_id"),
			reply_markup=menu_markup
		)
		chat_data["last_message_id"] = message.message_id

		inline_message = await update.message.reply_text(f'Выберите тариф:', reply_markup=inline_markup)
		messages.extend([message, inline_message])

	# Подраздел - НАПИСАТЬ В ПОДДЕРЖКУ
	elif match_query(SUPPORT_PATTERN, query_message):
		state = MenuState.SUPPORT
		title = str(state).upper()
		context.chat_data["local_data"] = {'message_for_admin': {"chat_id": update.effective_chat.id, "question": ""}}
		message = await update.message.reply_text(f'*{title}*', reply_markup=menu_markup)
		inline_message = await update.message.reply_text(f'Задайте свой вопрос')
		messages.extend([message, inline_message])

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
		save_full_messages=False
		# callback=callback
	)

	return state


async def edit_user_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк изменения полей данных пользователя """
	query = update.callback_query
	await query.answer()

	fields = context.bot_data.get("user_field_names")
	priority_group = context.user_data["priority_group"]
	last_message_id = context.chat_data.get("last_message_id", None)

	if priority_group == Group.UNCATEGORIZED:
		message = await query.message.reply_text(
			f'⚠️ Принадлежность к какой-либо категории не установлена! Обратитесь к администратору'
		)
		context.chat_data["warn_message_id"] = message.message_id
		return None

	if not fields:
		message = await query.message.reply_text(f'⚠️ Ошибка получения списка полей пользователя для группы {priority_group}!')
		context.chat_data["warn_message_id"] = message.message_id
		return None

	field_keys = []
	field_names = []
	# TODO: доработать отображение данных в зависимости от group
	for key in PROFILE_FIELD_SET[priority_group.value]:
		value = fields.get(key)
		if value:
			field_keys.append(key)
			field_names.append(value)

	field_buttons = generate_inline_markup(
		[field_names],
		callback_data=[field_keys],
		callback_data_prefix="modify_user_field_",
		vertical=True
	)

	message = await edit_or_reply_message(
		query.message,
		text="Выберите поле для изменения:",
		message_id=last_message_id,
		reply_markup=field_buttons
	)
	context.chat_data["last_message_id"] = message.message_id


async def modify_user_data_fields_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Функция изменения полей данных пользователя """
	# TODO: [task 5]:
	#  Требуется реализация логики обновления данных по каждому полю из списка PROFILE_FIELD_SET

	query = update.callback_query
	await query.answer()

	field_name = query.data.lstrip("modify_user_field_")
	bot_data = context.bot_data
	fields = bot_data.get("user_field_names")
	last_message_ids = context.chat_data.setdefault("last_message_ids", {})

	title = fields.get(field_name)
	if title:
		message = await query.message.reply_text(f"🖊 {title}:")
		last_message_ids[field_name] = message.message_id


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

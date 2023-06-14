import re
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, \
	ContextTypes, CallbackContext

from bot.bot_settings import CHANNEL_ID
from bot.constants.keyboards import GROUPS_REG_KEYBOARD
from bot.constants.menus import done_menu, start_menu, cancel_reg_menu, done_reg_menu
from bot.constants.patterns import CANCEL_REGISTRATION_PATTERN, CONTINUE_REGISTRATION_PATTERN, \
	DONE_REGISTRATION_PATTERN, REGISTRATION_PATTERN
from bot.handlers.registration import invite_user_to_channel, create_start_link, \
	success_join_callback, choose_categories_callback, supplier_group_questions, service_group_questions, \
	get_location_callback, generate_registration_info, choose_username_callback, continue_reg_choice, \
	confirm_region_callback, choose_top_region_callback
from bot.handlers.utils import check_user_in_channel
from bot.logger import log
from bot.utils import generate_inline_keyboard
from bot.states.registration import RegState


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user = update.effective_user

	is_user_in_channel = await check_user_in_channel(CHANNEL_ID, user.id, context.bot)
	if not is_user_in_channel:
		await update.message.reply_text(
			'*Вы уже зарегистрированы!*\n'
			'Чтобы войти в Консьерж Сервис,\n'
			'выберите в меню команду *start*'
			'или отправьте сообщение *"start"*',
			parse_mode=ParseMode.MARKDOWN,
		)
		return ConversationHandler.END

	context.user_data["state"] = None
	context.user_data["details"] = {
		"id": user.id,
	}

	buttons = generate_inline_keyboard(
		GROUPS_REG_KEYBOARD,
		callback_data=[
			str(RegState.SERVICE_GROUP_REGISTRATION),
			str(RegState.SUPPLIER_GROUP_REGISTRATION)
		])

	await update.message.reply_text(
		"Для начала давайте познакомимся.",
		reply_markup=cancel_reg_menu,
	)

	await update.message.reply_text(
		"Кого Вы представляете?",
		reply_markup=buttons,
	)

	return RegState.USER_GROUP_CHOOSING


async def end_registration(update: Update, context: CallbackContext):
	# Присоединяем пользователя к каналу
	if not await invite_user_to_channel(context.user_data["details"], CHANNEL_ID, context.bot):
		print("save user to DB")
		# TODO: Здесь надо добавить логику для сохранения информации о зарегистрированном пользователе
		# Добавьте код для сохранения данных пользователя в базу данных
		# Например, используя Django ORM:
		# user = User(user_id=user.id, username=nickname)
		# user.save()

		await update.message.reply_text(
			f'Добро пожаловать в Консьерж Сервис для дизайнеров!\n',
			reply_markup=start_menu
		)
	else:
		await create_start_link(update, context)

	context.bot_data.clear()
	context.user_data.clear()
	return ConversationHandler.END


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	await update.message.reply_text("Регистрация прервана.", reply_markup=done_menu)
	log.info(f"User {update.effective_user.full_name} interrupted registration")
	user_data = context.user_data

	if "details" in user_data:
		del user_data["details"]

	return ConversationHandler.END


cancel_reg_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(CANCEL_REGISTRATION_PATTERN, re.IGNORECASE)),
	cancel_registration,
)

continue_reg_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(CONTINUE_REGISTRATION_PATTERN, re.IGNORECASE)),
	continue_reg_choice,
)

registration_dialog = ConversationHandler(
	entry_points=[
		CommandHandler(['register'], start_registration),
		MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(
			re.compile(REGISTRATION_PATTERN, re.IGNORECASE)
		), start_registration),
	],
	states={
		RegState.USER_GROUP_CHOOSING: [
			CallbackQueryHandler(service_group_questions, pattern=str(RegState.SERVICE_GROUP_REGISTRATION)),
			CallbackQueryHandler(supplier_group_questions, pattern=str(RegState.SUPPLIER_GROUP_REGISTRATION)),
		],
		RegState.SERVICE_GROUP_REGISTRATION: [
			continue_reg_handler,
			CallbackQueryHandler(choose_username_callback, pattern="^username|first_name|full_name$"),
			CallbackQueryHandler(choose_top_region_callback, pattern=r'^region_\d+$'),
			CallbackQueryHandler(choose_categories_callback, pattern=r'^\d+$'),
			CallbackQueryHandler(confirm_region_callback, pattern=r'^yes|no$'),
			MessageHandler(filters.LOCATION, get_location_callback),
			MessageHandler(
				filters.TEXT & ~filters.COMMAND & (
						~filters.Regex(re.compile(CANCEL_REGISTRATION_PATTERN, re.IGNORECASE))
						| filters.Regex(re.compile(CONTINUE_REGISTRATION_PATTERN, re.IGNORECASE))
				),
				service_group_questions
			),
		],
		RegState.SUPPLIER_GROUP_REGISTRATION: [
			continue_reg_handler,
			CallbackQueryHandler(choose_top_region_callback, pattern=r'^region_\d+$'),
			CallbackQueryHandler(choose_categories_callback, pattern=r'^\d+$'),
			CallbackQueryHandler(confirm_region_callback, pattern=r'^yes|no$'),
			MessageHandler(filters.LOCATION, get_location_callback),
			MessageHandler(
				filters.TEXT & ~filters.COMMAND & (
						~filters.Regex(re.compile(CANCEL_REGISTRATION_PATTERN, re.IGNORECASE))
						| filters.Regex(re.compile(CONTINUE_REGISTRATION_PATTERN, re.IGNORECASE))
				),
				supplier_group_questions
			),
		],
		RegState.DONE: [
			MessageHandler(
				filters.TEXT & ~filters.COMMAND & (
						~filters.Regex(re.compile(CANCEL_REGISTRATION_PATTERN, re.IGNORECASE))
						& filters.Regex(re.compile(DONE_REGISTRATION_PATTERN, re.IGNORECASE))
				),
				end_registration
			),
			CallbackQueryHandler(success_join_callback, pattern="has_joined"),
		],
	},
	fallbacks=[cancel_reg_handler],
)

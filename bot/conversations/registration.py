import re
from typing import Optional

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

from bot.bot_settings import CHANNEL_ID
from bot.constants.messages import (
	start_reg_message, welcome_start_message, interrupt_reg_message, yet_registered_message
)
from bot.constants.patterns import (
	CANCEL_REGISTRATION_PATTERN, CONTINUE_REGISTRATION_PATTERN, DONE_REGISTRATION_PATTERN, REGISTRATION_PATTERN
)
from bot.handlers.registration import (
	invite_user_to_channel, create_start_link, success_join_callback,
	choose_categories_callback, supplier_group_questions, service_group_questions,
	get_location_callback, choose_username_callback, continue_reg_choice,
	confirm_region_callback, choose_top_region_callback
)
from bot.logger import log
from bot.states.registration import RegState
from bot.utils import fetch_user_data


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user = update.effective_user

	#is_user_in_channel = await check_user_in_channel(CHANNEL_ID, user.id, context.bot)
	data, token = await fetch_user_data(user.id)

	if data.get('user_id'):
		await yet_registered_message(update.message)
		return ConversationHandler.END

	context.user_data["token"] = token
	context.user_data["state"] = None
	context.user_data["details"] = {"user_id": user.id}
	await start_reg_message(update.message)

	return RegState.USER_GROUP_CHOOSING


async def end_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_data = context.user_data
	user_details = user_data["details"]

	if not await invite_user_to_channel(user_details, CHANNEL_ID, context.bot):
		await welcome_start_message(update.message)

	else:
		await create_start_link(update, context)

	# сохранение данных после регистрации в БД
	token = user_data.get('token', None)
	headers = {'Authorization': 'Token {}'.format(token)} if token else None
	print('before save: ', user_details)
	# TODO: добавить поле groups = []
	user_details.update({
		"groups": [user_details.get('group')],
		"categories": list(user_details["categories"].keys()),
		"regions": list(user_details["regions"].keys()),
	})

	data, _ = await fetch_user_data('/create/', headers=headers, method='POST', data=user_details)
	print('after save: ', data)

	if data.get('status_code') == 201:
		context.bot_data.clear()
		del context.user_data["state"]
		return ConversationHandler.END

	return RegState.DONE


async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	log.info(f"User {update.effective_user.full_name} interrupted registration")

	await interrupt_reg_message(update.message)

	context.bot_data.clear()
	context.user_data.clear()

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

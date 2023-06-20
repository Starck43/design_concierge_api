import re
from typing import Optional

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

from bot.bot_settings import CHANNEL_ID
from bot.constants.messages import (
	start_reg_message, welcome_start_message, interrupt_reg_message, yet_registered_message, show_done_reg_message,
	server_error_message
)
from bot.constants.patterns import (
	CANCEL_REGISTRATION_PATTERN, CONTINUE_REGISTRATION_PATTERN, DONE_REGISTRATION_PATTERN, REGISTRATION_PATTERN
)
from bot.handlers.done import send_error_message_callback
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
	user_data = context.user_data

	# is_user_in_channel = await check_user_in_channel(CHANNEL_ID, user.id, context.bot)
	res = await fetch_user_data(user.id)
	data = res.get('data', None)
	status_code = res.get('status_code', 500)

	if status_code == 200 and data.get('user_id'):
		await yet_registered_message(update.message)
		return ConversationHandler.END

	if status_code != 404:
		await server_error_message(update.message, context, error_data=res)
		return RegState.DONE

	user_data["token"] = res.get("token", None)
	user_data["state"] = None
	user_data["details"] = {"user_id": user.id}
	await start_reg_message(update.message)

	return RegState.USER_GROUP_CHOOSING


async def end_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_data = context.user_data
	user_details = user_data["details"]

	if "error" not in user_data:
		# сохранение данных после регистрации в БД
		token = user_data.get('token', None)
		headers = {'Authorization': 'Token {}'.format(token)} if token else None
		print('before save: ', user_details)
		# TODO: добавить поле groups = []
		user_details.update({
			"group": max(user_details.get("groups", []), default=-1),
			"categories": list(user_details["categories"].keys()),
			"regions": list(user_details["regions"].keys()),
		})

		res = await fetch_user_data('/create/', headers=headers, method='POST', data=user_details)
		data = res.get("data", None)
		print('after save: ', data)

		if res.get('status_code', None) == 201:
			await show_done_reg_message(update.message)
			if not await invite_user_to_channel(user_details, CHANNEL_ID, context.bot):
				await welcome_start_message(update.message)

			else:
				await create_start_link(update, context)

		else:
			await server_error_message(update.message, context, error_data=res)

	context.bot_data.clear()
	del user_data["state"]
	user_data.pop("error", None)
	return ConversationHandler.END


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
			CallbackQueryHandler(service_group_questions, pattern=str(RegState.SERVICE_GROUP)),
			CallbackQueryHandler(supplier_group_questions, pattern=str(RegState.SUPPLIER_GROUP)),
		],
		RegState.SERVICE_GROUP: [
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
		RegState.SUPPLIER_GROUP: [
			continue_reg_handler,
			CallbackQueryHandler(choose_top_region_callback, pattern=r'^region_\d+$'),
			CallbackQueryHandler(choose_categories_callback, pattern=r'^category_\d+$'),
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
			CallbackQueryHandler(send_error_message_callback, pattern='error'),
		],
	},
	fallbacks=[cancel_reg_handler],
)

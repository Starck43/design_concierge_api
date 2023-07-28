import re
from typing import Optional

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

from bot.constants.messages import introduce_reg_message, yet_registered_message
from bot.constants.patterns import (CANCEL_PATTERN, REGISTRATION_PATTERN, DONE_PATTERN)
from bot.handlers.common import catch_server_error, load_user_field_names, load_regions
from bot.handlers.registration import (
	choose_categories_callback, choose_telegram_username_callback,
	confirm_region_callback, choose_top_region_callback,
	interrupt_registration_callback, approve_verification_code_callback, end_registration,
	cancel_registration_choice, introduce_callback, name_choice, work_experience_choice, categories_choice,
	regions_choice, choose_segment_callback, segment_choice, socials_choice, address_choice,
	input_phone, repeat_input_phone_callback
)
from bot.logger import log
from bot.states.registration import RegState
from bot.utils import fetch_user_data


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user = update.effective_user

	data = await load_user_field_names(update.message, context)
	if not data:
		return RegState.DONE

	context.bot_data.setdefault("user_field_names", data)
	chat_data = context.chat_data
	user_data = context.user_data

	# сохраним весь список регионов и список популярных регионов
	chat_data["all_regions"], chat_data["top_regions"] = await load_regions(update.message, context)
	if not chat_data["all_regions"]:
		return RegState.DONE

	res = await fetch_user_data(params={"user_id": user.id})
	status_code = res.get('status_code', 500)

	if status_code == 200 and res["data"].get('user_id'):
		user_data["details"] = res["data"]
		await yet_registered_message(update.message)
		return ConversationHandler.END

	if status_code != 404:
		await catch_server_error(update.message, context, error_data=res)
		return RegState.DONE

	log.info(f'User {user.full_name} (ID:{user.id}) started registration.')
	await introduce_reg_message(update.message)

	user_data["token"] = res.get("token", None)
	user_data["details"] = {"user_id": user.id}
	chat_data["status"] = "registration"
	chat_data["chat_id"] = update.effective_chat.id

	return RegState.SELECT_USER_GROUP


cancel_reg_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(CANCEL_PATTERN, re.I)),
	cancel_registration_choice,
)

registration_dialog = ConversationHandler(
	entry_points=[
		CommandHandler('register', start_registration),
		MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(
			re.compile(REGISTRATION_PATTERN, re.I)
		), start_registration),
	],
	states={
		RegState.SELECT_USER_GROUP: [
			CallbackQueryHandler(introduce_callback, pattern=r"^0|1$"),
		],
		RegState.INPUT_NAME: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				name_choice
			),
			CallbackQueryHandler(choose_telegram_username_callback, pattern="^username|first_name|full_name$"),
		],
		RegState.SELECT_CATEGORIES: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				categories_choice
			),
			CallbackQueryHandler(choose_categories_callback, pattern=r'^category_\d+$'),
		],
		RegState.INPUT_WORK_EXPERIENCE: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				work_experience_choice
			),
		],
		RegState.SELECT_REGIONS: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				regions_choice
			),
			CallbackQueryHandler(confirm_region_callback, pattern=r'^choose_region_(yes|no)$'),
			CallbackQueryHandler(choose_top_region_callback, pattern=r'^region_\d+$'),
		],
		RegState.SELECT_SEGMENT: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				segment_choice
			),
			CallbackQueryHandler(choose_segment_callback, pattern=r'^segment_\d+$'),
		],
		RegState.SELECT_SOCIALS: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				socials_choice
			),
		],
		RegState.SELECT_ADDRESS: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				address_choice
			),
		],
		RegState.VERIFICATION: [
			MessageHandler(
				filters.CONTACT |
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				input_phone
			),
			CallbackQueryHandler(approve_verification_code_callback, pattern=r'^approve|cancel'),
			CallbackQueryHandler(repeat_input_phone_callback, pattern=r'^input_phone$'),
		],
		RegState.SUBMIT_REGISTRATION: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				end_registration
			),
		],
		RegState.DONE: [
			MessageHandler(
				filters.TEXT & ~filters.COMMAND & (
						filters.Regex(re.compile(CANCEL_PATTERN, re.I))
						| filters.Regex(re.compile(DONE_PATTERN, re.I))
				),
				end_registration
			),
		],
	},
	fallbacks=[
		CallbackQueryHandler(interrupt_registration_callback),
		cancel_reg_handler,
	],
)

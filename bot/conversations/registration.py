import re
from functools import partial
from typing import Union

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes
)

from bot.constants.menus import continue_menu
from bot.constants.messages import yet_registered_message, select_user_group_message
from bot.constants.patterns import (CANCEL_PATTERN, REGISTRATION_PATTERN, DONE_PATTERN)
from bot.handlers.common import (
	catch_critical_error, load_user_field_names, load_regions, select_user_categories_callback,
	select_user_group_callback, confirm_region_callback, post_user_log_data
)
from bot.handlers.registration import (
	end_registration, name_choice, regions_choice, socials_choice, segment_choice, address_choice, categories_choice,
	work_experience_choice, cancel_registration_choice, introduce_choice, add_user_region, input_phone,
	choose_segment_callback, choose_user_name_callback, approve_verification_code_callback,
	repeat_input_phone_callback, interrupt_registration_callback
)
from bot.logger import log
from bot.states.registration import RegState
from bot.utils import fetch_user_data


async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Union[str, int]:
	user = update.effective_user

	data = await load_user_field_names(update.message, context)
	if not data:
		return RegState.DONE

	chat_data = context.chat_data
	user_data = context.user_data

	# сохраним весь список регионов
	chat_data["region_list"], _ = await load_regions(update.message, context)
	if not chat_data["region_list"]:
		return RegState.DONE

	res = await fetch_user_data(params={"user_id": user.id})
	status_code = res.get("status_code", 500)

	if status_code == 200 and res["data"].get('user_id'):
		user_data["details"] = res["data"]
		await yet_registered_message(update.message)
		return ConversationHandler.END

	if status_code != 404:
		text = "Ошибка чтения данных пользователя."
		await catch_critical_error(update.message, context, error=res, text=text)
		return RegState.DONE

	user_data["token"] = res.get("token", None)
	chat_data["chat_id"] = update.effective_chat.id
	user_data["details"] = {"user_id": user.id}
	chat_data["status"] = "registration"
	message = f'User {user.full_name} (ID:{user.id}) started registration'
	log.info(message)
	await post_user_log_data(context, status_code=3, message=message)

	################################ TESTING #################################
	# chat_data["reg_state"] = RegState.SELECT_REGIONS
	# user_details = context.user_data["details"]
	# user_details.setdefault("main_region", None)
	# user_details.setdefault("regions", {})
	# chat_data["last_message_id"] = await verify_reg_data_choice(update, context)
	# user_details["groups"] = [1, 2]
	# set_priority_group(context)
	#
	# return chat_data["reg_state"]
	################################ TESTING #################################

	await update.message.reply_text(
		"🤝 Для начала давайте познакомимся.",
		reply_markup=continue_menu,
	)
	chat_data["last_message_id"] = await select_user_group_message(update.message)
	chat_data["reg_state"] = RegState.SELECT_USER_GROUP
	return chat_data["reg_state"]


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
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				introduce_choice
			),
			CallbackQueryHandler(select_user_group_callback, pattern=r"^0|1|2$"),
		],
		RegState.INPUT_NAME: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				name_choice
			),
			CallbackQueryHandler(choose_user_name_callback, pattern="^first_name|full_name$"),
		],
		RegState.SELECT_CATEGORIES: [
			MessageHandler(
				filters.TEXT & ~filters.Regex(re.compile(CANCEL_PATTERN, re.I)) & ~filters.COMMAND,
				categories_choice
			),
			CallbackQueryHandler(select_user_categories_callback, pattern=r"^category_\d+$"),
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
			CallbackQueryHandler(
				partial(confirm_region_callback, add_region_func=add_user_region),
				pattern=r'^choose_region_(yes|no)$'
			),
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

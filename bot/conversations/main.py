import re
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, filters, CallbackQueryHandler, ContextTypes
)

from bot.constants.menus import main_menu
from bot.constants.messages import denied_access_message, share_files_message
from bot.constants.patterns import (
	DONE_PATTERN, PROFILE_PATTERN, BACK_PATTERN, SERVICES_PATTERN,
	COOPERATION_REQUESTS_PATTERN, START_PATTERN, DESIGNER_PATTERN, USER_DETAILS_PATTERN, TARIFF_PATTERN,
	SUPPLIERS_SEARCH_PATTERN
)
from bot.handlers.common import (
	go_back, init_start_menu, user_authorization, load_rating_questions, load_user_field_names, set_priority_group
)
from bot.handlers.cooperation import cooperation_requests, fetch_supplier_requests
from bot.handlers.designers import (
	main_menu_choice, select_suppliers_in_cat_callback, select_user_details_callback, user_details_choice,
	select_events_callback, select_sandbox_callback, place_designer_order_callback, select_supplier_segment_callback,
	save_supplier_rating_callback, select_outsourcers_in_cat_callback, suppliers_search_choice
)
from bot.handlers.done import done
from bot.handlers.profile import (
	profile, edit_user_details_callback, edit_details_fields_callback, profile_options_choice, choose_tariff_callback
)
from bot.handlers.questionnaire import set_user_rating_callback
from bot.handlers.services import fetch_supplier_services, services_menu
from bot.handlers.upload import upload_files_callback, share_files_callback, share_files
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import determine_greeting, generate_inline_keyboard


async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	"""Начало диалога по команде /start или сообщении start"""

	# is_user_in_channel = await check_user_in_channel(CHANNEL_ID, user.id, context.bot)
	# Проверим, зарегистрирован ли пользователь
	has_authorized = await user_authorization(update, context)
	if has_authorized is None:
		return MenuState.DONE
	elif not has_authorized:
		return ConversationHandler.END

	user = update.effective_user
	context.bot_data.setdefault("rating_questions", await load_rating_questions(update.message, context))
	context.bot_data.setdefault("user_field_names", await load_user_field_names(update.message, context))
	user_data = context.user_data
	user_has_rating = user_data["details"].get("has_given_rating")

	chat_data = context.chat_data
	chat_data["chat_id"] = update.effective_chat.id
	restricted_title = None

	group = set_priority_group(context)

	if user_data["details"].get("access", -2) == -2:
		log.info(f"Access denied for user {user.full_name} (ID:{user.id}).")
		await denied_access_message(update.message)
		return MenuState.DONE

	# если пользователь первый раз начал диалог
	if chat_data.get("status") != "dialog":
		chat_data["status"] = "dialog"
		log.info(f"User {user.full_name} (ID:{user.id}) started conversation.")

		hour = datetime.now().time().hour
		greeting = determine_greeting(hour)

		reply_text = f'{greeting}, {user.first_name}\n'
		await update.message.reply_text(reply_text)

		if user_data["group"] == Group.DESIGNER and user_data["details"].get("access", -2) == -1:
			restricted_title = "⚠️ Доступ к Консьерж для дизайнера временно ограничен\\!\n"

		# если пользователь не поставщик и не выставлял вообще рейтинг ни разу, то вывести приглашение об анкетировании
		if not user_has_rating and user_data["group"] in [Group.DESIGNER, Group.OUTSOURCER]:
			reply_markup = generate_inline_keyboard(
				["Перейти к анкетированию"],
				callback_data="questionnaire"
			)
			context.chat_data["saved_message"] = await update.message.reply_text(
				"Для составления рейтинга поставщиков рекомендуем пройти анкетирование.",
				reply_markup=reply_markup
			)

	menu = await init_start_menu(context, text=restricted_title, menu_markup=main_menu[group])

	if restricted_title:
		await share_files_message(
			update.message,
			"Прикрепите файлы для подтверждения Вас как дизайнера или архитектора"
		)

	return menu["state"]


done_handler = MessageHandler(
	filters.TEXT & filters.Regex(re.compile(DONE_PATTERN, re.I)),
	done
)

back_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(BACK_PATTERN, re.I)),
	go_back
)

main_menu_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(DESIGNER_PATTERN, re.I)),
	main_menu_choice
)

user_details_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(USER_DETAILS_PATTERN, re.I)),
	user_details_choice
)

suppliers_search_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(SUPPLIERS_SEARCH_PATTERN, re.I)),
	suppliers_search_choice
)

profile_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(PROFILE_PATTERN, re.I)),
	profile
)

services_menu_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(SERVICES_PATTERN, re.I)),
	services_menu
)

cooperation_requests_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(COOPERATION_REQUESTS_PATTERN, re.I)),
	cooperation_requests
)

user_profile_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(TARIFF_PATTERN, re.I)),
	profile_options_choice
)

main_dialog = ConversationHandler(
	allow_reentry=True,
	entry_points=[
		CommandHandler('start', start_conversation),
		MessageHandler(
			filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(START_PATTERN, re.I)),
			start_conversation
		),
	],
	states={
		MenuState.START: [
			done_handler,
			main_menu_handler,
			services_menu_handler,
			cooperation_requests_handler,
			profile_handler,
		],
		MenuState.SUPPLIERS_REGISTER: [
			suppliers_search_handler,
			CallbackQueryHandler(select_suppliers_in_cat_callback, pattern=r"^category_\d+$"),
			CallbackQueryHandler(select_user_details_callback, pattern=r"^user_\d+$"),
		],
		MenuState.OUTSOURCER_SERVICES: [
			CallbackQueryHandler(select_outsourcers_in_cat_callback, pattern=r"^category_\d+$"),
			CallbackQueryHandler(select_user_details_callback, pattern=r"^user_\d+$"),
			CallbackQueryHandler(place_designer_order_callback, pattern=r"^place_order$"),
		],
		MenuState.USER_DETAILS: [
			user_details_handler,
			CallbackQueryHandler(save_supplier_rating_callback, pattern=r"^save_rating"),
			CallbackQueryHandler(set_user_rating_callback, pattern=r"^rate"),
		],
		MenuState.DESIGNER_EVENTS: [
			CallbackQueryHandler(select_events_callback, pattern=r"^event_type_\d+$"),
		],
		MenuState.DESIGNER_SANDBOX: [
			CallbackQueryHandler(select_sandbox_callback, pattern=r"^sandbox_type_\d+$"),
		],
		MenuState.PROFILE: [
			CallbackQueryHandler(edit_user_details_callback, pattern=r"^edit_user_details"),
			CallbackQueryHandler(edit_details_fields_callback, pattern=r"^edit_field_"),
			CallbackQueryHandler(select_supplier_segment_callback, pattern=r'^segment_\d+$'),
			user_profile_handler
		],
		MenuState.TARIFF_CHANGE: [
			CallbackQueryHandler(choose_tariff_callback, pattern=r"^tariff_"),
		],
		MenuState.SERVICES: [
			CallbackQueryHandler(fetch_supplier_services),
		],
		MenuState.COOP_REQUESTS: [
			CallbackQueryHandler(fetch_supplier_requests),
		],
		MenuState.DONE: [
			done_handler,
		],
	},
	fallbacks=[
		back_handler,
		MessageHandler(filters.PHOTO, share_files),
		MessageHandler(filters.ATTACHMENT, share_files),
		CallbackQueryHandler(upload_files_callback, pattern=r"^upload_files$"),
		CallbackQueryHandler(share_files_callback, pattern=r"^share_files$"),
	]
)

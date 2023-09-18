import re
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, filters, CallbackQueryHandler, ContextTypes
)

from bot.bot_settings import CHANNEL_ID
from bot.constants.menus import main_menu, start_menu
from bot.constants.messages import denied_access_message, share_files_message
from bot.constants.patterns import (
	START_PATTERN, DONE_PATTERN, BACK_PATTERN, PROFILE_PATTERN, USER_PROFILE_PATTERN, COOPERATION_REQUESTS_PATTERN,
	DESIGNER_PATTERN, USER_DETAILS_PATTERN, SUPPLIERS_SEARCH_PATTERN, SERVICES_PATTERN, DONE_ORDERS_PATTERN
)
from bot.handlers.common import (
	go_back, init_start_menu, user_authorization, load_rating_questions, load_user_field_names, set_priority_group,
	invite_user_to_chat, is_user_chat_member
)
from bot.handlers.cooperation import cooperation_requests, coop_request_message_callback
from bot.handlers.details import show_authors_for_user_rating_callback
from bot.handlers.done import done
from bot.handlers.main import (
	main_menu_choice, select_suppliers_in_cat_callback, show_user_details_callback, user_details_choice,
	select_events_callback, select_sandbox_callback, place_designer_order_callback, select_supplier_segment_callback,
	save_supplier_rating_callback, select_outsourcers_in_cat_callback, suppliers_search_choice,
	recommend_new_user_callback, orders_group_choice, show_order_details_callback,
	select_order_executor_callback, respond_designer_order_callback, change_order_status_callback,
	designer_orders_group_choice
)
from bot.handlers.profile import (
	profile, edit_user_details_callback, edit_details_fields_callback, profile_options_choice, choose_tariff_callback
)
from bot.handlers.questionnaire import set_user_rating_callback
from bot.handlers.upload import upload_files_callback, share_files_callback, share_files
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import determine_greeting, generate_inline_keyboard


async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	"""Начало диалога по команде /start или сообщении start"""

	# Проверим, зарегистрирован ли пользователь
	has_authorized = await user_authorization(update, context)
	if has_authorized is None:
		return MenuState.DONE
	elif not has_authorized:
		return ConversationHandler.END

	user = update.effective_user
	user_data = context.user_data
	context.bot_data.setdefault("rating_questions", await load_rating_questions(update.message, context))
	context.bot_data.setdefault("user_field_names", await load_user_field_names(update.message, context))
	user_has_rating = user_data["details"].get("has_given_rating")

	chat_data = context.chat_data
	chat_data["chat_id"] = update.effective_chat.id
	message_text = None
	is_channel_member = await is_user_chat_member(context.bot, user_id=user.id, chat_id=CHANNEL_ID)

	group = set_priority_group(context)

	if user_data["details"].get("access", -2) == -2:
		log.info(f"Access denied for user {user.full_name} (ID:{user.id}).")
		await denied_access_message(update.message)
		return MenuState.DONE

	# если пользователь первый раз начал диалог
	if chat_data.get("status") != "dialog":
		chat_data["status"] = "dialog"

		hour = datetime.now().time().hour
		greeting = determine_greeting(hour)

		await update.message.reply_text(
			f'{greeting}, {user.first_name}\n'
			f'Добро пожаловать в Консьерж Сервис!\n',
			reply_markup=None if is_channel_member else start_menu
		)

		if user_data["details"].get("access", -2) == -1:
			message_text = "⚠️ Доступ к Консьерж Сервис временно ограничен\\!\n"

		# если пользователь не поставщик и не выставлял вообще рейтинг ни разу, то вывести приглашение об анкетировании
		if not user_has_rating and user_data["priority_group"] in [Group.DESIGNER, Group.OUTSOURCER]:
			questionnaire_button = generate_inline_keyboard(
				["Перейти к анкетированию"],
				callback_data="questionnaire"
			)
			context.chat_data["saved_message"] = await update.message.reply_text(
				"Для составления рейтинга поставщиков рекомендуем пройти анкетирование.",
				reply_markup=questionnaire_button
			)

	if not is_channel_member:
		is_joined = await invite_user_to_chat(
			update,
			text='❗️Прежде чем войти в Консьерж Сервис,\nВы должны присоединиться к нашему каналу',
			user_id=user.id,
			chat_id=CHANNEL_ID,
		)
		if not is_joined:
			return ConversationHandler.END

	log.info(f"User {user.full_name} (ID:{user.id}) started conversation.")
	menu = await init_start_menu(context, text=message_text, menu_markup=main_menu[group])

	if message_text:
		await share_files_message(
			update.message,
			"❗️_Для получения полного доступа к функционалу "
			"не забудьте приложить сюда любые документы "
			"для подтверждения Вас как дизайнера или архитектора_"
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

orders_group_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(SERVICES_PATTERN, re.I)),
	orders_group_choice
)

designer_orders_group_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(DONE_ORDERS_PATTERN, re.I)),
	designer_orders_group_choice
)

suppliers_search_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(SUPPLIERS_SEARCH_PATTERN, re.I)),
	suppliers_search_choice
)

profile_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(PROFILE_PATTERN, re.I)),
	profile
)

cooperation_requests_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(COOPERATION_REQUESTS_PATTERN, re.I)),
	cooperation_requests
)

profile_options_choice_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(USER_PROFILE_PATTERN, re.I)),
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
			# cooperation_requests_handler, # в стадии будущего обсуждения
			profile_handler,
		],
		MenuState.SUPPLIERS_REGISTER: [
			suppliers_search_handler,
			CallbackQueryHandler(select_suppliers_in_cat_callback, pattern=r"^category_\d+$"),
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
			CallbackQueryHandler(recommend_new_user_callback, pattern=r"^add_new_user_\d+$"),
			CallbackQueryHandler(place_designer_order_callback, pattern=r"^place_order$"),
		],
		MenuState.SERVICES: [
			# TODO: [task 1, task 3]
			orders_group_handler,
			CallbackQueryHandler(select_outsourcers_in_cat_callback, pattern=r"^category_\d+$"),
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
			CallbackQueryHandler(recommend_new_user_callback, pattern=r"^add_new_user_\d+$"),
			CallbackQueryHandler(place_designer_order_callback, pattern=r"^place_order$"),
			CallbackQueryHandler(respond_designer_order_callback, pattern=r"^respond_order_\d+$"),
		],
		MenuState.ORDERS: [
			# TODO: [task 1]
			designer_orders_group_handler,
			CallbackQueryHandler(show_order_details_callback, pattern=r"^order_\d+$"),
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
			CallbackQueryHandler(select_order_executor_callback, pattern=r"^order_\d+__executor_\d+"),
			CallbackQueryHandler(change_order_status_callback, pattern=r"^order_\d+__status_\d+"),
			# CallbackQueryHandler(select_executor_orders_callback, pattern=r"^executor_\d+$"),
		],
		MenuState.USER_DETAILS: [
			user_details_handler,
			CallbackQueryHandler(save_supplier_rating_callback, pattern=r"^save_rating"),
			CallbackQueryHandler(set_user_rating_callback, pattern=r"^rate"),
			CallbackQueryHandler(show_authors_for_user_rating_callback, pattern=r"^authors_for_user_rating_\d+$"),
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
			profile_options_choice_handler
		],
		MenuState.TARIFF_CHANGE: [
			CallbackQueryHandler(choose_tariff_callback, pattern=r"^tariff_"),
		],
		MenuState.COOP_REQUESTS: [
			CallbackQueryHandler(coop_request_message_callback),
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

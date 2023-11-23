import re
from datetime import datetime
from typing import Optional, Union

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, filters, CallbackQueryHandler, ContextTypes
)

from bot.bot_settings import CHANNEL_ID
from bot.constants.menus import start_menu
from bot.constants.messages import denied_access_message, share_files_message
from bot.constants.patterns import (
	START_PATTERN, DONE_PATTERN, BACK_PATTERN, PROFILE_PATTERN, COOPERATION_REQUESTS_PATTERN, USERS_SEARCH_PATTERN
)
from bot.handlers.common import (
	init_start_section, user_authorization, load_user_field_names, set_priority_group,
	invite_user_to_chat, is_user_chat_member, go_back_section, update_category_list_callback, delete_messages_by_key,
	message_for_admin_callback
)
from bot.handlers.cooperation import cooperation_requests, coop_request_message_callback
from bot.handlers.done import done
from bot.handlers.main import (
	main_menu_choice, show_user_details_callback, user_details_choice,
	select_events_callback, select_sandbox_callback, change_supplier_segment_callback,
	users_search_choice, recommend_new_user_callback, services_choice, designer_orders_choice,
	select_users_list_callback
)
from bot.handlers.order import add_order_fields_choice, modify_order_fields_choice, show_order_details_callback, \
	manage_order_callback, select_order_executor_callback, modify_order_callback, remove_order_callback, \
	new_order_callback
from bot.handlers.search import select_search_option_callback, input_search_data_choice, select_search_segment_callback, \
	select_search_categories_callback, select_search_rating_callback
from bot.handlers.profile import (
	profile_menu_choice, profile_sections_choice, edit_user_details_callback, modify_user_data_fields_callback,
	choose_tariff_callback
)
from bot.handlers.rating import (
	select_rate_callback, answer_rating_questions_callback, change_rating_callback, show_voted_designers_callback
)
from bot.handlers.support import (
	ask_question_to_admin_choice,
	reply_to_user_message_callback
)
from bot.handlers.upload import prepare_shared_files, upload_files_callback, share_files_callback
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import determine_greeting, generate_inline_markup


async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Union[str, int]:
	"""Начало диалога по команде /start или сообщении start"""

	await delete_messages_by_key(context, "last_message_id")
	await delete_messages_by_key(context, "last_message_ids")

	# Проверим, зарегистрирован ли пользователь
	has_authorized = await user_authorization(update, context)
	if has_authorized is None:
		return MenuState.DONE
	elif not has_authorized:
		return ConversationHandler.END

	# TODO: переместить логику сохранения user_field_names в саму функцию load_user_field_names
	context.bot_data.setdefault("user_field_names", await load_user_field_names(update.message, context))

	user_data = context.user_data
	user_is_rated = user_data["details"].get("is_rated")

	chat_data = context.chat_data
	chat_data["chat_id"] = update.effective_chat.id
	user = update.effective_user
	message_text = None

	set_priority_group(context)  # установим основную группу пользователя (дизайнер или поставщик) и сохраним ее
	is_channel_member = await is_user_chat_member(context.bot, user_id=user.id, chat_id=CHANNEL_ID)

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
		if not user_is_rated and user_data["priority_group"] in [Group.DESIGNER, Group.OUTSOURCER]:
			questionnaire_button = generate_inline_markup(
				["Перейти к анкетированию"],
				callback_data="questionnaire"
			)
			await update.message.reply_text(
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
	menu = await init_start_section(context, state=MenuState.START, text=message_text)

	if message_text:
		await share_files_message(
			update.message,
			"❗️_Для получения полного доступа к функционалу "
			"необходимо поделиться любыми документами или фото, "
			"подтверждающими выбранный вид деятельности_"
		)

	return menu["state"]


main_menu_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND,
	main_menu_choice
)

profile_menu_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(PROFILE_PATTERN, re.I)),
	profile_menu_choice
)

services_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & ~filters.Regex(re.compile(USERS_SEARCH_PATTERN, re.I)),
	services_choice
)

profile_sections_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND,
	profile_sections_choice
)

user_details_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND,
	user_details_choice
)

designer_orders_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND,
	designer_orders_choice
)

users_search_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(USERS_SEARCH_PATTERN, re.I)),
	users_search_choice
)

input_search_data_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & ~filters.Regex(re.compile(BACK_PATTERN, re.I)),
	input_search_data_choice
)

cooperation_requests_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(COOPERATION_REQUESTS_PATTERN, re.I)),
	cooperation_requests
)

back_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(BACK_PATTERN, re.I)),
	go_back_section
)

done_handler = MessageHandler(
	filters.TEXT & filters.Regex(re.compile(DONE_PATTERN, re.I)),
	done
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
			profile_menu_handler,
			# cooperation_requests_handler, # в стадии будущего обсуждения
			main_menu_handler,
		],
		MenuState.SUPPLIERS_REGISTER: [
			users_search_handler,
			CallbackQueryHandler(select_users_list_callback, pattern=r"^group_\d+__category_\d+$"),
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
			# TODO: [task 3]
			CallbackQueryHandler(recommend_new_user_callback, pattern=r"^add_new_user_\d+$"),
		],
		MenuState.SERVICES: [
			services_handler,  # 1
			users_search_handler,  # 2
			CallbackQueryHandler(select_users_list_callback, pattern=r"^group_\d+__category_\d+$"),
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
			CallbackQueryHandler(recommend_new_user_callback, pattern=r"^add_new_user_\d+$"),
			CallbackQueryHandler(new_order_callback, pattern=r"^place_order$"),
		],
		MenuState.ORDERS: [
			designer_orders_handler,
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
			CallbackQueryHandler(show_order_details_callback, pattern=r"^order_\d+$"),
			CallbackQueryHandler(new_order_callback, pattern=r"^place_order$"),
			CallbackQueryHandler(select_order_executor_callback, pattern=r"^order_\d+__executor_\d+"),
			CallbackQueryHandler(manage_order_callback, pattern=r"^order_\d+__action_\d+"),
			CallbackQueryHandler(remove_order_callback, pattern=r'^remove_order_\d+__(yes|no)$'),
			CallbackQueryHandler(modify_order_callback, pattern=r"^modify_order_\d+__\D+$"),
		],
		MenuState.ADD_ORDER: [
			MessageHandler(filters.TEXT & ~filters.COMMAND, add_order_fields_choice),
			CallbackQueryHandler(update_category_list_callback, pattern=r"^group_\d+__category_\d+$"),
		],
		MenuState.MODIFY_ORDER: [
			MessageHandler(filters.TEXT & ~filters.COMMAND, modify_order_fields_choice),
		],
		MenuState.USER_DETAILS: [
			user_details_handler,
			CallbackQueryHandler(answer_rating_questions_callback, pattern=r"^update_rating"),
			CallbackQueryHandler(change_rating_callback, pattern=r"^save_rates"),
			CallbackQueryHandler(select_rate_callback, pattern=r"^rate"),
			CallbackQueryHandler(show_voted_designers_callback, pattern=r"^voted_list_for_user_\d+$"),
			CallbackQueryHandler(change_supplier_segment_callback, pattern=r'user_\d+__segment_\d+$'),
		],
		MenuState.PROFILE: [
			# TODO: [task 5]
			profile_sections_handler,
			CallbackQueryHandler(edit_user_details_callback, pattern=r"^modify_user_details"),
			CallbackQueryHandler(modify_user_data_fields_callback, pattern=r"^modify_user_field_"),
			CallbackQueryHandler(change_supplier_segment_callback, pattern=r'user_\d+$__segment_\d+$'),
		],
		MenuState.SUPPORT: [
			# TODO: в разработке
			MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question_to_admin_choice),
		],
		MenuState.SETTINGS: [
			# TODO: разработать структуру настроек
		],
		MenuState.FAVOURITES: [
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
		],
		MenuState.DESIGNER_EVENTS: [
			CallbackQueryHandler(select_events_callback, pattern=r"^event_type_\d+$"),
		],
		MenuState.DESIGNER_SANDBOX: [
			CallbackQueryHandler(select_sandbox_callback, pattern=r"^sandbox_type_\d+$"),
		],
		MenuState.TARIFF_CHANGE: [
			CallbackQueryHandler(choose_tariff_callback, pattern=r"^tariff_"),
		],
		MenuState.COOP_REQUESTS: [
			CallbackQueryHandler(coop_request_message_callback),
		],
		MenuState.USERS_SEARCH: [
			input_search_data_handler,
			CallbackQueryHandler(select_search_option_callback, pattern=r"^\d+$"),
			CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
			CallbackQueryHandler(select_search_rating_callback, pattern=r'^rating_\d+$'),
			CallbackQueryHandler(select_search_segment_callback, pattern=r'^segment_\d+$'),
			CallbackQueryHandler(select_search_categories_callback, pattern=r"^group_\d+__category_\d+$"),
		],
		MenuState.DONE: [
			done_handler,
		],
	},
	fallbacks=[
		back_handler,
		MessageHandler(filters.PHOTO, prepare_shared_files),
		MessageHandler(filters.ATTACHMENT, prepare_shared_files),
		CallbackQueryHandler(message_for_admin_callback, pattern=r"^message_for_admin"),
		CallbackQueryHandler(upload_files_callback, pattern=r"^upload_files$"),
		CallbackQueryHandler(share_files_callback, pattern=r"^share_files$"),
		CallbackQueryHandler(reply_to_user_message_callback, pattern=r"^reply_to_\d+__message_id_\d+$"),
	]
)

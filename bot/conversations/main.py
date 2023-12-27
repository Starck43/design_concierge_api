import re
from datetime import datetime
from functools import partial
from typing import Union
from warnings import filterwarnings

from telegram import Update
from telegram.ext import (
	CommandHandler, MessageHandler, ConversationHandler, filters, CallbackQueryHandler, ContextTypes
)
from telegram.warnings import PTBUserWarning

from bot.bot_settings import CHANNEL_ID
from bot.constants.menus import done_menu
from bot.constants.messages import denied_access_message, share_files_message, offer_questionnaire_message
from bot.constants.patterns import (
	START_PATTERN, DONE_PATTERN, BACK_PATTERN, PROFILE_PATTERN, COOPERATION_REQUESTS_PATTERN, USERS_SEARCH_PATTERN,
	TRADE_PATTERN
)
from bot.handlers.common import (
	init_start_section, user_authorization, load_user_field_names, set_priority_group,
	invite_user_to_chat, is_user_chat_member, go_back_section, select_user_categories_callback, delete_messages_by_key,
	message_for_admin_callback, select_user_group_callback, confirm_region_callback, show_chat_group_links,
	trade_dialog_choice, post_user_log_data
)
from bot.handlers.cooperation import cooperation_requests, coop_request_message_callback
from bot.handlers.done import done
from bot.handlers.main import (
	main_menu_choice, show_user_details_callback, user_details_choice,
	select_events_type_callback, change_supplier_segment_callback,
	users_search_choice, services_choice, show_users_list_callback, select_events_month_callback
)
from bot.handlers.order import (
	add_order_fields_choice, modify_order_fields_choice, show_order_details_callback, select_order_executor_callback,
	manage_order_callback, modify_order_callback, remove_order_callback, new_order_callback, apply_order_offer_callback,
	get_order_contact_info_callback, designer_orders_choice, order_details_choice, reply_to_order_message_callback
)
from bot.handlers.profile import (
	profile_menu_choice, profile_sections_choice, modify_profile_callback, modify_user_data_fields_callback,
	choose_tariff_callback, modify_user_field_choice, add_user_region, remove_region_callback
)
from bot.handlers.rating import (
	select_rate_callback, answer_rating_questions_callback, change_rating_callback, show_voted_designers_callback
)
from bot.handlers.search import (
	select_search_option_callback, input_search_data_choice, select_search_segment_callback,
	select_search_categories_callback, select_search_rating_callback
)
from bot.handlers.support import ask_question_to_admin_choice, reply_to_user_message_callback
from bot.handlers.upload import prepare_shared_files, upload_files_callback, share_files_callback
from bot.handlers.user import (
	recommend_user_choice, recommend_new_user_callback, select_user_segment_callback, confirm_user_region_callback
)
from logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import determine_greeting

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)


async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Union[str, int]:
	"""Начало диалога по команде /start или сообщении start"""
	# locale.setlocale(locale.LC_ALL, locale.getdefaultlocale())

	await delete_messages_by_key(context, "last_message_id")
	await delete_messages_by_key(context, "last_message_ids")

	# Проверим, зарегистрирован ли пользователь
	has_authorized = await user_authorization(update, context)
	if has_authorized is None:  # если проблемы с проверкой, то предложим меню с завершением работы
		return MenuState.DONE

	elif not has_authorized:  # если не авторизован, то завершим диалог
		return ConversationHandler.END

	await load_user_field_names(update.message, context)  # подгрузим имена полей данных у пользователя

	user_data = context.user_data
	user_details = user_data["details"]
	user_is_rated = user_details.get("is_rated")

	chat_data = context.chat_data
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	chat_data["chat_id"] = update.effective_chat.id
	user = update.effective_user

	set_priority_group(context)  # установим основную группу пользователя (дизайнер или поставщик) и сохраним ее
	is_channel_member = await is_user_chat_member(context.bot, user_id=user.id, chat_id=CHANNEL_ID)

	if user_data["details"].get("access", -2) == -2:
		message = f'Access denied for {user_data["details"]["name"]} (ID:{user.id})'
		log.warning(message, extra=user_data["details"])
		await post_user_log_data(context, status_code=5, message=message)

		message = await denied_access_message(update.message)
		last_message_ids["denied_access"] = message.message_id

		return MenuState.DONE

	# если пользователь первый раз начал диалог
	if chat_data.get("status") != "dialog":
		chat_data["status"] = "dialog"
		hour = datetime.now().time().hour
		greeting = determine_greeting(hour)

		await update.message.reply_text(
			f'{greeting}, {user.first_name}\n'
			f'Добро пожаловать в Консьерж для Дизайнера!\n',
			reply_markup=done_menu if not is_channel_member else None
		)

		if user_details.get("access", -1) < 0:
			message = await share_files_message(
				update.message,
				'❗️*Доступ к Консьерж Сервис частично ограничен!*\n'
				'_Для получения полного доступа к функционалу '
				'необходимо поделиться любыми документами или фото, '
				'подтверждающими Ваш вид деятельности._'
			)
			last_message_ids["share_files"] = message.message_id

		# выведем сообщение с присоединением к группам, если еще не присоединены
		if is_channel_member:
			await show_chat_group_links(update, context, hide_joined_groups=True)

		# если пользователь не поставщик и не выставлял вообще рейтинг ни разу, то вывести приглашение об анкетировании
		if not user_is_rated and user_data["priority_group"] in [Group.DESIGNER, Group.OUTSOURCER]:
			message = await offer_questionnaire_message(update.message)
			last_message_ids["offer_questionnaire"] = message.message_id

	# если дизайнер не присоединился к каналу,
	if user_data["priority_group"] == Group.DESIGNER and not is_channel_member:
		text = '❗️Прежде чем перейти в Консьерж Сервис, Вам необходимо присоединиться к нашему каналу'
		message = await invite_user_to_chat(update, user_id=user.id, chat_id=CHANNEL_ID, text=text)
		if message:
			last_message_ids["invite_to_channel"] = message.message_id

	else:
		message = f'User {user_details["name"]} (ID:{user.id}) started conversation'
		log.info(message)
		await post_user_log_data(context, status_code=3, message=message)
		# начальное меню разделов бота
		menu = await init_start_section(context, state=MenuState.START)
		return menu["state"]

	return ConversationHandler.END


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

order_details_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND,
	order_details_choice
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
		MessageHandler(
			filters.TEXT & ~filters.COMMAND & filters.Regex(re.compile(TRADE_PATTERN, re.I)),
			trade_dialog_choice
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
			CallbackQueryHandler(show_users_list_callback, pattern=r"^group_\d+__category_\d+.*$"),
			CallbackQueryHandler(recommend_new_user_callback, pattern=r"^recommended_user_\d+$"),
		],
		MenuState.SERVICES: [
			services_handler,  # first callback
			users_search_handler,  # second callback
			CallbackQueryHandler(show_users_list_callback, pattern=r"^group_\d+__category_\d+.*$"),
			CallbackQueryHandler(recommend_new_user_callback, pattern=r"^recommended_user_\d+$"),
			CallbackQueryHandler(new_order_callback, pattern=r"^place_order$"),
		],
		MenuState.DESIGNER_ORDERS: [
			designer_orders_handler,
			CallbackQueryHandler(new_order_callback, pattern=r"^place_order$"),
		],
		MenuState.ORDER: [
			order_details_handler,
			CallbackQueryHandler(select_order_executor_callback, pattern=r"^order_\d+__executor_\d+"),
			CallbackQueryHandler(apply_order_offer_callback, pattern=r"^apply_order_\d+"),
			CallbackQueryHandler(manage_order_callback, pattern=r"^order_\d+__action_\d+"),
			CallbackQueryHandler(remove_order_callback, pattern=r'^remove_order_\d+__(yes|no)$'),
			CallbackQueryHandler(modify_order_callback, pattern=r"^modify_order_\d+__\D+$"),
			CallbackQueryHandler(get_order_contact_info_callback, pattern=r"^owner_contact_info_\d+$"),
		],
		MenuState.ADD_ORDER: [
			MessageHandler(filters.TEXT & ~filters.COMMAND, add_order_fields_choice),
			CallbackQueryHandler(select_user_categories_callback, pattern=r"^group_\d+__category_\d+$"),
		],
		MenuState.RECOMMEND_USER: [
			MessageHandler(filters.TEXT & ~filters.COMMAND, recommend_user_choice),
			CallbackQueryHandler(confirm_user_region_callback, pattern=r'^choose_region_(yes|no)$'),
			CallbackQueryHandler(partial(select_user_group_callback, button_type="radiobutton"), pattern=r"0|1|2$"),
			CallbackQueryHandler(select_user_categories_callback, pattern=r".*category_\d+$"),
			CallbackQueryHandler(select_user_segment_callback, pattern=r'^segment_\d+$'),
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
			profile_sections_handler,
			CallbackQueryHandler(modify_profile_callback, pattern=r"^profile_(modify|cancel)$"),
			CallbackQueryHandler(change_supplier_segment_callback, pattern=r'user_\d+$__segment_\d+$'),
		],
		MenuState.MODIFY_PROFILE: [
			MessageHandler(filters.TEXT & ~filters.COMMAND, modify_user_field_choice),
			CallbackQueryHandler(modify_user_data_fields_callback, pattern=r"^modify_field_\D+$"),
			CallbackQueryHandler(select_user_categories_callback, pattern=r".*category_\d+$"),
			CallbackQueryHandler(
				partial(confirm_region_callback, add_region_func=add_user_region),
				pattern=r'^choose_region_(yes|no)$'
			),
			CallbackQueryHandler(remove_region_callback, pattern=r"^region_\d+$"),
		],
		MenuState.TARIFF_CHANGE: [
			CallbackQueryHandler(choose_tariff_callback, pattern=r"^tariff_"),
		],
		MenuState.SUPPORT: [
			MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question_to_admin_choice),
		],
		MenuState.SETTINGS: [
			# TODO: разработать структуру настроек
		],
		MenuState.FAVOURITES: [
		],
		MenuState.USERS_SEARCH: [
			input_search_data_handler,
			CallbackQueryHandler(select_search_option_callback, pattern=r"^\d+$"),
			CallbackQueryHandler(select_search_rating_callback, pattern=r'^rating_\d+$'),
			CallbackQueryHandler(select_search_segment_callback, pattern=r'^segment_\d+$'),
			CallbackQueryHandler(select_search_categories_callback, pattern=r"^group_\d+__category_\d+$"),
			CallbackQueryHandler(recommend_new_user_callback, pattern=r"^recommended_user_\d+$"),
		],
		MenuState.DESIGNER_EVENTS: [
			CallbackQueryHandler(select_events_type_callback, pattern=r"^events_type_\d+$"),
			CallbackQueryHandler(select_events_month_callback, pattern=r"^events_type_\d+__.+$"),
		],
		MenuState.PERSONAL_ASSISTANT: [
			# CallbackQueryHandler(success_joined_to_chat_callback, pattern=r"^joined_to_chat$"),
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
		MessageHandler(filters.PHOTO, prepare_shared_files),
		MessageHandler(filters.ATTACHMENT, prepare_shared_files),
		CallbackQueryHandler(message_for_admin_callback, pattern=r"^message_for_admin"),
		CallbackQueryHandler(upload_files_callback, pattern=r"^upload_files$"),
		CallbackQueryHandler(share_files_callback, pattern=r"^share_files$"),
		CallbackQueryHandler(show_user_details_callback, pattern=r"^user_\d+$"),
		CallbackQueryHandler(reply_to_order_message_callback, pattern=r"^order_\d+__message_id_\d+$"),
		CallbackQueryHandler(reply_to_user_message_callback, pattern=r"^reply_to_\d+__message_id_\d+$"),
		CallbackQueryHandler(show_order_details_callback, pattern=r"^order_\d+.*")
	]
)

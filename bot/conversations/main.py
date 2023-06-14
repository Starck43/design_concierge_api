import re
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, filters, CallbackQueryHandler, \
	ContextTypes

from bot.bot_settings import CHANNEL_ID
from bot.constants.menus import main_menu, reg_menu
from bot.constants.patterns import DONE_PATTERN, PROFILE_PATTERN, BACK_PATTERN, SERVICES_PATTERN, \
	COOPERATION_REQUESTS_PATTERN, START_PATTERN, DESIGNER_PATTERN
from bot.conversations.registration import registration_dialog
from bot.handlers.cooperation import cooperation_requests, fetch_supplier_requests
from bot.handlers.done import done
from bot.handlers.main import main, designer_menu_choice, activity_select_callback, supplier_select_callback
from bot.handlers.profile import profile
from bot.handlers.registration import create_registration_link
from bot.handlers.services import fetch_supplier_services, services
from bot.handlers.utils import check_user_in_channel
from bot.logger import log
from bot.utils import determine_greeting, generate_reply_keyboard
from bot.states.main import MenuState
from api.models import Group


async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	"""Send a message when the command /start is issued."""
	parameters = context.args
	user = update.message.from_user
	user_data = context.user_data

	is_user_in_channel = await check_user_in_channel(CHANNEL_ID, user.id, context.bot)
	if not is_user_in_channel:
		await update.message.reply_text(
			'Здравствуйте, Вас приветствует Консьерж Сервис для дизайнеров.\n'
		)
		if parameters and parameters[0].lower() == "register":
			await update.message.reply_text(
				"Чтобы попасть в наш закрытый канал, Вы должны пройти регистрацию.",
				reply_markup=reg_menu,
			)
		else:
			await create_registration_link(update, context)
		return ConversationHandler.END

	else:
		reply_text = f'{update.message.from_user.first_name}, мы уже начали диалог, если Вы помните'

		if "details" not in user_data:
			log.info("%s starts dialog...", user.full_name)
			user_data["details"] = {
				"id": user.id,
				"name": user.full_name,
			}
			hour = datetime.now().time().hour
			greeting = determine_greeting(hour)

			reply_text = f"{greeting}, {user.full_name}"

		# TODO: Заменить Данные на значение из БД
		user_group = user_data["details"].get("group", Group.DESIGNER.value)
		user_name = user_data["details"].get("username", user.full_name)
		user_data["details"] = {
			"group": Group.DESIGNER.value,
			"username": user_name,
		}
		user_data["previous_state"] = ConversationHandler.END
		user_data["current_state"] = MenuState.MAIN_MENU
		user_data["current_keyboard"] = main_menu.get(user_group, None)

		await update.message.reply_text(reply_text)

		return await main(update, context)


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	"""Back to level up screen."""
	user_data = context.user_data
	user_group = user_data["details"]["group"]

	previous_state = user_data.get("previous_state", None)
	if previous_state is not None:
		user_data["current_state"] = previous_state
	current_keyboard = user_data.get("current_keyboard", None)

	await update.message.delete()

	if context.error or previous_state == MenuState.MAIN_MENU or previous_state is None:
		return await main(update, context)

	if previous_state and previous_state != ConversationHandler.END:
		menu_markup = generate_reply_keyboard(current_keyboard)
		await update.message.reply_text(
			previous_state,
			reply_markup=menu_markup,
		)
	return previous_state


done_handler = MessageHandler(
	filters.TEXT & filters.Regex(
		re.compile(DONE_PATTERN, re.IGNORECASE)
	),
	done
)

back_handler = MessageHandler(
	filters.TEXT & filters.Regex(
		re.compile(BACK_PATTERN, re.IGNORECASE)
	),
	go_back
)

designer_main_menu_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(
		re.compile(DESIGNER_PATTERN, re.IGNORECASE)
	),
	designer_menu_choice
)

profile_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(
		re.compile(PROFILE_PATTERN, re.IGNORECASE)
	),
	profile
)

services_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(
		re.compile(SERVICES_PATTERN, re.IGNORECASE)
	),
	services
)

cooperation_requests_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(
		re.compile(COOPERATION_REQUESTS_PATTERN, re.IGNORECASE)
	),
	cooperation_requests
)

main_dialog = ConversationHandler(
	entry_points=[
		CommandHandler('start', start_conversation),
		MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(
			re.compile(START_PATTERN, re.IGNORECASE)
		), start_conversation),
	],
	states={
		MenuState.MAIN_MENU: [
			done_handler,
			profile_handler,
			designer_main_menu_handler,
			services_handler,
			cooperation_requests_handler,
		],
		MenuState.SUPPLIERS_REGISTER: [
			CallbackQueryHandler(activity_select_callback),
			back_handler,
		],
		MenuState.SUPPLIER_CHOOSING: [
			CallbackQueryHandler(supplier_select_callback),
			back_handler,
		],
		MenuState.PROFILE: [
			back_handler,
		],
		MenuState.SERVICES: [
			back_handler,
			CallbackQueryHandler(fetch_supplier_services),
		],
		MenuState.COOP_REQUESTS: [
			back_handler,
			CallbackQueryHandler(fetch_supplier_requests),
		],
		MenuState.NEW_USER: [
			registration_dialog,
		],
	},
	fallbacks=[
		MessageHandler(filters.TEXT & ~filters.COMMAND, go_back)
	]
)

from telegram import Update
from telegram.ext import ContextTypes

from bot.bot_settings import CHANNEL_ID
from bot.constants.common import HELP_CONTEXT
from bot.constants.menus import main_menu, done_menu
from bot.handlers.common import is_user_chat_member
from bot.utils import generate_reply_keyboard


async def helper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Send a message when the command /help is issued."""

	user_id = update.effective_user.id
	user_data = context.user_data
	if "details" in user_data:
		user_group = user_data["group"]
		menu_markup = main_menu.get(user_group, None)
	else:
		menu_markup = done_menu

	is_user_in_channel = await is_user_chat_member(context.bot, user_id, chat_id=CHANNEL_ID)
	if is_user_in_channel:
		await update.message.reply_text(" ".join(HELP_CONTEXT), reply_markup=menu_markup)

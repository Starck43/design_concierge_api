from telegram import Update
from telegram.ext import ContextTypes

from bot.bot_settings import CHANNEL_ID
from bot.constants.common import HELP_CONTEXT
from bot.constants.menus import main_menu, done_menu
from bot.handlers.utils import check_user_in_channel
from bot.utils import generate_reply_keyboard


async def helper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Send a message when the command /help is issued."""

	user_id = update.effective_user.id
	user_data = context.user_data
	if "details" in user_data:
		user_group = user_data["details"]["group"]
		keyboard = main_menu.get(user_group, None)
		menu_markup = generate_reply_keyboard(keyboard)
	else:
		menu_markup = done_menu

	is_user_in_channel = await check_user_in_channel(CHANNEL_ID, user_id, context.bot)
	if is_user_in_channel:
		await update.message.reply_text(" ".join(HELP_CONTEXT), reply_markup=menu_markup)

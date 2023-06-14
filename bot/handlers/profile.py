from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.constants.menus import profile_menu, main_menu
from bot.utils import generate_reply_keyboard
from bot.states.main import MenuState


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	user_name = user_data["details"]["username"]
	user_group = user_data["details"]["group"]
	keyboard = profile_menu.get(user_group, None)
	profile_markup = generate_reply_keyboard(keyboard)

	await update.message.reply_text(
		f'Профиль пользователя {user_name}',
		reply_markup=profile_markup
	)

	user_data["previous_state"] = user_data.get("current_state")
	user_data["current_state"] = MenuState.PROFILE
	user_data["current_keyboard"] = keyboard

	return user_data.get("current_state")


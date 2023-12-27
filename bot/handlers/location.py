from typing import Optional

from telegram import Update
from telegram.ext import CallbackContext

from bot.handlers.common import post_user_log_data
from bot.handlers.registration import update_location_in_reg_data
from logger import log
from bot.utils import fetch_location


async def update_geolocation_data_choice(update: Update, context: CallbackContext) -> Optional[str]:
	# Обработчик нажатия на кнопку поделиться геопозицией
	user = update.effective_user
	user_name = context.user_data.get("details", {}).get("name") or user.full_name
	location = update.message.location
	# Локация получена
	if location is not None:
		data: dict = await fetch_location(location.latitude, location.longitude)
		context.user_data["geolocation"] = data
		if data:
			message = f"User {user_name} (ID:{user.id}) shared his geolocation. " \
			          f"Region {data.get('region', 'not')} detected"
			log.info(message)
			await post_user_log_data(context, status_code=2, message=message)

		else:
			log.error(f"Geo location is not fetched")
	else:
		log.warning(f"Geo location is unavailable")

	if context.chat_data.get("status") == "registration":
		return await update_location_in_reg_data(update, context)

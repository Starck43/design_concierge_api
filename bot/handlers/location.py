from typing import Optional

from telegram import Update
from telegram.ext import CallbackContext

from bot.handlers.registration import update_location_in_reg_data
from bot.logger import log
from bot.utils import fetch_location


async def update_geolocation_data_choice(update: Update, context: CallbackContext) -> Optional[str]:
	# Обработчик нажатия на кнопку поделиться геопозицией
	user = update.effective_user
	location = update.message.location
	# Локация получена
	if location is not None:
		data: dict = await fetch_location(location.latitude, location.longitude)
		context.chat_data["geolocation"] = data

		if data:
			log.info(
				f"User {user.full_name} (ID:{user.id}) shared his geolocation. "
				f"Region {data.get('region', 'not')} detected."
			)
		else:
			log.warn(f"Geo location is not fetched.")
	else:
		log.warn(f"Geo location is unavailable.")

	if context.chat_data.get("status") == "registration":
		return await update_location_in_reg_data(update, context)

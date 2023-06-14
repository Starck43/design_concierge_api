
# Обработка события нажатия на кнопку
from telegram import Update
from telegram.ext import ContextTypes

from bot.utils import fetch_data
from bot.states.registration import RegState


async def fetch_regions(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_data = context.user_data
	print("service request")
	query = update.callback_query
	query_data = query.data # для передачи параметром в запросе

	# Получение выбранной услуги из списка
	regions_list = user_data.get("regions_list", None)
	if regions_list:

		# Выполнение API запроса к серверу
		url = "https://data.pbprog.ru/api/address/regions"
		params = {
			"token": "feb6b25016f54d488d02106e4202ed09b1d14bdb",
			"activeOnly": False,
		}

		res = await fetch_data(url)
		if res:
			data = res.get("data", "Пустой результат")
			# Отправка результата пользователю в виде сообщения
			await query.message.reply_text(
				f"Результат: \n{data}"
			)

	return RegState.REGISTRATION

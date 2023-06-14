from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.constants.keyboards import BACK_KEYBOARD
from bot.constants.menus import main_menu
from bot.utils import fetch_data, generate_inline_keyboard, generate_reply_keyboard
from bot.states.main import MenuState


async def services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	user_group = user_data["details"]["group"]

	# TODO: Получить список сервисов из БД
	user_data["services_list"] = ['услуга 1', 'услуга 2', 'услуга 3']
	services_list = user_data["services_list"]

	buttons = generate_inline_keyboard(services_list)

	await update.message.reply_text(
		update.message.text,
		reply_markup=generate_reply_keyboard([BACK_KEYBOARD])
	)

	await update.message.reply_text(
		f'Выберите услугу:',
		reply_markup=buttons
	)
	current_state = user_data.get("current_state")
	user_data["previous_state"] = current_state
	user_data["current_state"] = MenuState.SERVICES
	user_data["current_keyboard"] = main_menu.get(user_group, None)

	return user_data["current_state"]


# Обработка события нажатия на кнопку
async def fetch_supplier_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_data = context.user_data
	print("service request")
	query = update.callback_query
	query_data = query.data # для передачи параметром в запросе

	# Получение выбранной услуги из списка
	services_list = user_data.get("services_list", None)
	if services_list:

		# Выполнение API запроса к серверу
		url = "https://run.mocky.io/v3/d8936a23-ca71-49a3-bcab-49342ce51377"

		res = await fetch_data(url)
		if res:
			data = res.get("data", "Пустой результат")
			# Отправка результата пользователю в виде сообщения
			await query.message.reply_text(
				f"Результат: \n{data}"
			)

	return MenuState.SERVICES

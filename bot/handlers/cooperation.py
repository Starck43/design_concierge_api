from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.constants.keyboards import BACK_KEYBOARD
from bot.constants.menus import main_menu
from bot.utils import fetch, generate_inline_keyboard, generate_reply_keyboard
from bot.states.main import MenuState


async def cooperation_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	user_group = user_data["details"]["group"]

	# TODO: Получить список уведомлений от дизайнеров
	user_data["coop_request_list"] = ['заявка 1', 'заявка 2', 'заявка 3']
	coop_request_list = user_data["coop_request_list"]

	buttons = generate_inline_keyboard(coop_request_list)

	await update.message.reply_text(
		update.message.text,
		reply_markup=generate_reply_keyboard([BACK_KEYBOARD])
	)

	await update.message.reply_text(
		f'Список заявок:',
		reply_markup=buttons
	)
	current_state = user_data.get("current_state")
	user_data["previous_state"] = current_state
	user_data["current_state"] = MenuState.COOP_REQUESTS
	user_data["current_keyboard"] = main_menu.get(user_group, None)

	return user_data["current_state"]


# Обработка события нажатия на кнопку
async def fetch_supplier_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user_data = context.user_data
	query = update.callback_query
	query_data = query.data # для передачи параметром в запросе

	# Получение выбранной услуги из списка
	request_list = user_data.get("coop_request_list", None)
	if request_list:

		# Выполнение API запроса к серверу
		url = "https://run.mocky.io/v3/d8936a23-ca71-49a3-bcab-49342ce51377"

		res = await fetch(url)
		if res:
			data = res.get("data", "Пустой результат")
			# Отправка результата пользователю в виде сообщения
			await query.message.reply_text(
				f"Результат: \n{data}"
			)

	return MenuState.COOP_REQUESTS

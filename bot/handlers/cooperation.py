from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.constants.keyboards import BACK_KEYBOARD
from bot.constants.menus import back_menu
from bot.handlers.common import add_menu_item
from bot.states.main import MenuState
from bot.utils import fetch, generate_inline_keyboard, generate_reply_keyboard


async def cooperation_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	state = MenuState.COOP_REQUESTS
	menu_markup = back_menu

	# TODO: Разработать функционал установления сотрудничества между дизайнерами и поставщиками
	chat_data["coop_request_list"] = ['заявка от дизайнера', 'заявка на сотрудничество', 'заявка 3']
	coop_request_list = chat_data["coop_request_list"]

	message = await update.message.reply_text(
		update.message.text,
		reply_markup=generate_reply_keyboard(BACK_KEYBOARD)
	)

	inline_message = await update.message.reply_text(
		f'Список заявок:',
		reply_markup=generate_inline_keyboard(coop_request_list)
	)

	add_menu_item(context, state, message, inline_message, menu_markup)

	return state


# Обработка события нажатия на кнопку
async def coop_request_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data

	# Получение деталей сообщения из списка
	request_list = chat_data.get("coop_request_list", None)
	if request_list:
		# Выполнение API запроса к серверу
		url = "https://run.mocky.io/v3/d8936a23-ca71-49a3-bcab-49342ce51377"

		res = await fetch(url)
		if res[0]:
			data = res[0].get("data", "Пустой результат")
			await query.message.reply_text(
				f"Результат: \n{data}"
			)

	return MenuState.COOP_REQUESTS

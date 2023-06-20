from typing import List, Dict

from telegram import Message
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.constants.keyboards import GROUPS_REG_KEYBOARD, CONFIRM_KEYBOARD
from bot.constants.menus import (
	continue_reg_menu, cancel_reg_menu, start_menu, done_menu, done_reg_menu, reg_menu
)
from bot.logger import log
from bot.states.registration import RegState
from bot.utils import generate_inline_keyboard


async def before_start_reg_message(message: Message) -> Message:
	return await message.reply_text(
		"Чтобы попасть в наш закрытый канал, Вы должны пройти регистрацию.",
		reply_markup=reg_menu,
	)


async def start_reg_message(message: Message) -> Message:
	buttons = generate_inline_keyboard(
		GROUPS_REG_KEYBOARD,
		callback_data=[
			str(RegState.SERVICE_GROUP),
			str(RegState.SUPPLIER_GROUP)
		])

	await message.reply_text(
		"Для начала давайте познакомимся.",
		reply_markup=cancel_reg_menu,
	)

	return await message.reply_text(
		"Кого Вы представляете?",
		reply_markup=buttons,
	)


async def interrupt_reg_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or "⚠️ Регистрация прервана.",
		reply_markup=done_menu
	)


async def yet_registered_message(message: Message) -> None:
	await message.reply_text(
		'*Вы уже зарегистрированы!*\n'
		'Можете начать пользоваться Консьерж Сервис\n',
		reply_markup=start_menu
	)


async def welcome_start_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or f'Добро пожаловать в Консьерж Сервис для дизайнеров!\n',
		reply_markup=start_menu
	)


async def check_categories_message(message: Message, buttons: List, text: str = None) -> Message:
	reply_markup = generate_inline_keyboard(
		buttons,
		item_key="name",
		callback_data="id",
		prefix_callback_name="category_",
		vertical=True
	)
	return await message.reply_text(
		text or 'Отметьте категории, в которых вы представлены и нажмите *Продолжить* ⬇️',
		reply_markup=reply_markup,
	)


async def require_check_categories_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or "⚠️ Необходимо выбрать хотя бы одну категорию!",
		reply_markup=continue_reg_menu,
	)


async def only_in_list_warn_message(message: Message, text: str = None) -> Message:
	await message.delete()
	return await message.reply_text(
		text or '⚠️ Можно выбрать категорию только из списка!\n',
		reply_markup=continue_reg_menu,
	)


async def region_selected_warn_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		f'⚠️  *{text}* был уже выбран!\n',
		reply_markup=continue_reg_menu,
	)


async def confirm_region_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_keyboard([CONFIRM_KEYBOARD], callback_data=["yes", "no"])
	return await message.reply_text(
		f'{text}, все верно?\n',
		reply_markup=buttons
	)


async def not_found_region_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or f"⚠️ Регион с названием {message.text.upper()} не найден!\n"
		        f"Повторите ввод.\n",
		reply_markup=continue_reg_menu,
	)


async def add_new_region_message(message: Message, bot_data: Dict, text: str) -> None:
	if "selected_region_message" in bot_data:
		saved_message = bot_data["selected_region_message"]
		message_text = saved_message.text
		await saved_message.delete()
	else:
		message_text = ""

	bot_data["selected_region_message"] = await message.reply_text(
		message_text + f'\n*{text}* ☑️',
		reply_markup=continue_reg_menu,
	)


async def show_reg_report_message(message: Message, data: str = None) -> Message:
	return await message.reply_text(
		f'🏁 <b>Регистрация завершена!</b>\n\n'
		f'Проверьте и подтвердите Ваши данные через смс.\n\n'
		f'{data}',
		reply_markup=done_reg_menu,
		parse_mode=ParseMode.HTML
	)


async def show_done_reg_message(message: Message) -> None:
	await message.reply_text(
		f'*Спасибо за регистрацию*\n'
		f'Теперь Вам доступен весь функционал Консьерж Сервис.',
		reply_markup=start_menu
	)


async def server_error_message(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		error_data: Dict,
		text: str = "",
) -> None:
	user = message.chat
	user_data = context.user_data
	user_data["error"] = error_data.get("error", "Неизвестная ошибка")
	user_data["status_code"] = error_data.get("status_code", "unknown")
	user_data["url"] = error_data.get("url", "")
	error_text = text or f'{user_data["status_code"]}: {user_data["error"]}\n'
	log.info('User {} got server error {} on request {}: "{}"'.format(
		user.id, user_data["status_code"], user_data["url"], user_data["error"]
	))

	await message.reply_text(
		f"*Ошибка сервера!*\n"
		f"{error_text}\n\n"
		f"Приносим свои извинения, {user.first_name}",
		reply_markup=done_menu
	)
	await message.reply_text(
		"Вы можете сообщить об ошибке администратору",
		reply_markup=generate_inline_keyboard(["Отправить уведомление"])
	)

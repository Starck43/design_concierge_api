from typing import List

from telegram import Message
from telegram.constants import ParseMode

from bot.constants.keyboards import GROUPS_REG_KEYBOARD, CONFIRM_KEYBOARD
from bot.constants.menus import continue_reg_menu, cancel_reg_menu, start_menu, done_menu, done_reg_menu
from bot.states.registration import RegState
from bot.utils import generate_inline_keyboard


async def start_reg_message(message: Message) -> Message:
	buttons = generate_inline_keyboard(
		GROUPS_REG_KEYBOARD,
		callback_data=[
			str(RegState.SERVICE_GROUP_REGISTRATION),
			str(RegState.SUPPLIER_GROUP_REGISTRATION)
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


async def registered_yet_message(message: Message) -> None:
	await message.reply_text(
		'*Вы уже зарегистрированы!*\n'
		'Чтобы войти в Консьерж Сервис,\n'
		'выберите в меню команду *start*'
	)


async def welcome_start_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or f'Добро пожаловать в Консьерж Сервис для дизайнеров!\n',
		reply_markup=start_menu
	)


async def check_list_message(message: Message, buttons: List, text: str = None) -> Message:

	reply_markup = generate_inline_keyboard(
		buttons,
		item_key="name",
		callback_data="id",
		vertical=True
	)
	return await message.reply_text(
		text or 'Отметьте категории, в которых вы представлены и нажмите *Продолжить* ⬇️',
		reply_markup=reply_markup,
	)

	
async def require_check_list_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or "⚠️ Необходимо выбрать хотя бы одну категорию!",
		reply_markup=continue_reg_menu,
	)
	
	
async def only_in_list_warn_message(message: Message, text: str = None) -> None:
	await message.delete()
	await message.reply_text(
		text or '⚠️ Можно выбрать категорию только из списка!\n',
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


async def show_reg_report_message(message: Message, data: str = None) -> Message:
	return await message.reply_text(
		f'🏁 <b>Регистрация завершена!</b>\n\n'
		f'Проверьте и подтвердите Ваши данные через смс.\n\n'
		f'{data}',
		reply_markup=done_reg_menu,
		parse_mode=ParseMode.HTML
	)

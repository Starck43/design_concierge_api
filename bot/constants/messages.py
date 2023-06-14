from typing import List

from telegram import Message

from bot.constants.menus import continue_reg_menu
from bot.utils import generate_inline_keyboard


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
		"⚠️ Необходимо выбрать хотя бы одну категорию!",
		reply_markup=continue_reg_menu,
	)
	
	
async def only_in_list_warn_message(message: Message, text: str = None) -> None:
	await message.delete()
	await message.reply_text(
		text or '⚠️ Можно выбрать категорию только из списка!\n',
		reply_markup=continue_reg_menu,
	)

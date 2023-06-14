from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.constants.data import categories_list, suppliers_list
from bot.constants.keyboards import SUPPLIER_LIST_KEYBOARD, SUPPLIER_DETAILS_KEYBOARD
from bot.constants.menus import main_menu
from bot.utils import generate_reply_keyboard, generate_inline_keyboard, filter_list, find_obj_in_list
from bot.states.main import MenuState
from api.models import Group


async def main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	user_group = user_data["details"].get("group", Group.DESIGNER.value)
	keyboard = main_menu.get(user_group, None)
	menu_markup = generate_reply_keyboard(keyboard)

	await update.message.reply_text(
		'Основной раздел:' if user_data["previous_state"] == MenuState.MAIN_MENU else 'Выберите интересующий раздел:',
		reply_markup=menu_markup,
	)

	return user_data["current_state"]


async def designer_menu_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	user_data = context.user_data
	user_data["previous_state"] = user_data.get("current_state")
	# user_details = user_data["details"]
	message_text = update.message.text

	# await update.message.edit_text(f"Переход в раздел: <b>{message_text.upper()}</b>", parse_mode=ParseMode.HTML)

	if message_text == str(MenuState.SUPPLIERS_REGISTER):
		user_data["current_state"] = MenuState.SUPPLIERS_REGISTER
		user_data["current_keyboard"] = SUPPLIER_LIST_KEYBOARD

		await update.message.reply_text(
			f'*{message_text.upper()}*',
			reply_markup=generate_reply_keyboard(user_data["current_keyboard"]),
			parse_mode=ParseMode.MARKDOWN,
		)

		categories_inline_buttons = generate_inline_keyboard(
			categories_list,
			callback_data="id",
			item_key="name",
			vertical=True
		)

		await update.message.reply_text(
			"Выберите категорию поставщиков:",
			reply_markup=categories_inline_buttons,
		)

	return user_data.get("current_state")


async def activity_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	button_data = query.data
	user_data = context.user_data
	user_data["current_state"] = MenuState.SUPPLIER_CHOOSING
	user_data["current_keyboard"] = SUPPLIER_LIST_KEYBOARD

	supplier_list = filter_list(suppliers_list, filter_key="cat_id", filter_value=int(button_data))
	supplier_name, _ = find_obj_in_list(categories_list, key="id", value=int(button_data))

	await query.message.delete()

	await query.message.reply_text(
		f'➡️ *{supplier_name.get("name", "---").upper()}*',
		reply_markup=generate_reply_keyboard(user_data["current_keyboard"]),
		parse_mode=ParseMode.MARKDOWN,
	)

	await query.message.reply_text(
		text=f'_Выберите организацию:_',
		reply_markup=generate_inline_keyboard(supplier_list, callback_data="id", item_key="name"),
		parse_mode=ParseMode.MARKDOWN,
	)

	return MenuState.SUPPLIER_CHOOSING


async def supplier_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	button_data = query.data
	user_data = context.user_data

	supplier_name, _ = find_obj_in_list(suppliers_list, key="id", value=int(button_data))

	await query.message.delete()
	await query.message.reply_text(
		f'*{supplier_name.get("name", "---").upper()} ({user_data["current_state"]})*\n\n'
		f'_Описание организации..._',
		reply_markup=generate_reply_keyboard(SUPPLIER_DETAILS_KEYBOARD, one_time_keyboard=False),
		parse_mode=ParseMode.MARKDOWN,
	)

	return MenuState.SUPPLIER_CHOOSING

from telegram import ReplyKeyboardMarkup

from bot.constants.keyboards import (
	DESIGNER_KEYBOARD, SUPPLIER_KEYBOARD, DONE_KEYBOARD, CANCEL_KEYBOARD, SEND_CONFIRMATION_KEYBOARD,
	SUPPLIER_PROFILE_KEYBOARD, DESIGNER_PROFILE_KEYBOARD, START_BOT_KEYBOARD, BACK_KEYBOARD, TO_TOP_KEYBOARD,
	CONTINUE_KEYBOARD, OUTSOURCER_KEYBOARD, UNCATEGORIZED_KEYBOARD, OUTSOURCER_PROFILE_KEYBOARD
)

# TODO: заменить часть редких на автогенерируемые меню в коде
start_menu = ReplyKeyboardMarkup([START_BOT_KEYBOARD, DONE_KEYBOARD], resize_keyboard=True, is_persistent=True)
done_menu = ReplyKeyboardMarkup([DONE_KEYBOARD], resize_keyboard=True, one_time_keyboard=True, is_persistent=True)
back_menu = ReplyKeyboardMarkup([BACK_KEYBOARD + TO_TOP_KEYBOARD], resize_keyboard=True, is_persistent=True)
cancel_menu = ReplyKeyboardMarkup([CANCEL_KEYBOARD], resize_keyboard=True)
continue_menu = ReplyKeyboardMarkup([CONTINUE_KEYBOARD], resize_keyboard=True, one_time_keyboard=False, is_persistent=True)
post_menu = ReplyKeyboardMarkup([SEND_CONFIRMATION_KEYBOARD], resize_keyboard=True, one_time_keyboard=True)

main_menu = [
	ReplyKeyboardMarkup(DESIGNER_KEYBOARD, resize_keyboard=True, one_time_keyboard=True, is_persistent=True),
	ReplyKeyboardMarkup(OUTSOURCER_KEYBOARD, resize_keyboard=True, one_time_keyboard=True, is_persistent=True),
	ReplyKeyboardMarkup(SUPPLIER_KEYBOARD, resize_keyboard=True, one_time_keyboard=True, is_persistent=True),
	ReplyKeyboardMarkup(UNCATEGORIZED_KEYBOARD, resize_keyboard=True, one_time_keyboard=True, is_persistent=True),
]

profile_menu = [DESIGNER_PROFILE_KEYBOARD, OUTSOURCER_PROFILE_KEYBOARD, SUPPLIER_PROFILE_KEYBOARD, BACK_KEYBOARD]


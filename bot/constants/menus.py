from telegram import ReplyKeyboardMarkup

from bot.constants.keyboards import DESIGNER_KEYBOARD, SUPPLIER_KEYBOARD, DONE_KEYBOARD, CANCEL_REG_KEYBOARD, \
    SEND_CONFIRMATION_KEYBOARD, SUPPLIER_PROFILE_KEYBOARD, DESIGNER_PROFILE_KEYBOARD, CONTINUE_REG_KEYBOARD, \
    DONE_REG_KEYBOARD, START_KEYBOARD, REGISTRATION_KEYBOARD, PROFILE_KEYBOARD, BACK_KEYBOARD, QUESTIONNAIRE_KEYBOARD
from api.models import Group

# TODO: replace for generate_reply_keyboard func
start_menu = ReplyKeyboardMarkup(
    [START_KEYBOARD], resize_keyboard=True, one_time_keyboard=True)
reg_menu = ReplyKeyboardMarkup(
    [REGISTRATION_KEYBOARD], resize_keyboard=True, one_time_keyboard=True)
done_menu = ReplyKeyboardMarkup(
    [DONE_KEYBOARD], resize_keyboard=True, one_time_keyboard=True)
cancel_reg_menu = ReplyKeyboardMarkup(
    [CANCEL_REG_KEYBOARD], resize_keyboard=True, one_time_keyboard=False)
continue_reg_menu = ReplyKeyboardMarkup(
    [CONTINUE_REG_KEYBOARD + CANCEL_REG_KEYBOARD],
    resize_keyboard=True,
    one_time_keyboard=False,
)
done_reg_menu = ReplyKeyboardMarkup(
    [DONE_REG_KEYBOARD + CANCEL_REG_KEYBOARD],
    resize_keyboard=True,
    one_time_keyboard=False,
)
post_menu = ReplyKeyboardMarkup(
    SEND_CONFIRMATION_KEYBOARD, resize_keyboard=True, one_time_keyboard=True)

main_menu = {
    Group.DESIGNER.value: DESIGNER_KEYBOARD + [PROFILE_KEYBOARD] + [DONE_KEYBOARD],
    Group.SUPPLIER.value: SUPPLIER_KEYBOARD + [PROFILE_KEYBOARD] + [DONE_KEYBOARD],
}

profile_menu = {
    Group.DESIGNER.value: DESIGNER_PROFILE_KEYBOARD + BACK_KEYBOARD,
    Group.SUPPLIER.value: SUPPLIER_PROFILE_KEYBOARD + BACK_KEYBOARD,
}

questionnaire_menu = ReplyKeyboardMarkup(
    QUESTIONNAIRE_KEYBOARD, resize_keyboard=True, one_time_keyboard=False)

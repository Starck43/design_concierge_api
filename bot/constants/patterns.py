from bot.constants.keyboards import PROFILE_KEYBOARD, DESIGNER_PROFILE_KEYBOARD, SUPPLIER_PROFILE_KEYBOARD, \
	DESIGNER_KEYBOARD, BACK_KEYBOARD, SUPPLIER_LIST_KEYBOARD, SUPPLIER_DETAILS_KEYBOARD
from bot.utils import flatten_list

DONE_PATTERN = r'отменить|завершить|закончить|до свидания|всего хорошего|bye|done'
CANCEL_REGISTRATION_PATTERN = r'(отменить|прервать) регистрацию$'
CONTINUE_REGISTRATION_PATTERN = r'продолжить регистрацию$'
REGISTRATION_PATTERN = r'(начать регистрацию)|регистрация|register$'
DONE_REGISTRATION_PATTERN = r'подтвердить регистрацию$'
CANCEL_POST_PATTERN = r'(отменить)(.*пост)'
BACK_PATTERN = r'назад|вернуться'
START_PATTERN = r'начать|старт|start'
SERVICES_PATTERN = r'услуги|список услуг'
COOPERATION_REQUESTS_PATTERN = r'заявки|сотрудничество'

PROFILE_PATTERN = r''+str(PROFILE_KEYBOARD[0])
DESIGNER_PATTERN = r''+flatten_list(DESIGNER_KEYBOARD, delimiter="|")
DESIGNER_PROFILE_PATTERN = r''+flatten_list(DESIGNER_PROFILE_KEYBOARD, delimiter="|")
SUPPLIER_PROFILE_PATTERN = r''+flatten_list(SUPPLIER_PROFILE_KEYBOARD, delimiter="|")
SUPPLIER_LIST_PATTERN = r''+flatten_list(SUPPLIER_LIST_KEYBOARD[0], delimiter="|")
SUPPLIER_DETAILS_PATTERN = r''+flatten_list(SUPPLIER_DETAILS_KEYBOARD[0], delimiter="|")

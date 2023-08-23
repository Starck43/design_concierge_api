from bot.constants.keyboards import (
	PROFILE_KEYBOARD, DESIGNER_KEYBOARD, USER_DETAILS_KEYBOARD, DESIGNER_PROFILE_KEYBOARD, BACK_KEYBOARD, )
from bot.utils import flatten_list


START_PATTERN = r'начать|старт|start|перейти в консьерж'
DONE_PATTERN = r'завершить|закончить|до свидания|всего хорошего|пока|bye|done'
CANCEL_PATTERN = r'отмена|отменить|прервать|остановить'
CONTINUE_PATTERN = r'вперед|продолжить|дальше'
BACK_PATTERN = r'назад|вернуться|в начало'
SUBMIT_PATTERN = r'подтвердить|подтверждаю|согласен'
SERVICES_PATTERN = r'услуги|список услуг'
COOPERATION_REQUESTS_PATTERN = r'заявки|сотрудничество'
CANCEL_POST_PATTERN = r'(отменить)(.*пост)'
START_QUESTIONNAIRE_PATTERN = r'начать анкетирование|start questionnaire'
REPEAT_QUESTIONNAIRE_PATTERN = r'повторить анкетирование|repeat questionnaire'
REGISTRATION_PATTERN = r'(начать|повторить) регистрацию|регистрация|register$'
PROFILE_PATTERN = r'профиль'
EVENTS_PATTERN = r'мероприятия|события'
SANDBOX_PATTERN = r'барахолк|песочниц'
TARIFF_PATTERN = r'тариф'
FAVOURITE_PATTERN = r'избранное'
SETTINGS_PATTERN = r'настройки'
USER_RATE_PATTERN = 'рейтинг|оценка|оценить(.*поставщика)'
ADD_FAVOURITE_PATTERN = 'добавить в избранное'
REMOVE_FAVOURITE_PATTERN = '(убрать|удалить) из избранного'
USER_FEEDBACK_PATTERN = r'отзыв'
SUPPLIERS_SEARCH_PATTERN = r'поиск|отбор|подбор|найти|искать|подобрать|отобрать|отфильтровать'
ACTIVE_ORDERS_PATTERN = r'все заказы|активные заказы'
USER_DETAILS_PATTERN = r'' + USER_RATE_PATTERN + "|" + ADD_FAVOURITE_PATTERN + "|" + REMOVE_FAVOURITE_PATTERN

USER_PROFILE_PATTERN = r'' + flatten_list(DESIGNER_PROFILE_KEYBOARD, exclude=BACK_KEYBOARD, delimiter="|")
DESIGNER_PATTERN = r'' + flatten_list(DESIGNER_KEYBOARD[0:3], exclude=PROFILE_KEYBOARD, delimiter="|")

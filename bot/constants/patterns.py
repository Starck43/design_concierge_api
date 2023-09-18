from bot.constants.keyboards import (
	PROFILE_KEYBOARD, DESIGNER_KEYBOARD, DESIGNER_PROFILE_KEYBOARD, BACK_KEYBOARD,
)
from bot.utils import flatten_list

START_PATTERN = r'начать|старт|start|перейти в консьерж'
DONE_PATTERN = r'завершить|закончить|до свидания|всего хорошего|пока|bye|done'
CANCEL_PATTERN = r'отмена|отменить|прервать|остановить'
CONTINUE_PATTERN = r'вперед|продолжить|дальше'
BACK_PATTERN = r'назад|вернуться|в начало|обратно'
SUBMIT_PATTERN = r'подтвердить|подтверждаю|согласен'
DETAILS_PATTERN = r'открыть|посмотреть'
COOPERATION_REQUESTS_PATTERN = r'заявки|сотрудничество'
CANCEL_POST_PATTERN = r'(отменить)(.*пост)'
START_QUESTIONNAIRE_PATTERN = r'начать анкетирование|start questionnaire'
REPEAT_QUESTIONNAIRE_PATTERN = r'повторить анкетирование|repeat questionnaire'
REGISTRATION_PATTERN = r'(начать|повторить) регистрацию|регистрация|register$'
PROFILE_PATTERN = r'профиль'
TARIFF_PATTERN = r'тариф'
FAVOURITE_PATTERN = r'избранное'
SETTINGS_PATTERN = r'настройки'
USER_RATE_PATTERN = 'рейтинг|оценка|оценить(.*поставщика)'
ADD_FAVOURITE_PATTERN = 'добавить в избранное'
REMOVE_FAVOURITE_PATTERN = '(убрать|удалить) из избранного'
USER_FEEDBACK_PATTERN = r'отзыв'
SUPPLIERS_SEARCH_PATTERN = r'поиск|отбор|подбор|найти|искать|подобрать|отобрать|отфильтровать'
DESIGNER_ORDERS_PATTERN = 'мои(.*заказы)'
PLACED_DESIGNER_ORDERS_PATTERN = 'все|другие|размещенные|текущие|активные(.*заказы)'
OUTSOURCER_ACTIVE_ORDERS_PATTERN = 'в работе|взятые(.*заказы)'
SUSPENDED_ORDERS_PATTERN = 'приостановленные|снятые(.*заказы)'
DONE_ORDERS_PATTERN = 'выполненные|завершенные|закрытые|архивные(.*заказы)'

SERVICES_PATTERN = r'' + '|'.join([
	DESIGNER_ORDERS_PATTERN, PLACED_DESIGNER_ORDERS_PATTERN,
	OUTSOURCER_ACTIVE_ORDERS_PATTERN, DONE_ORDERS_PATTERN
])

USER_DETAILS_PATTERN = r'' + '|'.join([USER_RATE_PATTERN, ADD_FAVOURITE_PATTERN, REMOVE_FAVOURITE_PATTERN])
USER_PROFILE_PATTERN = r'' + flatten_list(DESIGNER_PROFILE_KEYBOARD, exclude=BACK_KEYBOARD, delimiter="|")
DESIGNER_PATTERN = r'' + flatten_list(DESIGNER_KEYBOARD[0:3], exclude=PROFILE_KEYBOARD, delimiter="|")

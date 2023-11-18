from bot.constants.keyboards import (
	PROFILE_KEYBOARD, DESIGNER_KEYBOARD, DESIGNER_PROFILE_KEYBOARD, BACK_KEYBOARD,
)
from bot.utils import flatten_list

START_PATTERN = r'начать|старт|start|перейти в консьерж'
DONE_PATTERN = r'завершить|закончить|до свидания|всего хорошего|пока|bye|done'
CANCEL_PATTERN = r'отмен|отказ|прервать|останов|назад'
CONTINUE_PATTERN = r'вперед|продолжить|дальше'
BACK_PATTERN = r'назад|вернуться|в начало|обратно|наверх|back|start|top'
BACK_TO_TOP_PATTERN = r'в начало|наверх|start|top'
SEND_PATTERN = r'отправить'
SUBMIT_PATTERN = r'подтвердить|подтверждаю|согласен'
DETAILS_PATTERN = r'открыть|посмотреть'
CANCEL_POST_PATTERN = r'(отменить)(.*пост)'
START_QUESTIONNAIRE_PATTERN = r'начать анкетирование|start questionnaire'
REPEAT_QUESTIONNAIRE_PATTERN = r'повторить анкетирование|repeat questionnaire'
REGISTRATION_PATTERN = r'(начать|повторить) регистрацию|регистрация|register$'
PROFILE_PATTERN = r'профиль'
TARIFF_PATTERN = r'тариф'
FAVOURITE_PATTERN = r'избранное'
SETTINGS_PATTERN = r'настройки'
SUPPORT_PATTERN = r'поддержк*|администратор|сообщить|написать|письмо|вопрос|спросить|support|ask|ошибк*'
COOPERATION_REQUESTS_PATTERN = r'сотрудничество'
ADD_FAVOURITE_PATTERN = 'добавить в избранное'
REMOVE_FAVOURITE_PATTERN = '(убрать|удалить) из избранного'
USER_FEEDBACK_PATTERN = r'отзыв'
SUPPLIERS_SEARCH_PATTERN = r'поиск|отбор|подбор|найти|искать|подобрать|отобрать|отфильтровать'
DESIGNER_ORDERS_PATTERN = 'мои(.*заказы)'
PLACED_DESIGNER_ORDERS_PATTERN = '(?:все|другие|размещенные|текущие|активные)(.*заказы)|заказы на бирже'
NEW_DESIGNER_ORDER_PATTERN = '(новый|добавить|создать|разместить) заказ'
OUTSOURCER_ACTIVE_ORDERS_PATTERN = 'в работе|взятые(.*заказы)'
SUSPENDED_ORDERS_PATTERN = '(?:остановленные|снятые)(.*заказы)'
DONE_ORDERS_PATTERN = '(?:выполненные|завершенные|закрытые|архив)(.*заказ)'
MODIFY_ORDER_PATTERN = 'изменить|исправить|редактировать'
REMOVE_ORDER_PATTERN = 'удалить|в архив'

DESIGNER_PATTERN = r'' + flatten_list(DESIGNER_KEYBOARD[0:3], exclude=PROFILE_KEYBOARD, delimiter="|")

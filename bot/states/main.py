from enum import Enum

from bot.constants.keyboards import DESIGNER_KEYBOARD


class MenuState(Enum):
    DONE: str = 'Завершить'
    START: str = 'Основное меню'
    SUPPLIERS_REGISTER: str = 'Реестр поставщиков'
    SERVICES: str = DESIGNER_KEYBOARD[0][1]
    DESIGNER_ORDERS: str = 'Заказы дизайнеров'
    ORDER: str = 'Карточка заказа'
    ADD_ORDER: str = 'Новый заказ'
    MODIFY_ORDER: str = 'Изменение заказа'
    RECOMMEND_USER: str = 'Рекомендовать поставщика'
    DESIGNER_EVENTS: str = 'События'
    PERSONAL_ASSISTANT: str = 'Личный помощник'
    USER_DETAILS: str = "Карточка организации"
    USER_RATE: str = 'Обновить рейтинг'
    USERS_SEARCH: str = 'Подбор поставщика'
    TARIFF_CHANGE: str = 'Изменение тарифа'
    FAVOURITES: str = 'Избранное'
    SUPPLIERS_FAVOURITES: str = 'Избранные поставщики'
    COOP_REQUESTS: str = 'Заявки на сотрудничество'
    UPLOAD_FILES: str = 'Отправка прикрепленных файлов'
    PROFILE: str = 'Карточка профиля'
    MODIFY_PROFILE: str = 'Изменение данных пользователя'
    SETTINGS: str = 'Настройки'
    SUPPORT: str = 'Техподдержка'

    def __str__(self):
        return self.value

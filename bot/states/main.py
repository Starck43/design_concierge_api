from enum import Enum

from bot.constants.keyboards import DESIGNER_KEYBOARD


class MenuState(Enum):
    DONE: str = 'Завершить'
    START: str = 'Основное меню'
    SUPPLIERS_REGISTER: str = 'Реестр поставщиков'
    SERVICES: str = DESIGNER_KEYBOARD[0][1]
    ORDERS: str = 'Заказы дизайнеров'
    ADD_ORDER: str = 'Новый заказ'
    MODIFY_ORDER: str = 'Изменение заказа'
    DESIGNER_EVENTS: str = 'События'
    DESIGNER_SANDBOX: str = 'Барахолка'
    USER_DETAILS: str = "Карточка организации"
    USER_RATE: str = 'Обновить рейтинг'
    SUPPLIERS_SEARCH: str = 'Поиск поставщика'
    TARIFF_CHANGE: str = 'Изменение тарифа'
    FAVOURITES: str = 'Избранное'
    SUPPLIERS_FAVOURITES: str = 'Избранные поставщики'
    COOP_REQUESTS: str = 'Заявки на сотрудничество'
    UPLOAD_FILES: str = 'Отправка прикрепленных файлов'
    PROFILE: str = 'Карточка профиля'
    SETTINGS: str = 'Настройки'
    SUPPORT: str = 'Техподдержка'

    def __str__(self):
        return self.value

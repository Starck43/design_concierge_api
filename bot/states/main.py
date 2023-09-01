from enum import Enum


class MenuState(Enum):
    DONE: str = 'Завершить'
    START: str = 'Основное меню'
    SUPPLIERS_REGISTER: str = 'Реестр поставщиков'
    OUTSOURCER_SERVICES: str = 'Биржа услуг'
    ORDERS: str = 'Заказы дизайнеров'
    DESIGNER_EVENTS: str = 'События'
    DESIGNER_SANDBOX: str = 'Барахолка'
    USER_DETAILS: str = "Карточка организации"
    USER_RATE: str = 'Обновить рейтинг'
    SUPPLIERS_SEARCH: str = 'Поиск поставщика'
    TARIFF_CHANGE: str = 'Изменение тарифа'
    FAVOURITE_CHOICE: str = 'Избранное'
    SUPPLIERS_FAVOURITES: str = 'Избранные поставщики'
    COOP_REQUESTS: str = 'Заявки на сотрудничество'
    UPLOAD_FILES: str = 'Отправка прикрепленных файлов'
    PROFILE: str = 'Профиль пользователя'
    SETTINGS: str = 'Настройки'

    def __str__(self):
        return self.value

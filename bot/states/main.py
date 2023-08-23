from enum import Enum


class MenuState(Enum):
    DONE: str = 'Завершить'
    START: str = 'Основное меню'
    SUPPLIERS_REGISTER: str = 'Реестр поставщиков'
    OUTSOURCER_SERVICES: str = 'Биржа услуг'
    ORDERS: str = 'Заказы дизайнеров'
    DESIGNER_EVENTS: str = 'Мероприятия'
    DESIGNER_SANDBOX: str = 'Барахолка'
    USER_DETAILS: str = "Карточка организации"
    USER_RATE: str = 'Обновить рейтинг'
    SUPPLIERS_SEARCH: str = 'Поиск поставщика'
    PROFILE: str = 'Профиль пользователя'
    TARIFF_CHANGE: str = 'Изменение тарифа'
    FAVOURITE_CHOICE: str = 'Избранное'
    SETTINGS: str = 'Настройки'
    SUPPLIERS_FAVOURITES: str = 'Избранные поставщики'
    SERVICES: str = 'Услуги'
    COOP_REQUESTS: str = 'Заявки на сотрудничество'
    UPLOAD_FILES: str = 'Отправка прикрепленных файлов'

    def __str__(self):
        return self.value

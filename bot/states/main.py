from enum import Enum

from bot.constants.keyboards import DESIGNER_KEYBOARD, DESIGNER_PROFILE_KEYBOARD, SUPPLIER_DETAILS_KEYBOARD
from bot.utils import remove_special_chars


class MenuState(Enum):
    DONE: str = 'Консьерж Сервис: Завершить'
    START: str = 'Консьерж Сервис: Основное меню'
    SUPPLIERS_REGISTER: str = remove_special_chars(DESIGNER_KEYBOARD[0][0])
    DESIGNER_EXCHANGE: str = remove_special_chars(DESIGNER_KEYBOARD[0][1])
    DESIGNER_EVENTS: str = remove_special_chars(DESIGNER_KEYBOARD[1][0])
    DESIGNER_SANDBOX: str = remove_special_chars(DESIGNER_KEYBOARD[1][1])
    SUPPLIER_DETAILS: str = "Карточка организации"
    SUPPLIER_RATE: str = remove_special_chars(SUPPLIER_DETAILS_KEYBOARD[1][0])
    SUPPLIER_SEARCH: str = remove_special_chars(SUPPLIER_DETAILS_KEYBOARD[0][0])
    PROFILE: str = 'Профиль пользователя'
    TARIFF_CHANGE: str = 'Изменение тарифа'
    SUPPLIERS_FAVOURITES: str = remove_special_chars(DESIGNER_PROFILE_KEYBOARD[0][0])
    SERVICES: str = 'Услуги'
    COOP_REQUESTS: str = 'Заявки на сотрудничество'
    UPLOAD_FILES: str = 'Отправка прикрепленных файлов'

    def __str__(self):
        return self.value

from enum import Enum

from bot.constants.keyboards import DESIGNER_KEYBOARD, DESIGNER_PROFILE_KEYBOARD


class MenuState(Enum):
    MAIN_MENU: str = 'Основное меню'
    QUESTIONNAIRE_CAT: str = 'Опросник: категории'
    QUESTIONNAIRE_QUES: str = 'Опросник: вопросы'
    QUESTIONNAIRE_END: str = 'Опросник: завешение опроса'
    QUESTIONNAIRE_CANSEL: str = 'Опросник: выйти'
    SUPPLIERS_REGISTER: str = DESIGNER_KEYBOARD[0][0]
    SUPPLIER_CHOOSING: str = "Карточка организации"
    PROFILE: str = 'Профиль'
    SUPPLIERS_FAVOURITES: str = DESIGNER_PROFILE_KEYBOARD[0][0]
    SERVICES: str = 'Услуги'
    COOP_REQUESTS: str = 'Заявки на сотрудничество'
    NEW_USER: str = 'Регистрация'

    def __str__(self):
        return self.value

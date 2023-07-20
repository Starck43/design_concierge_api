START_KEYBOARD = ["🚀 Перейти в Консьерж сервис"]
DONE_KEYBOARD = ["🏁 Завершить"]
BACK_KEYBOARD = ["🔙 Назад"]
TO_TOP_KEYBOARD = ["🔝 В начало"]
CONFIRM_KEYBOARD = ["Да", "Нет"]
REPEAT_KEYBOARD = ["Повторить операцию"]
CANCEL_KEYBOARD = ["🚫 Отменить"]
SEND_CONFIRMATION_KEYBOARD = [['📦 Отправить', '🚫 Отменить'], ]
CONTINUE_KEYBOARD = [["➡️ Продолжить", "🚫 Отменить"], ]
PAYMENT_KEYBOARD = [["💳 Оплатить", "🚫 Отменить"], ]

START_QUESTIONNAIRE_KEYBOARD = ["🚀 Начать анкетирование"]
REPEAT_QUESTIONNAIRE_KEYBOARD = ["Повторить анкетирование"]
REG_GROUP_KEYBOARD = [["Дизайнер или аутсорсер"], ["Поставщик товаров"]]
START_REG_KEYBOARD = ["Начать регистрацию"]
CANCEL_REG_KEYBOARD = ["🚫 Отменить регистрацию"]
CONTINUE_REG_KEYBOARD = ["➡️ Продолжить регистрацию"]
SUBMIT_REG_KEYBOARD = ["✅ Подтвердить данные"]
SEGMENT_KEYBOARD = ["Премиум/Средний+", "Средний", "Средний-/Эконом"]
PROFILE_KEYBOARD = ["Мой профиль 👤"]

DESIGNER_KEYBOARD = [
	["Реестр поставщиков 👥", "Биржа услуг 🛠"],
	["События ✨", "Барахолка 💰️"],
	["Личный помощник 📠"] + PROFILE_KEYBOARD,
	DONE_KEYBOARD
]

DESIGNER_EXCHANGE_KEYBOARD = [
	["Мои заявки"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

DESIGNER_EVENTS_KEYBOARD = [
	["Календарь событий", "Архив"],
	# ["Местные", "Российские", "Международные"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

DESIGNER_SANDBOX_KEYBOARD = ["Купить", "Продать", "Беседа"]

SUPPLIERS_REGISTER_KEYBOARD = [
	["Подбор поставщика"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

SUPPLIER_DETAILS_KEYBOARD = [
	["Подбор поставщика"],
	["Обновить рейтинг", "Оставить отзыв"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

DESIGNER_PROFILE_KEYBOARD = [
	["♥️️ Избранное", "🚝 Тариф"],
	["⚙️ Настройки"] + BACK_KEYBOARD,
]

OUTSOURCER_KEYBOARD = [
	["Биржа услуг 🛠"],
	["События ✨", "Барахолка 💰️️"],
	["Личный помощник 📠"] + PROFILE_KEYBOARD,
	DONE_KEYBOARD
]

OUTSOURCER_EXCHANGE_KEYBOARD = [
	["В исполнении"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

OUTSOURCER_PROFILE_KEYBOARD = [
	["🚝 Тариф"] + BACK_KEYBOARD,
]

SUPPLIER_KEYBOARD = [
	["👥 Реестр поставщиков"],
	PROFILE_KEYBOARD + DONE_KEYBOARD
]

SUPPLIER_PROFILE_KEYBOARD = [
	["🚝 Тариф"] + BACK_KEYBOARD,
]

UNCATEGORIZED_KEYBOARD = [
	DONE_KEYBOARD
]

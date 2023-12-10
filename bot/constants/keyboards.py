MODIFY_KEYBOARD = ["✍️ Изменить"]
CANCEL_KEYBOARD = ["🚫 Отменить"]
REMOVE_KEYBOARD = ["❌ Удалить"]
REPEAT_KEYBOARD = ["Повторить операцию"]
CONFIRM_KEYBOARD = ["Да", "Нет"]
SUBMIT_REG_KEYBOARD = ["✅ Подтвердить данные"]
BACK_KEYBOARD = ["⬅️ Назад"]
TO_TOP_KEYBOARD = ["⬆️ В начало"]
DONE_KEYBOARD = ["🏁 Завершить"]
REPLY_KEYBOARD = ["Ответить ⤴️"]
SAVE_KEYBOARD = ["✅ Сохранить", '🚫 Отменить']
SEND_CONFIRMATION_KEYBOARD = ['📦 Отправить', '🚫 Отменить']
CONTINUE_KEYBOARD = ["➡️ Продолжить", "🚫 Отменить"]
PAYMENT_KEYBOARD = ["💳 Оплатить", "🚫 Отменить"]
SUPPORT_KEYBOARD = ["Сообщить в поддержку"]
PROFILE_KEYBOARD = ["Мой профиль 👤"]
FAVORITES_KEYBOARD = ["♥️️ Избранное"]

START_BOT_KEYBOARD = ["👉 Перейти в Консьерж сервис"]
START_QUESTIONNAIRE_KEYBOARD = ["💫 Начать анкетирование"]
START_REG_KEYBOARD = ["🆕 Начать регистрацию"]
REG_GROUP_KEYBOARD = ["Архитектор или дизайнер", "Оказание услуг", "Поставщик товаров"]
SEARCH_KEYBOARD = ["🔎 Поиск", "🧹 Очистить фильтр"]
SEARCH_OPTIONS_KEYBOARD = ["🗃 Вид деятельности", "⭐️ Рейтинг", "🎯 Сегмент"]
SEGMENT_KEYBOARD = ["Премиум/Средний+", "Средний", "Средний-/Эконом"]
TARIFF_KEYBOARD = ["Базовый", "Расширенный", "Премиум"]
FAVORITES_ACTIONS_KEYBOARD = ["Добавить в избранное", "Убрать из избранного"]
RATING_KEYBOARD = ["Выставить рейтинг", "Изменить рейтинг"]
ORDER_EXECUTOR_KEYBOARD = ["👁‍🗨 Посмотреть", "✅ Выбрать исполнителем", "❎ Отказать"]
ORDER_ACTIONS_KEYBOARD = [
	"🟢 Разместить заказ", "🔴 Снять заказ", "👍 Принять предложение", "👎 Отклонить предложение",
	"📆 Сдать работу", "✅️ Принять работу", "❎ На доработку", "🏁 Досрочно завершить", "✉️ Контактные данные заказчика"
]
ORDER_RESPOND_KEYBOARD = ["✅️ Откликнуться", "❎ Отозвать отклик", "Открыть ⟩", "Перейти ⟩", "Показать ⟩",
                          "💭 Принять/Отклонить"]

DESIGNER_KEYBOARD = [
	["Реестр поставщиков 🗂", "Биржа услуг 🛠"],
	["Личный помощник 🧰", "События ✨", ],
	PROFILE_KEYBOARD + DONE_KEYBOARD
]

DESIGNER_SERVICES_KEYBOARD = [
	["Заказы на бирже", "Мои заказы"],
	["🔎 Поиск исполнителя"] + BACK_KEYBOARD,
]

OUTSOURCER_SERVICES_KEYBOARD = [
	["Взятые заказы"],
	["Архивные заказы"] + BACK_KEYBOARD,
]

DESIGNER_SERVICES_ORDERS_KEYBOARD = [
	["Новый заказ", "Архивные заказы"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

DESIGNER_AND_OUTSOURCER_SERVICES_KEYBOARD = [
	["Заказы на бирже", "Мои заказы"],
	["Взятые заказы", "Архивные заказы"],
	["🔎 Поиск исполнителя"] + BACK_KEYBOARD,

]

SUPPLIERS_REGISTER_KEYBOARD = [
	["🔎 Поиск поставщика"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

DESIGNER_EVENTS_KEYBOARD = [
	["Календарь событий", "Архив"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

USER_DETAILS_KEYBOARD = [
	["Избранное", "Оставить отзыв"],
	BACK_KEYBOARD + TO_TOP_KEYBOARD,
]

DESIGNER_PROFILE_KEYBOARD = [
	FAVORITES_KEYBOARD + SUPPORT_KEYBOARD,
	BACK_KEYBOARD,
]

OUTSOURCER_KEYBOARD = [
	["Биржа услуг 🛠", "События ✨"],
	["Личный помощник 🧰"] + PROFILE_KEYBOARD,
	DONE_KEYBOARD
]

OUTSOURCER_PROFILE_KEYBOARD = [
	SUPPORT_KEYBOARD + BACK_KEYBOARD,
]

SUPPLIER_KEYBOARD = [
	["👥 Реестр поставщиков"],
	PROFILE_KEYBOARD + DONE_KEYBOARD
]

SUPPLIER_PROFILE_KEYBOARD = [
	SUPPORT_KEYBOARD + BACK_KEYBOARD,
]

UNCATEGORIZED_KEYBOARD = [
	SUPPORT_KEYBOARD,
	DONE_KEYBOARD
]

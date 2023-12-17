from bot.bot_settings import TRADE_GROUP_ID, SANDBOX_GROUP_ID

HELP_CONTEXT = (
	"Используйте `/start` для начала диалога.\n",
	"Используйте `/help` для подсказок.\n",
)

CHAT_GROUPS_DATA = {TRADE_GROUP_ID: "Объявления", SANDBOX_GROUP_ID: "Беседка"}

EXCLUDED_GROUP_FIELDS = [["segment"], ["segment"], ["segment"]]

CAT_GROUP_DATA = [
	{"name": "designers", "title": "Дизайнеры/архитекторы"},
	{"name": "outsourcers", "title": "Специалисты"},
	{"name": "suppliers", "title": "Поставщики"},
]

SEARCH_FIELD_LIST = ["categories", "rating", "segment", "keywords"]
ORDER_STATUS = [
	"снят 🔴", "в поиске исполнителя 🟢", "ожидает ответ от исполнителя ⏳", "заказ в работе 🟠",
	"истек срок ожидания ⚪️", "в стадии приемки ⏳", "завершен 🏁", "досрочно завершен ✔️"
]
ORDER_RELATED_USERS_TITLE = ["Откликнулись на заявку", "Исполнитель заказа"]

ORDER_RESPONSE_MESSAGE_TEXT = [
	"Вы успешно оставили свою заявку.\n"
	"Если работодатель выберет именно Вас, то Вам придет уведомление.",
	"Вы отозвали свою заявку."
]

ORDER_FIELD_DATA = {
	"title": "Заголовок",
	"description": "Описание заказа",
	"price": "Стоимость работ",
	"expire_date": "Дата выполнения"
}

MAX_RATE = 8
RATE_BUTTONS = [("🟩", 0.7), ("🟨", 0.4), "🟧️", "⬜"]
MESSAGE_TYPE = {"info": "❕", "warn": "⚠️", "error": "❗️"}

MONTH_NAME_LIST = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
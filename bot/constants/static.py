HELP_CONTEXT = (
	"Используйте `/start` для начала диалога.\n",
	"Используйте `/help` для подсказок.\n",
)

PROFILE_FIELD_SET = [
	["username", "categories", "main_region", "socials_url", "regions", ],
	["username", "categories", "main_region", "regions", "description", "address", "socials_url", "site_url"],
	["username", "name", "segment", "categories", "main_region", "regions", "description", "address", "socials_url",
	 "site_url"],
]

SUPPLIER_SUBTITLE = ["Специалисты", "Поставщики"]
TARIFF_LIST = ["Базовый", "Расширенный", "Премиум"]
ORDER_STATUS = ["снят", "в поиске", "ожидает подтверждения исполнителем", "заказ в работе", "истек срок ожидания", "в стадии приемки", "завершен", "досрочно завершен"]
ORDER_RELATED_USERS_TITLE = ["Откликнулись на заявку", "Исполнитель заказа"]
NO_ORDERS_MESSAGE_TEXT = {"creator": "❕Пока нет ни одного нового заказа.", "contender": "❕Пока нет новых заказов для вас."}
ORDER_RESPONSE_MESSAGE_TEXT = [
	"Вы успешно оставили свою заявку.\n"
	"Если работодатель выберет именно Вас, то Вам придет уведомление.",
	"Вы отозвали свою заявку."
]
ORDER_REMOVE_MESSAGE_TEXT = ["⚠️ Не удалось удалить заказ на сервере!", "✔️ Ваш заказ успешно удален!"]
ORDER_ERROR_MESSAGE_TEXT = [
	"🚫 Операция недоступна если заказ не активирован!", "🚫 Операция недоступна если заказ завершен!"
]
ORDER_FIELD_SET = {
	"title": "Заголовок",
	"description": "Описание заказа",
	"price": "Стоимость работ",
	"expire_date": "Дата выполнения"
}
MAX_RATE = 8
RATE_BUTTONS = [("🟩", 0.7), ("🟨", 0.4), "🟧️" ,"⬜"]

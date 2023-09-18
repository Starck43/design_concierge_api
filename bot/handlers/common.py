from typing import Union, List, Optional, ValuesView, Tuple, Any

from telegram import Update, Message, ReplyKeyboardMarkup, InlineKeyboardMarkup, CallbackQuery, Bot, helpers, \
	InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID
from bot.constants.common import ORDER_STATUS
from bot.constants.keyboards import BACK_KEYBOARD, ORDER_RESPOND_KEYBOARD
from bot.constants.menus import main_menu, done_menu, back_menu
from bot.constants.messages import (offer_for_registration_message, share_link_message, yourself_rate_warning_message,
                                    show_inline_message)
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	fetch_data, filter_list, generate_inline_keyboard, fetch_user_data, find_obj_in_list, extract_fields,
	match_message_text, dict_to_formatted_text, get_formatted_date, format_output_text
)


async def user_authorization(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[bool]:
	parameters = context.args
	user_data = context.user_data
	user = update.message.from_user

	res = await fetch_user_data(params={"user_id": user.id, "is_rated": "true"})

	if res["data"] is None:
		if res["status_code"] == 404:
			await offer_for_registration_message(update.message)
			if parameters and parameters[0].lower() != "register":
				await create_registration_link(update.message, context)
				return None
			return False
		else:
			text = "Ошибка авторизации."
			await catch_server_error(update.message, context, error=res, text=text)
			return None
	else:
		user_data["details"] = res["data"]
		return True


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE, level: int = -2) -> str:
	""" Переход вверх по меню """
	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	await query.message.delete()

	current_menu = get_menu_item(context)
	current_message = current_menu[1]
	current_inline_message = current_menu[2]
	# удаление с экрана текущих сообщений
	await delete_messages_by_key(context, current_message)
	await delete_messages_by_key(context, current_inline_message)

	# если нажата кнопка Назад, то вернем предыдущее состояние меню, иначе переходим в начальное состояние
	index = level if match_message_text(BACK_KEYBOARD[0], query.message.text) else 0
	prev_menu = extract_menu_item(context, index)
	if not prev_menu:
		init_menu = await init_start_menu(context)
		await delete_messages_by_key(context, "last_message_id")
		await delete_messages_by_key(context, context.chat_data.get("last_message_ids"))
		state = init_menu["state"]

	else:
		state, reply_message, inline_message, markup, inline_markup = prev_menu

		if reply_message:
			reply_message = await query.message.reply_text(
				text=reply_message.text_markdown,
				reply_markup=markup
			)
			update_menu_item(context, message=reply_message)

		if inline_message:
			inline_messages = []
			if not isinstance(inline_message, list):
				inline_message = [inline_message]

			for message in inline_messages:
				markup = inline_markup if inline_markup and len(inline_message) == 1 else message.reply_markup
				message = await query.message.reply_text(
					text=message.text_markdown,
					reply_markup=markup
				)
				inline_messages.append(message)

			update_menu_item(context, inline_messages=inline_messages)

	await delete_messages_by_key(context, "last_message_id")
	await delete_messages_by_key(context, context.chat_data.get("last_message_ids"))
	context.chat_data.pop("local_data", None)  # удалим временные сохраненные значения на предыдущем уровне

	saved_message: Message = context.chat_data.get("saved_message")
	if saved_message:
		if index == 0:
			# если поднимаемся в начало меню, то удалим сообщение "saved_message", если оно было сохранено
			await delete_messages_by_key(context, saved_message)

		else:
			try:
				saved_message = await saved_message.reply_text(
					saved_message.text,
					reply_markup=saved_message.reply_markup
				)
				context.chat_data["last_message_id"] = saved_message.message_id
			except TelegramError:
				pass
			context.chat_data.pop("saved_message")

	return state


def add_menu_item(
		context: ContextTypes.DEFAULT_TYPE,
		state: str,
		message: Message = None,
		inline_messages: Union[Message, List[Message]] = None,
		markup: ReplyKeyboardMarkup = back_menu,
		inline_markup: InlineKeyboardMarkup = None
) -> dict:
	menu = context.chat_data.setdefault("menu", [])
	if inline_messages and not isinstance(inline_messages, list):
		inline_messages = [inline_messages]

	menu_item = {
		"state": state,
		"message": message,
		"inline_message": inline_messages or [],
		"markup": markup,
		"inline_markup": inline_markup
	}
	menu.append(menu_item)

	return menu_item


def update_menu_item(
		context: ContextTypes.DEFAULT_TYPE,
		state: str = None,
		message: Message = None,
		inline_messages: Union[Message, List[Message]] = None,
		markup: ReplyKeyboardMarkup = None,
		inline_markup: InlineKeyboardMarkup = None,
		index: int = -1
) -> Optional[dict]:
	menu = context.chat_data.get("menu", [])

	try:
		menu_item = menu[index]
		if inline_messages and not isinstance(inline_messages, list):
			inline_messages = [inline_messages]

		menu_item.update({
			"state": state or menu_item.get("state"),
			"message": message or menu_item.get("message"),
			"inline_message": inline_messages or menu_item.get("inline_message", []),
			"markup": markup or menu_item.get("markup"),
			"inline_markup": inline_markup or menu_item.get("inline_markup")
		})

	except ValueError:
		return None

	return menu_item


def get_menu_item(context: ContextTypes.DEFAULT_TYPE, index: int = -1) -> Tuple[Any, ...]:
	try:
		chat_data = context.chat_data
		menu = chat_data.get("menu", [])
		return tuple(menu[index].values())

	except IndexError:
		return None, None, None, None, None


def extract_menu_item(context: ContextTypes.DEFAULT_TYPE, index: int = -1) -> Optional[ValuesView]:
	chat_data = context.chat_data
	menu = chat_data.get("menu", None)

	if not menu:
		return None

	try:
		if index < 0:
			index = len(menu) + index
			obj = menu[index]
			chat_data["menu"] = menu[:index + 1]

		else:
			obj = menu[index]
			chat_data["menu"] = menu[0:index + 1]

		return obj.values()

	except ValueError:
		return None


async def init_start_menu(
		context: ContextTypes.DEFAULT_TYPE,
		menu_markup: Optional[ReplyKeyboardMarkup] = main_menu,
		text: str = None,
) -> dict:
	chat_data = context.chat_data
	chat_data["menu"] = []

	message = await context.bot.send_message(
		chat_id=chat_data["chat_id"],
		text=text or '*Выберите интересующий раздел:*',
		reply_markup=menu_markup,
		parse_mode=ParseMode.MARKDOWN_V2
	)

	return add_menu_item(context, MenuState.START, message, [], menu_markup)


async def edit_last_message(
		query: Union[Update, CallbackQuery],
		context: ContextTypes.DEFAULT_TYPE,
		text: str,
		reply_markup: Union[ReplyKeyboardMarkup, InlineKeyboardMarkup] = None
) -> Message:
	""" Вывод на экран измененного inline сообщения, сохраненного в 'last_message_id' """
	chat_data = context.chat_data
	last_message_id = chat_data.get("last_message_id")

	if last_message_id:
		message = await context.bot.edit_message_text(
			text=text,
			chat_id=chat_data.get("chat_id"),
			message_id=last_message_id,
			reply_markup=reply_markup
		)
	else:
		message = await query.message.reply_text(text=text, reply_markup=reply_markup)

	chat_data["last_message_id"] = message.message_id  # сохраним id последнего инлайн сообщения
	return message


async def delete_messages_by_key(context: ContextTypes.DEFAULT_TYPE, message: Union[Message, List[Message], str, None]):
	"""
	Deletes messages based on a given key name from the chat data.
	:param context: The context object containing chat data.
	:param message: The Message or field name of the message or list of messages or message ID.
	"""
	chat_id = context.chat_data.get("chat_id")
	if not message or not chat_id:
		return

	if isinstance(message, Message):
		message = [message]

	if isinstance(message, list):
		message_ids = [msg.message_id for msg in message if isinstance(msg, Message)]
		try:
			for message_id in message_ids:
				await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
		except TelegramError:
			pass
		return

	message_id = context.chat_data.get(message)
	if not message_id:
		context.chat_data.pop(message, None)
		return

	if isinstance(message_id, int):
		try:
			await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
		except TelegramError:
			pass

	try:
		if isinstance(message_id, dict):
			for value in message_id.values():
				await context.bot.delete_message(chat_id=chat_id, message_id=value)

		if isinstance(message_id, list):
			for value in reversed(message_id):
				await context.bot.delete_message(chat_id=chat_id, message_id=value)

	except TelegramError:
		pass

	del context.chat_data[message]


def search_message_by_data(message: Message, substring: str, exception: str = "") -> Optional[int]:
	"""
	Checks for the presence of a button with the specified substring in the callback_data
	of the inline_keyboard buttons of a message.
	Args:
		message: The message object containing the inline_keyboard.
		substring: The substring to search for in the callback_data of the buttons.
		exception: An exception where the button should not match the condition.
	Returns:
		Message ID if a button with the specified substring is found and does not match the exception.
	"""
	if hasattr(message, 'reply_markup') and hasattr(message.reply_markup, 'inline_keyboard'):
		inline_keyboard = message.reply_markup.inline_keyboard
		for row in inline_keyboard:
			for button in row:
				callback_data = str(button.callback_data)
				if substring in callback_data and (not exception or exception not in callback_data):
					return message.message_id
	return None


def get_order_status(order: dict) -> Tuple[str, str]:
	date_string, expire_date, current_date = get_formatted_date(order["expire_date"])
	is_valid = not expire_date or current_date <= expire_date

	if order["status"] == 0:
		order_status = ORDER_STATUS[0]
	elif order["status"] == 1:
		if not is_valid:
			order_status = ORDER_STATUS[4]
		elif order["executor"]:
			order_status = ORDER_STATUS[3]
		else:
			order_status = ORDER_STATUS[1]
	else:
		order_status = ORDER_STATUS[2]

	return order_status, date_string


def check_user_in_groups(groups: List[int], allowed_codes: Union[str, List[str]]) -> bool:
	""" Проверяем у пользователя принадлежность к одной из групп через кодовые обозначения
	Args:
		groups: группы пользователя в виде списка от 0 до 2.
		allowed_codes: проверяемые коды групп, где:
			'D' - Designer, 'O' - Outsourcer, 'DO' - Designer + Outsourcer, 'S' - Supplier

	Returns:
		True - если пользователь принадлежит одной из кодовых групп or False, если нет совпадений

	Examples:
		check_user_in_groups([0,1], "S") # False \n
		check_user_in_groups([0,1], ["D", "S"]) # True
	"""

	if not groups:
		return False

	user_role = Group.get_groups_code(groups)
	if user_role == "U":
		return False

	if isinstance(allowed_codes, str):
		allowed_codes = [allowed_codes]

	return any(role in allowed_codes for role in user_role)


async def show_user_orders(
		message: Message,
		orders: list,
		user_role: str,
		user_id: Optional[int] = None,
		title: str = None,
		reply_markup: Optional[ReplyKeyboardMarkup] = back_menu
) -> Tuple[Optional[Message], Optional[Union[Message, List[Message]]]]:
	""" Вывод на экран списка заказов пользователя по его id.:

		Args:
			message: объект с сообщением,
			orders: заказы дизайнера,
			user_role: флаг указывающий на то, что текущий пользователь есть автор заказов,
			user_id: id текущего пользователя,
			title: заголовок для сообщений,
			reply_markup: клавиатура для reply message.
		Returns:
			Кортеж (Reply message, Inline messages)
	 """

	if not orders:
		if user_role == "creator":
			# добавим кнопку для размещения нового заказа для дизайнера
			message_text = "❕Пока нет ни одного нового заказа."
		elif user_role == "receiver":
			message_text = "❕Пока нет новых заказов по вашему профилю."
		else:
			message_text = "❕Пока пусто."

		reply_message = await message.reply_text(message_text, reply_markup=reply_markup)

		return reply_message, None

	if user_role == "creator":
		subtitle = "Мои заказы"
		order_button_text = "Показать"
		callback_prefix = "order"

	elif user_role == "viewer":
		subtitle = "Активные заказы на бирже"
		order_button_text = "Подробнее"
		callback_prefix = "order"

	elif user_role == "receiver":
		subtitle = "Размещенные заказы на бирже"
		order_button_text = ORDER_RESPOND_KEYBOARD[0]
		callback_prefix = "respond_order"

	elif user_role == "executor":
		subtitle = "Завершенные заказы"
		order_button_text = "Открыть"
		callback_prefix = "order"

	else:
		return None, None

	reply_message = await message.reply_text(
		f'*{title or subtitle}:*\n',
		reply_markup=reply_markup
	)
	inline_messages = []

	for index, order in enumerate(orders, 1):
		responded_user, _ = find_obj_in_list(order["responding_users"], {"id": user_id})
		if responded_user and user_role == "receiver":
			order_button_text = ORDER_RESPOND_KEYBOARD[1]

		order_button = InlineKeyboardMarkup([[InlineKeyboardButton(
			text=order_button_text,
			callback_data=f'{callback_prefix}_{order["id"]}',
		)]])

		inline_message_text = format_output_text(f'{index}', order["title"]+"\n", value_tag="`", default_sep=".")

		order_status, date_string = get_order_status(order)
		if not user_role == "creator":
			order_status = ""

		if date_string:
			inline_message_text += f'\nсрок реализации: _{date_string}_'

		if order_status:
			inline_message_text += f'\nстатус: _{order_status}_'

		await show_inline_message(
			message,
			text=inline_message_text,
			inline_markup=order_button,
			inline_messages=inline_messages
		)

	return reply_message, inline_messages


def set_priority_group(context: ContextTypes.DEFAULT_TYPE) -> int:
	""" Выбор приоритетной группы, если пользователь относится к разным типам категорий """
	user_details = context.user_data["details"]
	user_groups = user_details.get("groups", [])

	if not user_groups and user_details["categories"]:
		category_list = []
		if isinstance(user_details["categories"], dict):
			category_list = user_details["categories"].values()

		if isinstance(user_details["categories"], list):
			category_list = user_details["categories"]

		user_groups = extract_fields(category_list, field_names="group")

	group = min(user_groups, default=3)
	context.user_data["priority_group"] = Group.get_enum(group)

	return group


def get_user_rating_data(context: ContextTypes.DEFAULT_TYPE, user: dict) -> Tuple[dict, dict]:
	""" Возвращаем вопросы для анкетирования, подробный рейтинг в виде объекта и в виде строки """
	rating = user.get("average_rating", {})
	group = max(user.get("groups"))
	rating_questions = context.bot_data["rating_questions"][group - 1] if group else {}

	return rating_questions, rating


def build_inline_username_buttons(users: List[dict]) -> InlineKeyboardMarkup:
	""" Вспомогательная функция для создания инлайн кнопок с именем пользователя и его рейтингом """
	inline_keyboard = generate_inline_keyboard(
		users,
		callback_data="id",
		item_key="username",
		item_prefix=["⭐️", "total_rate"],
		callback_data_prefix="user_"
	)

	return inline_keyboard


async def check_required_user_group_rating(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Optional[bool]:
	chat_data = context.chat_data
	selected_user = chat_data.get("selected_user")
	rating_questions = context.bot_data.get("rating_questions")

	if not selected_user or not rating_questions:
		return None

	rates, _ = find_obj_in_list(chat_data["user_ratings"], {"receiver_id": selected_user["id"]})
	group = max(selected_user["groups"])
	questions_count = len(rating_questions[group - 1].items())
	questions_rated_count = len(rates.items()) - 1 if rates else 0

	if group == 1 and questions_rated_count < 2 or group == 2 and questions_rated_count < 6:
		message = await message.reply_text(
			f"*Необходимо оценить все критерии!*\n"
			f"Отмечено: _{questions_rated_count}_ из _{questions_count}_",
			# reply_markup=continue_menu
		)
		chat_data["last_message_id"] = message.message_id
		return True

	return False


async def update_user_data(message: Message, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> Optional[dict]:
	""" Получаем с сервера и обновляем сохраненные данные пользователя с user_id в контексте """
	chat_data = context.chat_data

	params = {"related_user": context.user_data["details"]["id"]}
	res = await fetch_user_data(user_id, params=params)
	supplier_data = res["data"]

	if supplier_data:
		chat_data["selected_user"] = supplier_data
		chat_data["suppliers"].update({user_id: supplier_data})

		# удалим всех поставщиков из сохраненных в cat_users
		cat_users = chat_data.get("cat_users", {})
		cat_ids = extract_fields(supplier_data["categories"], "id")
		[cat_users[cat_id].clear() for cat_id in cat_ids if cat_id in cat_users]

		# обновим сохраненное состояние со списком поставщиков через inline_markup в menu
		selected_cat = chat_data.get("selected_cat", {})
		users = await load_cat_users(message, context, selected_cat.get("id"))
		inline_markup = build_inline_username_buttons(users)
		if inline_markup:
			prev_menu = chat_data["menu"][-2]
			prev_menu["inline_markup"] = inline_markup

	return supplier_data


async def update_ratings(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Optional[List[dict]]:
	user_id = context.user_data["details"]["user_id"]

	data = context.chat_data["user_ratings"]
	res = await fetch_user_data(user_id, "/update_ratings", data=data, method="POST")
	if res["status_code"] == 304:
		await yourself_rate_warning_message(message)

	elif res["error"]:
		res.setdefault("request_body", data)
		text = "Ошибка сохранения результатов анкетирования"
		await catch_server_error(message, context, error=res, text=text)

	return res["data"]


async def load_cat_users(message: Message, context: ContextTypes.DEFAULT_TYPE, cat_id: str) -> Optional[List[dict]]:
	if not cat_id:
		return None

	chat_data = context.chat_data
	cat_users = chat_data.get("cat_users", {})
	if not cat_users.get(cat_id):
		res = await fetch_user_data(params={"category": cat_id})
		if res["error"]:
			text = f'Ошибка получения списка поставщиков!'
			await catch_server_error(message, context, error=res, text=text, reply_markup=back_menu)
			return None

		cat_users[cat_id] = res["data"]

	return cat_users[cat_id]


async def load_categories(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		group: Union[int, list] = None,
		related_users: Union[None, str, int] = "all",
):
	params = {"group": group}
	if related_users:
		params["related_users"] = related_users
	res = await fetch_data("/categories", params=params)

	if res["error"]:
		text = "Ошибка загрузки списка категорий"
		await catch_server_error(
			message,
			context,
			error=res,
			text=text,
			reply_markup=done_menu,
			auto_send_notification=False
		)

	return res["data"]


async def load_users_in_category(message: Message, context: ContextTypes.DEFAULT_TYPE, cat_id: int):
	res = await fetch_user_data(params={"category": cat_id})
	if not res["data"]:
		text = f"Ошибка загрузки пользователей для категории {cat_id} через api"
		await catch_server_error(message, context, error=res, text=text)

	return res["data"]


async def load_user(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: int,
		designer_id: Optional[int] = None,
) -> Tuple[Optional[dict], Optional[Message]]:
	params = {"related_user": designer_id} if designer_id is not None else {}
	res = await fetch_user_data(user_id, params=params)
	data: dict = res["data"]
	reply_message = None

	if data is None:
		text = "Ошибка чтения данных пользователя."
		reply_message = await catch_server_error(message, context, error=res, text=text)

	if data:
		data.setdefault("name", data["username"])

	return data, reply_message


async def load_regions(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[list], Optional[list]]:
	res = await fetch_data("/regions")
	if not res["data"]:
		text = "Ошибка загрузки регионов через api"
		await catch_server_error(
			message,
			context,
			error=res,
			text=text,
			reply_markup=done_menu,
			auto_send_notification=False
		)
		return None, None

	return res["data"], filter_list(res["data"], "in_top", 1)


async def load_orders(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		order_id: int = "",
		params: dict = None
) -> Union[list, dict, None]:
	chat_data = context.chat_data
	orders = chat_data.get("orders", {})

	# попытка найти заказ по id в загруженном ранее списке заказов
	if order_id and orders:
		data = orders.get(order_id)
		if data:
			return data

	res = await fetch_data(f"/orders/{order_id}", params=params)
	data = res["data"]

	if res["error"]:
		text = f'Ошибка загрузки заказ{"а" if order_id else "ов"}'
		await catch_server_error(message, context, error=res, text=text)

	# сохраним в памяти полученные с сервера заказы в виде объектов с ключом order.id
	elif data and isinstance(data, list):
		chat_data["orders"] = {item["id"]: item for item in data}

	return data


async def update_order(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		order_id: int,
		params: dict = None,
		data: dict = None
) -> Optional[dict]:
	res = await fetch_data(f'/orders/{order_id}', params=params, data=data, method="POST")
	if res["error"]:
		res.setdefault("request_body", data)
		text = f'Ошибка обновления данных заказа (ID:{order_id})'
		await catch_server_error(message, context, error=res, text=text)
		return None

	context.chat_data["orders"][order_id] = res["data"]

	return res["data"]


async def load_rating_questions(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
) -> Tuple[Optional[list], str]:
	res = await fetch_data("/rating/questions/")
	if not res["data"]:
		text = "Ошибка загрузки вопросов для рейтинга"
		await catch_server_error(
			message,
			context,
			error=res,
			text=text,
			reply_markup=done_menu,
			auto_send_notification=False
		)
	return res["data"]


async def load_rating_authors(message: Message, context: ContextTypes.DEFAULT_TYPE, receiver_id: int) -> list:
	res = await fetch_data(f"/rating/{receiver_id}/authors/")
	if res["status_code"] != 200:
		text = "Ошибка загрузки списка голосовавших"
		await catch_server_error(message, context, error=res, text=text)

	return res["data"]


async def load_user_field_names(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		params: dict = None
) -> Tuple[Optional[list], str]:
	res = await fetch_data("/user_field_names", params=params or {})
	if not res["data"]:
		text = "Ошибка загрузки названий полей пользователя"
		await catch_server_error(message, context, error=res, text=text)

	return res["data"]


def rates_to_string(rates: dict, questions: dict, rate_value: int = 8) -> str:
	if not rates or not questions:
		return ""

	result = ""
	for key, val in rates.items():
		if val is None:
			continue

		name = questions.get(key)
		if not name:
			continue

		rate = min(round(val), rate_value)
		level = rate / rate_value

		if level > 0.7:
			symbol = "🟩"
		elif level >= 0.5:
			symbol = "🟨"
		else:
			symbol = "🟧️"

		empty_rate = "⬜" * (rate_value - rate)
		result += f"{name} ({rate}/{rate_value}):\n{symbol * rate}{empty_rate}\n"

	return result


async def is_user_chat_member(bot: Bot, user_id: int, chat_id: Union[str, int]) -> bool:
	""" Проверка наличия пользователя в группе или канале """
	try:
		member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
		return bool(member)
	except TelegramError:
		return False


async def invite_user_to_chat(
		update: Union[Update, CallbackQuery],
		user_id: int,
		chat_id: Union[str, int],
		text: str = None,
		is_group_chat: bool = False,
) -> bool:
	""" Добавляем пользователя в чат (канал/группа) """

	chat_variants = ["каналу", "группе"]
	chat_variant_text = chat_variants[int(is_group_chat)]
	bot = update.get_bot()

	try:
		await bot.approve_chat_join_request(user_id=user_id, chat_id=chat_id)

	except TelegramError:
		pass

	# Проверяем принадлежность пользователя к чату
	is_member = await is_user_chat_member(bot, user_id, chat_id=chat_id)
	if not is_member:
		join_link = await bot.export_chat_invite_link(chat_id=chat_id)
		join_button = generate_inline_keyboard(
			[f'Присоединиться к {chat_variant_text}'],
			url=join_link,
		)
		await update.message.reply_text(
			text=text or "Присоединяйтесь к нашему каналу Консьерж для Дизайнера",
			reply_markup=join_button
		)

	return is_member


async def create_start_link(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Отправляем сообщение с ссылкой для начала диалога
	url = helpers.create_deep_linked_url(context.bot.username, "start")

	await share_link_message(
		message,
		link=url,
		link_text="Ссылка на Консьерж Сервис",
		text="Перейдите по ссылке для запуска Консьерж для дизайнера"
	)

	return url


async def create_registration_link(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Создаем ссылку для регистрации
	url = helpers.create_deep_linked_url(context.bot.username, "register")

	await share_link_message(
		message,
		link=url,
		link_text="Ссылка на регистрацию",
		text="Ссылка на регистрацию в Консьерж для дизайнеров"
	)

	return url


async def create_questionnaire_link(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Создаем ссылку для анкетирования
	url = helpers.create_deep_linked_url(context.bot.username, "questionnaire")

	await share_link_message(
		message,
		link=url,
		link_text="Ссылка на анкетирование",
		text="Для составления рейтинга поставщиков, предлагаем пройти анкетирование."
	)

	return url


async def catch_server_error(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		error: dict,
		text: str = "",
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
		auto_send_notification: bool = True,
) -> Message:
	user = message.chat
	error_data = {
		"error_text": error.get("error", "Неизвестная ошибка"),
		"error_code": error.get("status_code", "unknown"),
		"url": error.get("url", ""),
		"body": error.get("request_body", {})
	}

	log.info('User {} got server error {} on request {}: "{}"'.format(
		user.id, error_data["error_code"], error_data["url"], error_data["error_text"]
	))

	error_title = text or f'{error_data["error_code"]}: {error_data["error_text"]}\n'
	if auto_send_notification:
		await send_error_to_admin(message, context, error=error_data, text=error_title)
		error_text = "Администратор уже проинформирован о Вашей проблеме.\nПопробуйте повторить или зайдите позже."
		markup = generate_inline_keyboard(["Отправить"], callback_data="send_error")

	else:
		error_text = "Просьба поделиться проблемой с администратором Консьерж Сервис."
		markup = reply_markup

	reply_message = await message.reply_text(
		f'Что-то пошло нет так!\n'
		f'*{error_title}*\n\n'
		f'{error_text}.\n\n'
		f'Приносим свои извинения, {user.first_name}',
		reply_markup=markup
	)

	return reply_message


async def send_error_to_admin(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		error: dict,
		text: Union[str, dict] = ""
) -> None:
	user = message.from_user
	user_details = context.user_data.get('details', {
		'user_id': user.id,
		'username': user.username,
		'name': user.full_name,
	})

	chat_data = context.chat_data
	error_data = {
		"chat_id": chat_data["chat_id"],
		"bot_status": chat_data["status"],
		"current_state": chat_data["menu"][-1]["state"],
		"reply_message": chat_data["menu"][-1]["message"].text,
	}
	error_data.update(error)

	if isinstance(text, dict):
		title_text = dict_to_formatted_text(text)
	elif not isinstance(text, str):
		title_text = str(text)
	else:
		title_text = text

	error_text = dict_to_formatted_text(error_data)
	user_text = dict_to_formatted_text(user_details)

	# TODO: Добавить функционал для логирования ошибок на сервере
	await context.bot.send_message(
		chat_id=ADMIN_CHAT_ID,
		text=f'*Сообщение для администратора!*\n\n'
		     f'_{title_text}_\n'
		     f'`\n{error_text}`\n\n'
		     f'*User info:*\n'
		     f'`\n{user_text}`\n'
	)


async def send_error_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# TODO: Необходимо протестировать!!!
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data
	error_code = str(chat_data["status_code"])
	error_message = {
		error_code: chat_data.get("error", "unknown"),
		"url": chat_data.get("api_url", "unknown"),
	}

	# sending error message to admin
	await send_error_to_admin(update.message, context, error_message)

	# sending error message to user
	user_chat_id = update.effective_user.id
	error_text = f"{update.effective_user.full_name}, спасибо за обратную связь!\n" \
	             f"Сообщение уже отправлено администратору Консьерж Сервис\n" \
	             f"Приносим свои извинения за предоставленные неудобства."
	await context.bot.send_message(chat_id=user_chat_id, text=error_text)

from asyncio import sleep
from typing import Union, List, Optional, Tuple, Callable, Literal

from telegram import (
	Update, Message, ReplyKeyboardMarkup, InlineKeyboardMarkup, CallbackQuery, Bot, helpers, InlineKeyboardButton
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID
from bot.constants.keyboards import BACK_KEYBOARD, ORDER_EXECUTOR_KEYBOARD, ORDER_RESPOND_KEYBOARD, SEGMENT_KEYBOARD
from bot.constants.menus import main_menu, done_menu, back_menu
from bot.constants.messages import (
	offer_for_registration_message, share_link_message, place_new_order_message, send_unknown_question_message
)
from bot.constants.patterns import BACK_PATTERN, BACK_TO_TOP_PATTERN, SUPPORT_PATTERN
from bot.constants.static import MESSAGE_TYPE, CAT_GROUP_DATA, ORDER_STATUS, ORDER_RELATED_USERS_TITLE
from bot.entities import TGMessage
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	fetch_data, filter_list, generate_inline_markup, fetch_user_data, find_obj_in_dict, extract_fields,
	match_query, dict_to_formatted_text, get_formatted_date, format_output_text, update_inline_markup, list_to_dict
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
			if res["status_code"] == 503:
				text = "Ошибка соединения с сервером."
			await update.message.reply_text(f'❗️{text}\nПопробуйте зайти в Консьерж Сервис повторно!')
			await send_error_to_admin(update.message, context, error=res, text=text)
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

	current_menu = prepare_current_section(context)
	current_message = current_menu[1]
	current_inline_message = current_menu[2]
	# удаление с экрана текущих сообщений
	await delete_messages_by_key(context, current_message)
	await delete_messages_by_key(context, current_inline_message)

	# если нажата кнопка Назад, то вернем предыдущее состояние меню, иначе переходим в начальное состояние
	index = level if match_query(BACK_KEYBOARD[0], query.message.text) else 0
	prev_menu = pop_section(context, index)
	if not prev_menu:
		await delete_messages_by_key(context, "last_message_id")
		await delete_messages_by_key(context, context.chat_data.get("last_message_ids"))
		state = MenuState.START

	else:
		state, reply_message, inline_message, markup, inline_markup = prev_menu

		if reply_message:
			reply_message = await query.message.reply_text(
				text=reply_message.text_markdown,
				reply_markup=markup
			)
			update_section(context, message=reply_message)

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

			update_section(context, inline_messages=inline_messages)

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


async def go_back_section(
		update: Union[Update, CallbackQuery],
		context: ContextTypes.DEFAULT_TYPE,
		command: Literal["back", "top"] = None,
		level: int = -1
) -> str:
	""" Возврат к предыдущей секции или переход в начало """
	query = update.callback_query
	chat_data = context.chat_data

	if query:
		await query.answer()
	else:
		query = update
		try:
			await query.message.delete()  # удалим текущее сообщение после нажатия на кнопку
		except TelegramError:
			pass

	query_message = command or query.message.text
	# если сообщение касается техподдержки
	if match_query(SUPPORT_PATTERN, query_message):
		return await message_for_admin_callback(update, context)

	# или если сообщение не связано с возвратом наверх, то будем считать, что это неизвестный вопрос
	elif not match_query(BACK_PATTERN, query_message):
		section = get_section(context)
		await send_unknown_question_message(query.message, context, reply_markup=section["reply_markup"])
		return section["state"]

	current_section = pop_section(context)  # удалим секцию из навигации
	leave_local_messages = current_section.get("leave_local_messages", False)
	if not leave_local_messages:
		await delete_messages_by_key(context, "temp_messages")
		await delete_messages_by_key(context, "warn_message_id")
		await delete_messages_by_key(context, "last_message_id")
		await delete_messages_by_key(context, "last_message_ids")
	if current_section:
		await delete_messages_by_key(context, current_section.get("messages"))
	chat_data["local_data"] = {}  # обнулим временные сохраненные значения на предыдущем уровне

	# если нажата кнопка "В начало", то присвоим нулевой индекс
	if not current_section or match_query(BACK_TO_TOP_PATTERN, query_message) or len(chat_data["sections"]) == 1:
		section_index = 0
	else:
		section_index = level
	back_section = get_section(context, section_index)

	# print("back section: \n", back_section)
	# если необходимо перейти в начало меню или не найден уровень раздела для возврата
	if section_index == 0 or not back_section:
		section = await init_start_section(context, state=MenuState.START)
		return section["state"]

	state = back_section.get("state", None)
	leave_messages = back_section.get("leave_messages", False)
	callback = back_section.get("callback")

	if leave_messages:
		back_message = await query.message.reply_text(BACK_KEYBOARD[0], reply_markup=back_section["reply_markup"])
		back_section["messages"].append(back_message.message_id)
		return state

	if callback:  # если указан колбэк, то перейдем по нему, установив флаг возврата
		back_section["go_back"] = True
		return await callback(update, context)

	# если нет колбэка, но есть сохраненные TGMessage сообщения у раздела ниже, то выведем все не пустые
	reply_markup = back_section.get("reply_markup", None)
	tg_messages = []
	for message in back_section.get("messages", []):
		if isinstance(message, TGMessage) and message.text:
			_message = await update.message.reply_text(
				f'*{message.text.upper()}*' if not message.reply_markup and reply_markup else message.text,
				reply_markup=message.reply_markup or reply_markup
			)
			# единожды добавим к сообщению без reply_markup нижнюю клавиатуру
			if not message.reply_markup and reply_markup:
				reply_markup = None
			tg_messages.append(TGMessage.create_message(_message))

	# обновим id сообщений, которые показали в текущем разделе
	back_section["messages"] = tg_messages

	return state


async def prepare_current_section(context: ContextTypes.DEFAULT_TYPE, leave_messages: bool = False) -> dict:
	""" Получение и подготовка данных из последнего выбранного раздела перед переходом в новый """
	current_section = get_section(context).copy()
	is_back = current_section.get("go_back", False)

	# если переходим в следующий раздел, а не возвращаемся назад
	if not is_back:
		update_section(context, leave_messages=leave_messages)

		await delete_messages_by_key(context, "warn_message_id")
		await delete_messages_by_key(context, "last_message_id")
		await delete_messages_by_key(context, "last_message_ids")

		current_section["query_message"] = None  # если переходим ниже, то query_message вначале должен быть пустым
		if not leave_messages:  # если разрешаем удалить сообщения после перехода в новый раздел
			messages = current_section.get("messages", [])
			await delete_messages_by_key(context, messages)  # удалим все сообщения с экрана на текущем уровне

	return current_section


def add_section(
		context: ContextTypes.DEFAULT_TYPE,
		state: str,
		query_message: str = None,
		messages: Union[Message, List[Message], List[int]] = None,
		callback: Callable = None,
		leave_local_messages: bool = False,
		save_full_messages: bool = True,
		**kwargs
) -> dict:
	chat_data = context.chat_data
	chat_data.setdefault("sections", [])
	current_section = get_section(context)
	is_back = current_section.get("go_back", False)

	_messages = TGMessage.create_list(messages, only_ids=bool(callback) or not save_full_messages)

	section = {
		"state": state,
		"query_message": query_message,
		"messages": _messages,
		"reply_markup": None,
		"callback": callback,
		**kwargs
	}

	if is_back:
		current_section.pop("go_back", None)
		chat_data["sections"][-1].update(section)
	else:
		chat_data["sections"].append(section)

	return section


def get_section(context: ContextTypes.DEFAULT_TYPE, section_index: int = -1) -> dict:
	context.chat_data.setdefault("sections", [])
	try:
		return context.chat_data["sections"][section_index]
	except IndexError:
		return {}


def update_section(context: ContextTypes.DEFAULT_TYPE, section_index: int = -1, **kwargs) -> Optional[dict]:
	context.chat_data.setdefault("sections", [])
	section = get_section(context, section_index)

	if not section:
		return None

	section.update(**kwargs)
	return section


def pop_section(context: ContextTypes.DEFAULT_TYPE, section_index: int = -1) -> Optional[dict]:
	chat_data = context.chat_data
	sections = chat_data.get("sections")

	if not sections:
		return None

	try:
		section = sections.pop(section_index)
		return section

	except IndexError:
		return None


async def init_start_section(
		context: ContextTypes.DEFAULT_TYPE,
		state: str,
		text: str = None,
) -> dict:
	chat_data = context.chat_data
	chat_data["sections"] = []
	group = context.user_data["priority_group"].value
	reply_markup = main_menu[group]

	message = await context.bot.send_message(
		chat_id=chat_data["chat_id"],
		text=text or '*Выберите интересующий раздел:*',
		reply_markup=reply_markup
	)

	return add_section(context, state, messages=message, reply_markup=reply_markup)


async def edit_or_reply_message(
		context: ContextTypes.DEFAULT_TYPE,
		text: str,
		reply_markup: Union[ReplyKeyboardMarkup, InlineKeyboardMarkup] = None,
		message: Union[Message, int] = None,
		delete_before_reply: Union[bool, int] = False,
		return_only_id: bool = True,
		message_type: Literal["info", "warn", "error", None] = None,
		lifetime: Literal[0, 1, 2, 3, 4, 5] = 0
) -> Union[Message, int, None]:
	""" Outputs a modified message or creates a new one """

	chat_id = context.chat_data["chat_id"]
	if message_type:
		text = MESSAGE_TYPE.get(message_type, "") + " " + text

	if delete_before_reply and isinstance(delete_before_reply, int):
		try:
			await context.bot.delete_message(chat_id=chat_id, message_id=delete_before_reply)
		except TelegramError:
			pass

	if message:
		message_id = message.message_id if isinstance(message, Message) else message
		try:
			if delete_before_reply and isinstance(delete_before_reply, bool):
				raise TelegramError

			message = await context.bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=text,
				reply_markup=reply_markup
			)

		except TelegramError:
			try:
				await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
			except TelegramError:
				pass
			message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

	else:
		message = await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

	if lifetime:
		await sleep(lifetime)
		await message.delete()
	else:
		return message.message_id if return_only_id else message


async def delete_messages_by_key(context: ContextTypes.DEFAULT_TYPE, message: Union[Message, List[Message], str, None]):
	"""
	Deletes messages based on a given key name from the chat data.
	:param context: The context object containing chat data.
	:param message: The Message or field name of the message or list of messages or message ID.
	"""
	chat_id = context.chat_data.get("chat_id")
	if not message or not chat_id:
		return

	if isinstance(message, str):
		instance = context.chat_data.pop(message, None)
		if not instance:
			return

		if isinstance(instance, int):
			try:
				await context.bot.delete_message(chat_id=chat_id, message_id=instance)
			except TelegramError:
				pass

		elif isinstance(instance, dict):
			for value in instance.values():
				if value is not None and (
						isinstance(value, int) or isinstance(value, TGMessage) or isinstance(value, Message)
				):
					try:
						await context.bot.delete_message(chat_id, value if isinstance(value, int) else value.message_id)
					except TelegramError:
						pass

		elif isinstance(instance, list):
			for value in reversed(instance):
				try:
					await context.bot.delete_message(chat_id=chat_id, message_id=value)
				except TelegramError:
					pass

	elif isinstance(message, int):
		try:
			await context.bot.delete_message(chat_id=chat_id, message_id=message)

		except TelegramError:
			pass

	elif not isinstance(message, list):
		message = [message]

	if isinstance(message, list):
		# если в массиве числа, а не объекты классов
		for msg in reversed(message):
			if isinstance(msg, int):
				message_id = msg
			elif isinstance(msg, Message) or isinstance(msg, TGMessage):
				message_id = msg.message_id
			else:
				continue

			try:
				await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
			except TelegramError:
				pass


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
	if message.reply_markup:
		inline_keyboard = message.reply_markup.inline_keyboard
		for row in inline_keyboard:
			for button in row:
				callback_data = str(button.callback_data)
				if substring in callback_data and (not exception or exception not in callback_data):
					return message.message_id
	return None


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


async def regenerate_inline_keyboard(
		message: Message,
		active_value: str,
		button_type: Literal["checkbox", "radiobutton", "rate"]
) -> None:
	""" Отметка выбранной кнопки инлайн клавиатуры """

	keyboard = message.reply_markup.inline_keyboard
	inline_markup = update_inline_markup(keyboard, active_value, button_type)
	await message.edit_reply_markup(inline_markup)


async def generate_categories_list(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		groups: Union[list, int] = None,
		checked_callback_data: list = None,
		button_type: Optional[Literal["checkbox", "radiobutton"]] = None
) -> Optional[InlineKeyboardMarkup]:
	""" Вспомогательная функция для создания инлайн кнопок с названиями категорий для своей группы """

	category_list = await load_categories(message, context, groups=groups)  # получаем категории для своей группы
	if not category_list:
		return

	group = None if isinstance(groups, list) else groups
	inline_markup = generate_inline_markup(
		category_list,
		item_key="name",
		callback_data="id",
		callback_data_prefix=f"group_{group}__category_" if group else "category_",
		vertical=True
	)

	if button_type:  # обновим кнопки для предустановки иконок для отметки
		inline_markup = update_inline_markup(
			inline_keyboard=inline_markup.inline_keyboard,
			active_value=checked_callback_data,
			button_type=button_type
		)

	return inline_markup


def generate_users_list(users: List[dict]) -> InlineKeyboardMarkup:
	""" Вспомогательная функция для создания инлайн кнопок с именем пользователя и его рейтингом """
	inline_keyboard = generate_inline_markup(
		users,
		callback_data="id",
		item_key="username",
		item_prefix=["⭐️", "total_rating"],
		callback_data_prefix="user_"
	)

	return inline_keyboard


async def load_categories(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		exclude_empty: bool = True,
		cat_id: int = None,
		groups: Union[int, list] = None,  # by default it means all groups
):
	if cat_id:
		category = context.bot_data.setdefault("categories_dict", {}).get(cat_id)
		if category:
			return category

		res = await fetch_data(f'/categories/{cat_id}')
		if res["error"]:
			text = f"Ошибка загрузки категории {cat_id}"
			await send_error_to_admin(message, context, error=res, text=text)
			await message.reply_text(f'❗️{text}')
			return None

		context.bot_data["categories_dict"] = list_to_dict(res["data"], "id", *["name", "group"])
		return res["data"]

	region_ids = []
	main_region = context.user_data["details"].get("main_region")
	if main_region:
		region_ids.append(main_region["id"])

	cat_name = "categories"
	group = groups[0] if isinstance(groups, list) and len(groups) == 1 else groups

	# важно что именно аргумент 'groups' отпределяет в какой переменной в chat_data будут храниться категории
	# type list: в "categories" (там все вмеате)
	# type int : в "designers_cats", "outsourcers_cats", "suppliers_cats"
	if isinstance(groups, int):
		if groups >= len(CAT_GROUP_DATA):
			return
		group_data = CAT_GROUP_DATA[group]
		cat_name = group_data["name"] + "_cats"

	categories = context.chat_data.get(cat_name, None)

	# сигнал обязательного обновления категорий для всех пользователей
	is_outdated_categories = context.bot_data.get("is_outdated_categories", False)
	if not is_outdated_categories and categories is not None:
		return categories

	params = {"regions": region_ids}
	if groups:
		params["groups"] = groups
	if exclude_empty:
		params["exclude_empty"] = "true"

	res = await fetch_data("/categories", params=params)
	if res["error"]:
		text = "Ошибка загрузки списка категорий"
		await send_error_to_admin(message, context, error=res, text=text)
		await message.reply_text(f'❗️{text}')
		return None

	context.chat_data[cat_name] = res["data"]  # сохраним данные в памяти
	context.bot_data["categories_dict"] = list_to_dict(res["data"], "id", *["name", "group"])
	return res["data"]


async def load_cat_users(message: Message, context: ContextTypes.DEFAULT_TYPE, cat_id: str) -> Optional[List[dict]]:
	if not cat_id:
		return None

	# TODO: реализовать кэширование и обновление данных по сигналу, сохраняемому в bot_data или chat_data админом
	res = await fetch_user_data(params={"category": cat_id})
	if res["error"]:
		text = f'Ошибка получения списка поставщиков!'
		await send_error_to_admin(message, context, error=res, text=text, reply_markup=back_menu)
		return None

	return res["data"]


async def load_user(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: int,
		with_details: bool = False,
) -> Optional[dict]:
	params = {}
	if with_details:
		related_user_id = context.user_data["details"]["id"]
		params = {"with_details": "true", "related_user": related_user_id}

	res = await fetch_user_data(user_id, params=params)
	data = res["data"]
	if data is None:
		text = "Ошибка чтения данных пользователя."
		await catch_server_error(message, context, error=res, text=text)

	return data


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
		await send_error_to_admin(message, context, error=res, text=text)

	# сохраним в памяти полученные с сервера заказы в виде объектов с ключом order.id
	elif data:
		if isinstance(data, list):
			chat_data["orders"] = {item["id"]: item for item in data}

	return data


async def update_order(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		order_id: Union[int, str] = None,
		params: dict = None,
		data: dict = None,
		method: Literal["POST", "DELETE"] = "POST"
) -> Tuple[dict, str]:
	endpoint = f'/orders/{"create" if not order_id and method == "POST" else order_id}'
	res = await fetch_data(endpoint, params=params, data=data, method=method)

	if res["error"]:
		res.setdefault("request_body", data)
		if order_id:
			text = f'Ошибка {"обновления" if method == "POST" else "удаления"} заказа.'
		else:
			text = 'Ошибка при создании заказа.'

		await send_error_to_admin(message, context, error=res, text=text)
		return None, text

	orders = context.chat_data.setdefault("orders", {})
	if method == "DELETE":
		orders.pop(order_id, None)  # удалим заказ из сохраненных данных
	else:
		_id = res["data"]["id"]
		orders[_id] = res["data"]  # обновим заказ в сохраненных данных

	return res["data"], None


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


async def load_support_data(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: str = None,
		message_id: int = None,
		params: dict = None
) -> Union[dict, list, None]:
	if message_id and user_id:
		res = await fetch_data(f'/supports/{user_id}/{message_id}', params=params or {})
		data = res["data"] or {}
	else:
		res = await fetch_data(f'/supports/{user_id}', params=params or {})
		data = res["data"] or []

	if res["error"]:
		text = "Ошибка загрузки вопросов пользователя"
		await send_error_to_admin(message, context, error=res, text=text)
		return None

	return data


async def update_support_data(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: int,
		message_id: int,
		data: dict = None
) -> Optional[dict]:
	res = await fetch_data(f'/supports/{user_id}/{message_id}', data=data, method="POST")

	if res["error"]:
		text = "Ошибка сохранения вопроса пользователя"
		await send_error_to_admin(message, context, error=res, text=text)
		return None

	return res["data"]


async def load_favourites(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Tuple[List[dict], str]:
	user_details = context.user_data["details"]

	res = await fetch_user_data(user_details["user_id"], '/favourites', method="GET")
	if res["error"]:
		text = f'Ошибка получения списка Избранное!'
		await send_error_to_admin(message, context, error=res, text=text)
		return None, text

	return res["data"], None


async def update_favourites(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: int,
		method: Literal["POST", "DELETE"] = "POST"
) -> Tuple[Optional[List[dict]], Optional[str]]:
	user_details = context.user_data["details"]

	res = await fetch_user_data(user_details["user_id"], f'/favourites/{user_id}', method=method)

	if res["error"]:
		text = "Ошибка обновления списка Избранное" if method == "POST" else "Ошибка удаления пользователя из Избранное"
		await send_error_to_admin(message, context, error=res, text=text)
		return None, text

	return res["data"], None


async def update_category_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк выбора нажатой inline кнопки для списка категорий """

	query = update.callback_query
	await query.answer()

	query_data = query.data.split("__")
	cat_id = query_data[-1].lstrip("category_")
	group = None
	if len(query_data) > 1:
		group = int(query_data[0].lstrip("group_"))

	categories = await load_categories(query.message, context, groups=group)
	if not categories:
		return

	selected_cat = find_obj_in_dict(categories, {"id": int(cat_id)})
	if not selected_cat:
		return

	local_data = context.chat_data.setdefault("local_data", {})
	selected_categories = local_data.setdefault("selected_categories", {})

	await delete_messages_by_key(context, "warn_message_id")

	# Добавим или удалим найденную категорию
	if selected_categories.get(cat_id):
		del selected_categories[cat_id]
	else:
		selected_categories[cat_id] = {
			"name": selected_cat["name"],
			"group": selected_cat["group"]
		}

	await regenerate_inline_keyboard(query.message, active_value=query.data, button_type="checkbox")


async def select_supplier_segment(message: Message, context: ContextTypes.DEFAULT_TYPE, user: dict) -> None:
	""" Функция вывода сообщения с предложением выставить сегмент поставщика """

	temp_messages = context.chat_data.setdefault("temp_messages", {})

	# если выбранный поставщик еще лично не зарегистрирован в боте и не имеет ранее выбранного кем-то сегмента
	if not Group.has_role(user, Group.SUPPLIER) or user["user_id"] or not user["segment"] is None:
		return

	inline_markup = generate_inline_markup(
		SEGMENT_KEYBOARD,
		callback_data_prefix=f'user_{user["id"]}__segment_',
		vertical=True
	)

	_message = await message.reply_text(
		f'🎯 *Сегмент еще не установлен!*\n'
		f'Подскажите, если работали с этим поставщиком.',
		reply_markup=inline_markup
	)
	temp_messages["user_segment"] = _message.message_id


def order_has_approved_executor(order: dict) -> bool:
	""" Вернет истина, если претендент отсутствует в списке откликнувшихся на заказ responded_users """
	if not order["executor"]:
		return False

	responded_user = find_obj_in_dict(order["responded_users"], {"id": order["executor"]})
	return not bool(responded_user)


def get_order_status(order: dict) -> Tuple[str, str]:
	"""
	Получение статуса заказа в виде строки
	Returns:
		Tuple (статус, дата выполнения заказа)
	"""
	date_string, expire_date, current_date = get_formatted_date(order["expire_date"])
	is_valid = not expire_date or current_date <= expire_date

	if order["status"] == 0:
		order_status = ORDER_STATUS[0]
	elif order["status"] == 1:
		if not is_valid:
			order_status = ORDER_STATUS[4]
		elif order["executor"]:
			order_status = ORDER_STATUS[int(order_has_approved_executor(order) + 2)]
		else:
			order_status = ORDER_STATUS[1]
	elif order["status"] == 2:
		order_status = ORDER_STATUS[5]
	elif order["status"] == 3:
		order_status = ORDER_STATUS[6]
	else:
		order_status = ORDER_STATUS[7]

	return order_status, date_string


async def show_user_orders(
		message: Message,
		orders: list,
		user_role: Literal["creator", "contender", "executor"],
		user_id: int = None,
		title: str = None,
		reply_markup: ReplyKeyboardMarkup = back_menu
) -> list:
	""" Вывод на экран списка заказов пользователя по его id:
		Args:
			message: объект с сообщением,
			orders: заказы дизайнера,
			user_role: флаг указывающий на текущую роль пользователя,
			user_id: id текущего пользователя,
			title: заголовок для сообщений,
			reply_markup: клавиатура для reply message.
		Returns:
			массив Message сообщений
	 """

	messages = []
	callback_prefix = "order_"

	if title:
		reply_message = await message.reply_text(f'*{title.upper()}*\n', reply_markup=reply_markup)
		messages.append(reply_message)

	if not orders:
		message_text = "❕Список заказов пустой"
		reply_message = await message.reply_text(message_text, reply_markup=reply_markup)
		messages.append(reply_message)

		if user_role == "creator":
			inline_message = await place_new_order_message(message)
			messages.append(inline_message)

		return messages

	elif not user_role:
		return messages

	for index, order in enumerate(orders, 1):
		order_has_executor = order_has_approved_executor(order)
		order_button_text = ORDER_RESPOND_KEYBOARD[3]

		if user_role == "creator":
			order_button_text = ORDER_RESPOND_KEYBOARD[4]
			if order["status"] == 2:
				order_button_text = ORDER_RESPOND_KEYBOARD[5]

			responded_user_counter = len(order["responded_users"])
			if order["status"] < 2 and responded_user_counter and not order_has_executor:
				# вставим счетчик между названием кнопки и ее иконкой справа
				order_button_text = f'{order_button_text[:-2]} ({responded_user_counter} {order_button_text[-1]})'

		elif order["executor"] == user_id and not order_has_executor:
			order_button_text = ORDER_RESPOND_KEYBOARD[2]

		inline_markup = generate_inline_markup(
			[order_button_text],
			callback_data=[order["id"]],
			callback_data_prefix=callback_prefix
		)

		inline_message_text = format_output_text(f'{index}', order["title"] + "\n", tag="`", default_sep=".")

		order_status, date_string = get_order_status(order)
		if not user_role == "creator":
			order_status = ""
		# inline_message_text += f'\nЗаказчик: _{order["owner_name"]}_'

		if order_has_executor and order["executor"] != user_id:
			executor = order.get("executor_name")
			if executor:
				inline_message_text += f'\nИсполнитель: _{executor}_'

		order_price = f'{order["price"]}₽' if order["price"] else "по договоренности"
		inline_message_text += f'\nСтоимость работ: _{order_price}_'

		if date_string:
			inline_message_text += f'\nСрок реализации: _{date_string}_'

		if order_status:
			inline_message_text += f'\nСтатус: _{order_status}_'

		inline_message = await message.reply_text(inline_message_text, reply_markup=inline_markup)
		messages.append(inline_message)

	if user_role == "creator":
		inline_message = await place_new_order_message(message)
		messages.append(inline_message)

	return messages


async def show_order_related_users(message: Message, context: ContextTypes.DEFAULT_TYPE, order: dict) -> List[Message]:
	""" Вывод данных претендентов на заказ или исполнителя с inline кнопками управления """

	executor_id = order["executor"]
	users = order["responded_users"]

	if not executor_id and not users:
		return []

	order_has_executor = order_has_approved_executor(order)
	selected_postfix = ""
	inline_messages = []

	# если пользователь был выбран дизайнером
	if executor_id:
		if order_has_executor:  # если подтвержденный исполнитель
			executor = await load_user(message, context, user_id=executor_id)
			if executor:
				users = [executor]

		else:
			selected_postfix = "__is_selected"

	# изменим заголовок списка претендентов или исполнителя
	_message = await message.reply_text(f'_{ORDER_RELATED_USERS_TITLE[int(order_has_executor)]}:_')
	inline_messages.append(_message)

	for user in users:
		buttons = [InlineKeyboardButton(ORDER_EXECUTOR_KEYBOARD[0], callback_data=f'user_{user["id"]}')]
		if order["status"] == 1 and not order_has_executor:
			user_is_contender = user["id"] == executor_id
			if not executor_id or user_is_contender:
				buttons.append(InlineKeyboardButton(
					ORDER_EXECUTOR_KEYBOARD[int(user_is_contender) + 1],
					callback_data=f'order_{order["id"]}__executor_{user["id"]}{selected_postfix}'
				))

		_message = await message.reply_text(
			f'*{user["name"]}*'
			f'{format_output_text("рейтинг", "⭐️" + str(user["total_rating"]) if user["total_rating"] else "отсутствует")}',
			reply_markup=InlineKeyboardMarkup([buttons])
		)
		inline_messages.append(_message)

	return inline_messages


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
		join_button = generate_inline_markup(
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
		error_text = "Администратор уже проинформирован о проблеме.\nПопробуйте повторить позже."
		markup = generate_inline_markup(["Отправить"], callback_data="send_error")

	else:
		error_text = "Можете поделиться ошибкой с администратором Консьерж Сервис."
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
	section = get_section(context)
	error_data = {
		"chat_id": chat_data.get("chat_id"),
		"bot_status": chat_data.get("status"),
		"state": section.get("state"),
		"query_message": section.get("query_message", None),
		"callback": section.get("callback", None),
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
		text=f'*📥 Сообщение для администратора!*\n\n'
		     f'_{title_text}_\n'
		     f'`\n{error_text}`\n\n'
		     f'*Данные чата:*\n'
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


async def message_for_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	chat_data = context.chat_data
	state = MenuState.SUPPORT

	message = await query.message.reply_text(
		"О чем Вы хотели сообщить нам?"
	)

	return state

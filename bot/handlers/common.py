from asyncio import sleep
from typing import Union, List, Optional, Tuple, Callable, Literal, Dict

from telegram import (
	Update, Message, ReplyKeyboardMarkup, InlineKeyboardMarkup, CallbackQuery, Bot, helpers, ReplyKeyboardRemove,
	ChatMember
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID, TRADE_GROUP_ID, SANDBOX_GROUP_ID
from bot.constants.keyboards import BACK_KEYBOARD, SEGMENT_KEYBOARD
from bot.constants.menus import main_menu, done_menu
from bot.constants.messages import (
	offer_for_registration_message, share_link_message, send_unknown_question_message, confirm_region_message,
	join_chat_message
)
from bot.constants.patterns import BACK_PATTERN, BACK_TO_TOP_PATTERN, SUPPORT_PATTERN, CANCEL_PATTERN, TRADE_PATTERN
from bot.constants.static import MESSAGE_TYPE, CAT_GROUP_DATA, CHAT_GROUPS_DATA
from bot.entities import TGMessage
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	fetch_data, generate_inline_markup, fetch_user_data, find_obj_in_dict, extract_fields, list_to_dict,
	match_query, dict_to_formatted_text, update_inline_markup, fuzzy_compare, format_output_link, group_objects_by_date
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
		message_text: str = None,
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

	section = get_section(context)
	query_message = query.message.text

	# если сообщение касается техподдержки
	if match_query(SUPPORT_PATTERN, query_message):
		return await message_for_admin_callback(update, context)

	# или если сообщение не связано с возвратом или отменой, то будем считать, что это неизвестный вопрос
	elif not match_query(BACK_PATTERN + "|" + CANCEL_PATTERN, query_message):
		await send_unknown_question_message(query.message, context, reply_markup=section["reply_markup"])
		return section["state"]

	# удалим все сохраненные значения в рабочих переменных
	chat_data["local_data"] = {}
	await delete_messages_by_key(context, "temp_messages")
	await delete_messages_by_key(context, "warn_message_id")
	await delete_messages_by_key(context, "last_message_id")
	await delete_messages_by_key(context, "last_message_ids")

	current_section = pop_section(context)  # удалим тек секцию из навигации
	if current_section:
		await delete_messages_by_key(context, current_section.get("messages"))  # удалим все сообщения из тек секции

	# если нажата кнопка "В начало", то присвоим нулевой индекс
	if not current_section or match_query(BACK_TO_TOP_PATTERN, query_message) or len(chat_data["sections"]) == 1:
		section_index = 0
	else:
		section_index = level

	# получим предыдущую секцию, к которой возвращаемся
	back_section = get_section(context, section_index)
	# print("back section: \n", back_section)
	# если необходимо перейти в начало меню или не найден уровень раздела для возврата
	if section_index == 0 or not back_section:
		section = await init_start_section(context, state=MenuState.START)
		return section["state"]

	state = back_section.get("state", None)
	keep_messages = back_section.get("keep_messages", False)
	callback = back_section.get("callback")

	# если на предыдущем уровне не было установлено свойство сохранить сообщения на экране, то выведем их
	if not keep_messages:
		if callback:  # если указан колбэк, то перейдем по нему, установив флаг возврата
			back_section["go_back"] = True
			state = await callback(update, context)

		else:
			# если нет колбэка, но есть сохраненные сообщения у предыдущего раздела, то выведем их
			await TGMessage.display_section_messages(context, back_section)

	if message_text or keep_messages:
		if not message_text or message_text == "back":
			message_text = f'Вернулись в *{str(back_section["state"]).upper()}*'

		back_message = await query.message.reply_text(message_text, reply_markup=back_section["reply_markup"])
		back_section["messages"].append(back_message.message_id)

	return state


async def prepare_current_section(context: ContextTypes.DEFAULT_TYPE, keep_messages: bool = False) -> dict:
	""" Получение и подготовка данных из последнего выбранного раздела перед переходом в новый """
	current_section = get_section(context).copy()
	is_back = current_section.get("go_back", False)

	# если переходим в следующий раздел, а не возвращаемся назад
	if not is_back:
		update_section(context, keep_messages=keep_messages)

		await delete_messages_by_key(context, "warn_message_id")
		await delete_messages_by_key(context, "last_message_id")
		await delete_messages_by_key(context, "last_message_ids")

		current_section["query_message"] = None  # если переходим ниже, то query_message вначале должен быть пустым
		if not keep_messages:  # если разрешаем удалить сообщения после перехода в новый раздел
			messages = current_section.get("messages", [])
			await delete_messages_by_key(context, messages)  # удалим все сообщения с экрана на текущем уровне

	return current_section


def add_section(
		context: ContextTypes.DEFAULT_TYPE,
		state: str,
		query_message: str = None,
		messages: Union[Message, List[Message], List[int]] = None,
		callback: Callable = None,
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
	group = context.user_data.get("priority_group")
	menu_index = group.value if group else 3
	reply_markup = main_menu[menu_index]

	message = await context.bot.send_message(
		chat_id=chat_data["chat_id"],
		text='*Выберите интересующий раздел:*',
		reply_markup=reply_markup
	)

	return add_section(context, state, messages=message, reply_markup=reply_markup)


async def edit_or_reply_message(
		context: ContextTypes.DEFAULT_TYPE,
		text: str,
		message: Union[Message, int, None] = None,
		delete_before_reply: Union[bool, int] = False,
		return_message_id: bool = True,
		message_type: Literal["info", "warn", "error", None] = None,
		reply_markup: Union[ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove] = None,
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

	if message is not None:
		message_id = message.message_id if isinstance(message, Message) else message
		try:
			if delete_before_reply and isinstance(delete_before_reply, bool):
				raise TelegramError("Сообщение еще не было создано!")

			message = await context.bot.edit_message_text(
				chat_id=chat_id,
				message_id=message_id,
				text=text,
				reply_markup=reply_markup
			)

		except TelegramError:
			if message_id:
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
		return message.message_id if return_message_id else message


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
		show_all: bool = False,
		checked_ids: list = None,
		button_type: Optional[Literal["checkbox", "radiobutton"]] = None
) -> Optional[InlineKeyboardMarkup]:
	""" Вспомогательная функция для создания инлайн кнопок с названиями категорий для своей группы """

	# получаем категории для своей группы, учитывая все или только те, которые присвоены пользователям
	category_list = await load_categories(message, context, exclude_empty=not show_all, groups=groups)
	if not category_list:
		return

	callback_data_prefix = "category_" if isinstance(groups, list) else f"group_{groups}__category_"
	inline_markup = generate_inline_markup(
		category_list,
		item_key="name",
		callback_data="id",
		callback_data_prefix=callback_data_prefix,
		cols=1
	)

	if button_type:  # обновим кнопки для предустановки иконок для отметки
		callback_data = [callback_data_prefix + str(_id) for _id in checked_ids] if checked_ids else []
		inline_markup = update_inline_markup(
			inline_keyboard=inline_markup.inline_keyboard,
			active_value=callback_data,
			button_type=button_type
		)

	return inline_markup


def generate_users_list(users: List[dict]) -> InlineKeyboardMarkup:
	""" Вспомогательная функция для создания инлайн кнопок с именем пользователя и его рейтингом """
	inline_keyboard = generate_inline_markup(
		users,
		callback_data="id",
		item_key="name",
		item_prefix=["⭐️", "total_rating"],
		callback_data_prefix="user_"
	)

	return inline_keyboard


async def select_region(
		context: ContextTypes.DEFAULT_TYPE,
		region_name: str,
		geolocation: bool = False,
		reply_markup: ReplyKeyboardMarkup = None
) -> Optional[dict]:
	chat_data = context.chat_data
	regions = chat_data.get("region_list")
	if not regions:
		return

	# получим объект региона по выбранному названию региона
	found_region, c, _ = fuzzy_compare(region_name, regions, "name", 0.3)
	if not found_region:
		text = f'Регион с названием *{region_name}* не найден!\nВведите корректное название региона'
		chat_data["warn_message_id"] = await edit_or_reply_message(
			context,
			text=text,
			message=chat_data.get("warn_message_id"),
			message_type="warn",
			reply_markup=reply_markup
		)
		return

	region_name = found_region["name"]
	# если введенное название региона близко похоже на то что есть в общем перечне, то предложим подтвердить
	if c < 0.8:
		chat_data["new_region"] = found_region
		if geolocation and not chat_data["selected_geolocation"]:
			title = "Определился регион"
		else:
			title = "Вы имели ввиду"

		title += f' *{region_name.upper()}*, все верно?'
		await confirm_region_message(context, title)  # подтвердим что правильно найден в таблице регион
		return

	else:
		# сохраним статус разового использования геолокации
		if geolocation:
			chat_data["selected_geolocation"] = True

		return found_region


async def confirm_region_callback(
		update: Update,
		context: ContextTypes.DEFAULT_TYPE,
		add_region_func: Callable
) -> None:
	""" Колбэк подтверждения автоматически предложенного региона """

	query = update.callback_query
	await query.answer()

	button_data = query.data.lstrip("choose_region_")
	geolocation = context.user_data.get("geolocation")
	chat_data = context.chat_data
	section = get_section(context) or {}

	if button_data == 'yes':
		if geolocation:
			chat_data["selected_geolocation"] = True

		await query.message.delete()
		if add_region_func:
			await add_region_func(update, context, chat_data["new_region"])

	elif section:
		await query.message.delete()
		await query.message.reply_text("Тогда введите другое название", reply_markup=section.get("reply_markup"))

	else:
		if geolocation:
			text = "Хорошо. Тогда введите название самостоятельно"
			context.user_data["geolocation"].clear()
		else:
			text = "Хорошо. Тогда введите другое название"
		await query.edit_message_text(text)


async def select_user_group_callback(
		update: Update,
		context: ContextTypes.DEFAULT_TYPE,
		button_type: Literal["checkbox", "radiobutton", "rate"] = "checkbox"
):
	""" Колбэк выбора группы и добавления индекса в глобальный список selected_groups """

	query = update.callback_query
	await query.answer()

	user_group = int(query.data)
	local_data = context.chat_data.setdefault("local_data", {})
	selected_groups = local_data.setdefault("selected_groups", [])
	if button_type == "checkbox":
		if user_group in selected_groups:
			selected_groups.pop(selected_groups.index(user_group))
		else:
			selected_groups.append(user_group)

	elif button_type == "radiobutton":
		local_data["selected_groups"] = [user_group]

	await regenerate_inline_keyboard(query.message, active_value=query.data, button_type=button_type)


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

	# важно что именно аргумент 'groups' определяет в какой переменной в chat_data будут храниться категории
	# type list: в "categories" (там все вместе)
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

	params = {}
	if groups:
		params["groups"] = groups
	if exclude_empty:
		params["exclude_empty"] = "true"
		if region_ids:
			params["regions"] = region_ids

	res = await fetch_data("/categories", params=params)
	if res["error"]:
		text = "Ошибка загрузки списка категорий"
		await send_error_to_admin(message, context, error=res, text=text)
		await message.reply_text(f'❗️{text}')
		return None

	context.chat_data[cat_name] = res["data"]  # сохраним данные в памяти
	context.bot_data["categories_dict"] = list_to_dict(res["data"], "id", *["name", "group"])
	return res["data"]


async def load_cat_users(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		cat_id: str,
		offset: int = 0,
		limit: int = 10
) -> Optional[List[dict]]:
	if not cat_id:
		return None

	# TODO: реализовать кэширование и обновление данных по сигналу, сохраняемому в bot_data или chat_data админом
	params = {"category": cat_id}
	if offset:
		params["offset"] = offset

	if limit:
		params["limit"] = limit

	res = await fetch_user_data(params=params)
	if res["error"]:
		text = f'Ошибка получения списка поставщиков!'
		await send_error_to_admin(message, context, error=res, text=text)
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
		await send_error_to_admin(message, context, error=res, text=text)

	return data


async def load_regions(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[list], Optional[list]]:
	res = await fetch_data("/regions")
	if not res["data"]:
		text = "Ошибка загрузки списка регионов"
		await send_error_to_admin(
			message,
			context,
			error=res,
			text=text,
		)
		return None, None

	return res["data"], None  # filter_list(res["data"], "in_top", 1)


async def load_orders(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		order_id: int = "",
		params: dict = None
) -> Union[list, dict, None]:
	chat_data = context.chat_data
	orders = chat_data.setdefault("orders", {})

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
		if isinstance(data, dict):
			_id = data["id"]
			orders[_id] = data

		elif isinstance(data, list):
			[orders.update({obj["id"]: obj}) for obj in data]

	return data


async def update_order(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		order_id: Union[int, str] = None,
		params: dict = None,
		data: dict = None,
		method: Literal["POST", "DELETE"] = "POST"
) -> tuple:
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


async def load_user_field_names(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Dict[str, str]:
	user_field_names = context.bot_data.setdefault("user_field_names", {})

	if user_field_names:
		return user_field_names

	res = await fetch_data("/user_field_names")
	if not res["data"]:
		text = "Ошибка загрузки названий полей пользователя"
		await send_error_to_admin(message, context, error=res, text=text)

	else:
		context.bot_data["user_field_names"] = res["data"]

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


async def load_favourites(message: Message, context: ContextTypes.DEFAULT_TYPE) -> tuple:
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
) -> tuple:
	user_details = context.user_data["details"]

	res = await fetch_user_data(user_details["user_id"], f'/favourites/{user_id}', method=method)

	if res["error"]:
		text = "Ошибка обновления списка Избранное" if method == "POST" else "Ошибка удаления пользователя из Избранное"
		await send_error_to_admin(message, context, error=res, text=text)
		return None, text

	return res["data"], None


async def load_events(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		events_type: int,
		events_date: str = None,
		group: int = None,
) -> Union[Dict[str, List[dict]], List[dict]]:
	""" Загрузка событий за год или выбранный месяц для группы: 0 или 1 """

	# TODO: доделать проверку прошедших месяцев и удалять их из events. После чего надо обновить данные по api
	if events_type == 2:
		events = context.bot_data.setdefault("world_events", {})
	elif events_type == 1:
		events = context.bot_data.setdefault("country_events", {})
	else:
		events = context.chat_data.setdefault("region_events", {})

	# попытка найти событие по месяцу в загруженном ранее списке событий
	data = events.get(events_date)
	if data:
		return data

	params = {"events_type": events_type}
	if group is not None:
		params["group"] = group

	if events_date:
		params["month"], params["year"] = events_date.split(".")

	res = await fetch_data(f'/events', params=params)
	if res["error"]:
		text = f'Ошибка получения событий за {"месяц" if events_date else "12 мес"} для группы {group}'
		await send_error_to_admin(message, context, error=res, text=text)

	if res["data"]:
		grouped_events = group_objects_by_date(res["data"], date_field_name="start_date", date_format='%m.%Y')
		events.update(grouped_events)

	if events_date:
		return events.get(events_date, [])

	return events


async def post_user_log_data(context: ContextTypes.DEFAULT_TYPE, status_code: int, message, error_code: int = None):
	""" Сохранение записи в лог таблицу """
	user_id = context.bot.id
	data = {"user_id": str(user_id), "status": status_code, "message": message, "error_code": error_code}
	await fetch_data("/logs", data=data, method="POST")


async def select_user_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк выбора нажатой inline кнопки для списка категорий """

	query = update.callback_query
	await query.answer()

	query_data = query.data.split("__")
	cat_id = int(query_data[-1].lstrip("category_"))
	group = None
	if len(query_data) > 1:
		group = int(query_data[0].lstrip("group_"))

	categories = await load_categories(query.message, context, groups=group)
	if not categories:
		return

	selected_cat = find_obj_in_dict(categories, {"id": cat_id})
	if not selected_cat:
		return

	local_data = context.chat_data.setdefault("local_data", {})
	selected_categories = local_data.setdefault("selected_categories", {})

	# Добавим или удалим найденную категорию
	if selected_categories.get(cat_id):
		del selected_categories[cat_id]
	else:
		selected_categories[cat_id] = {
			"name": selected_cat["name"],
			"group": selected_cat["group"]
		}

	await regenerate_inline_keyboard(query.message, active_value=query.data, button_type="checkbox")


async def select_supplier_segment(context: ContextTypes.DEFAULT_TYPE, user: dict) -> None:
	""" Функция вывода сообщения с предложением выставить сегмент поставщика """

	temp_messages = context.chat_data.setdefault("temp_messages", {})

	# если выбранный поставщик еще лично не зарегистрирован в боте и не имеет ранее выбранного кем-то сегмента
	if not Group.has_role(user, Group.SUPPLIER) or user.get("user_id") or user.get("segment", None) is not None:
		return

	inline_markup = generate_inline_markup(
		SEGMENT_KEYBOARD,
		callback_data_prefix=f'user_{user["id"]}__segment_',
		cols=1
	)

	temp_messages["user_segment"] = await edit_or_reply_message(
		context,
		f'🎯 *Сегмент еще не установлен!*\n'
		f'Подскажите, если работали с этим поставщиком.',
		reply_markup=inline_markup
	)


async def trade_dialog_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	# если сообщение касается вопроса покупки/продажи
	await update.message.delete()
	section = get_section(context)
	last_message_ids = context.chat_data.setdefault("last_message_ids", {})
	trade_url = await context.bot.export_chat_invite_link(chat_id=TRADE_GROUP_ID)
	sandbox_url = await context.bot.export_chat_invite_link(chat_id=SANDBOX_GROUP_ID)

	trade_link = format_output_link(trade_url, "Дизайн Консьерж " + CHAT_GROUPS_DATA[TRADE_GROUP_ID])
	sandbox_link = format_output_link(sandbox_url, "Дизайн Консьерж " + CHAT_GROUPS_DATA[SANDBOX_GROUP_ID])

	last_message_ids["trade_message"] = await edit_or_reply_message(
		context,
		f'Если желаете что-то купить, продать или отдать, то переходите в группу {trade_link}\n'
		f'Для других целей есть своя группа {sandbox_link}',
		message=last_message_ids.get("trade_message"),
		message_type="info",
		reply_markup=section["reply_markup"]
	)

	return section["state"]


async def is_user_chat_member(bot: Bot, user_id: int, chat_id: int) -> bool:
	""" Проверка наличия пользователя в группе или канале """
	try:
		chat = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
		if chat.status not in [ChatMember.LEFT, ChatMember.BANNED]:
			return True
	except TelegramError:
		pass

	return False


async def invite_user_to_chat(
		update: Union[Update, CallbackQuery],
		user_id: int,
		chat_id: int,
		text: str = None,
		chat_is_channel: bool = True,
		chat_name: str = ""
) -> Optional[Message]:
	""" Добавляем пользователя в чат (канал/группа) """

	bot = update.get_bot()
	chat_variants = ["нашей группе", "нашему каналу"]
	subtext = " " + chat_variants[int(chat_is_channel)]
	join_link = await bot.export_chat_invite_link(chat_id=chat_id)
	join_group_text = f'🫂 Вы присоединены к{subtext} *{chat_name}*!'
	inline_markup = generate_inline_markup(["Перейти в группу"], url=join_link)

	# Проверяем принадлежность пользователя к чату
	is_member = await is_user_chat_member(bot, user_id=user_id, chat_id=chat_id)
	if is_member:
		return await update.message.reply_text(join_group_text, reply_markup=inline_markup)

	try:
		is_joined = await bot.approve_chat_join_request(user_id=user_id, chat_id=chat_id)
		if is_joined:
			return await update.message.reply_text(join_group_text, reply_markup=inline_markup)

	except TelegramError:
		pass

	return await join_chat_message(update.message, join_link, text, subtext, chat_name)


async def show_chat_group_links(
		update: Update,
		context: ContextTypes.DEFAULT_TYPE,
		group_id: int = None,
		hide_joined_groups: bool = True
) -> None:
	user_id = context.user_data["details"]["user_id"]
	last_message_ids = context.chat_data.setdefault("last_message_ids", {})

	chat_groups = {group_id: CHAT_GROUPS_DATA.get(group_id)} if group_id else CHAT_GROUPS_DATA

	for chat_id, chat_name in chat_groups.items():
		if not group_id and hide_joined_groups and await is_user_chat_member(context.bot, user_id, chat_id):
			continue
		else:
			message = await invite_user_to_chat(
				update,
				user_id=user_id,
				chat_id=chat_id,
				chat_is_channel=False,
				chat_name=chat_name
			)

			if message:
				last_message_ids[str(chat_id)] = message.message_id


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


async def catch_critical_error(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		error: dict,
		text: str = "",
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
		auto_send_notification: bool = True,
) -> Message:
	user = message.chat
	user_name = context.user_data.get("details", {}).get("name") or user.full_name
	error_data = {
		"error": error.get("error", "Неизвестная ошибка"),
		"status_code": error.get("status_code", "unknown"),
		"url": error.get("url", ""),
		"body": error.get("request_body", {})
	}

	log.error('User {} (ID:{}) got server error {} on request {}: "{}"'.format(
		user_name, user.id, error_data["status_code"], error_data["url"], error_data["error"]
	))

	error_title = text or f'{error_data["status_code"]}: {error_data["error"]}\n'
	await post_user_log_data(context, status_code=0, message=error_data["error"], error_code=error_data["status_code"])

	if auto_send_notification:
		await send_error_to_admin(message, context, error=error_data, text=error_title)
		error_text = "Сообщение об ошибке отправлено в техподержку.\nПопробуйте повторить позже"
		markup = reply_markup

	else:
		context.chat_data["last_error"] = {"text": error.get("error"), "code": error.get("status_code")}
		error_text = "Опишите более подробно ситуацию при которой возникла ошибка " \
		             "и/или нажмите *Отправить* уведомление в техподдержку"
		markup = generate_inline_markup(["Отправить"], callback_data="send_error")

	reply_message = await message.reply_text(
		f'Что-то пошло нет так!\n'
		f'*{error_title}*\n\n'
		f'{error_text}.\n'
		f'Приносим свои извинения, {user.first_name}',
		reply_markup=markup
	)

	return reply_message


async def send_message_to(
		context: ContextTypes.DEFAULT_TYPE,
		user_id: Union[int, str, List[int]],
		text: str,
		from_name: str,
		from_username: str = None,
		reply_to_message_id: int = None,
		reply_markup: InlineKeyboardMarkup = None
) -> None:
	"""
    Функция для отправки уведомлений пользователям.
    :param context: Контекст выполнения функции.
    :param user_id: Идентификатор или список идентификаторов пользователей.
    :param text: Текст уведомления.
    :param from_name: Имя отправителя уведомления.
    :param from_username: Имя пользователя в Телеграм (необязательный параметр).
    :param reply_to_message_id: id сообщения на которое отвечают
    :param reply_markup: Инлайн клавиатура
    :return: None
    """
	if not user_id and not text:
		return

	if not isinstance(user_id, list):
		user_ids = [user_id]

	else:
		user_ids = user_id

	for _id in user_ids:
		if isinstance(_id, int):
			res = await fetch_user_data(_id)
			data = res["data"]
			if data and data["user_id"]:
				user_id = data["user_id"]
			else:
				break
		else:
			user_id = _id

		if from_username and not reply_to_message_id:
			text = f" (@{from_username})\n{text}"
		else:
			text = f"\n{text}"

		await context.bot.send_message(
			chat_id=user_id,
			text=f'📨 *{"Ответ" if reply_to_message_id else "Пришло сообщение"}*'
			     f'* от {from_name}*{text}',
			reply_to_message_id=reply_to_message_id,
			reply_markup=reply_markup
		)


async def send_error_to_admin(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		error: dict,
		text: Union[str, dict] = ""
) -> None:
	user = message.from_user
	user_details = context.user_data.get('details', {
		'user_id': user.id,
		'name': user.full_name,
		'username': user.username,
	})

	chat_data = context.chat_data
	chat_data["last_error"] = {"text": error.get("error"), "code": error.get("status_code")}
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
		text=f'📥 *Сообщение для администратора!*\n\n'
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
	error_message = {
		"error": chat_data.get("error", "unknown"),
		"status_code": chat_data.get("status_code", "unknown"),
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

	state = MenuState.SUPPORT

	message = await query.message.reply_text("О чем Вы хотели сообщить нам?")
	context.chat_data["last_message_id"] = message.message_id

	return state

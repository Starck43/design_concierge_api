from typing import Union, List, Dict, Optional, ValuesView, Tuple

from telegram import Update, Message, ReplyKeyboardMarkup, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ExtBot, ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID, CHANNEL_ID
from bot.constants.keyboards import BACK_KEYBOARD
from bot.constants.menus import main_menu, done_menu, back_menu
from bot.constants.messages import (
	offer_for_registration_message, share_link_message, yourself_rate_warning_message, empty_data_message
)
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (fetch_data, filter_list, generate_inline_keyboard, fetch_user_data, find_obj_in_list,
                       rating_to_string, extract_fields)


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
			await catch_server_error(update.message, context, error_data=res)
			return None
	else:
		user_data["details"] = res["data"]
		return True


async def check_user_in_channel(user_id: int, bot: ExtBot) -> bool:
	"""Проверяет наличие пользователя в группе"""
	try:
		member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
		return bool(member)
	except TelegramError:
		return False


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE, level: int = -2) -> Optional[Message]:
	""" Переход вверх по меню """
	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	chat_data = context.chat_data
	button_text = query.message.text.lower()
	up_level = level if button_text in BACK_KEYBOARD[0].lower() else 0

	menu = extract_state_menu(context, up_level)
	if not menu:
		start_menu = await init_start_menu(context)
		return start_menu["state"]

	state, reply_message, inline_message, markup, inline_markup = menu
	last_message_id = chat_data.get("last_message_id")
	once_message_ids = chat_data.get("once_message_ids")

	if reply_message and not inline_message:
		await delete_messages_by_key(context, "last_message_id")

	if once_message_ids:
		await delete_messages_by_key(context, "once_message_ids")

	if reply_message:
		await query.message.reply_text(
			text=reply_message.text_markdown,
			reply_markup=markup
		)

	if inline_message:
		if last_message_id and not reply_message:
			await context.bot.edit_message_text(
				text=inline_message.text_markdown,
				chat_id=chat_data.get("chat_id"),
				message_id=last_message_id,
				reply_markup=inline_markup or inline_message.reply_markup
			)
		else:
			message = await query.message.reply_text(
				text=inline_message.text_markdown,
				reply_markup=inline_markup or inline_message.reply_markup
			)
			chat_data["last_message_id"] = message.message_id

	return state


async def init_start_menu(
		context: ContextTypes.DEFAULT_TYPE,
		menu_markup: Optional[ReplyKeyboardMarkup] = main_menu,
		text: str = None,
) -> Dict[str, Optional[Message]]:
	chat_data = context.chat_data

	reply_message = await context.bot.send_message(
		chat_id=chat_data["chat_id"],
		text=text or '*Выберите интересующий раздел:*',
		reply_markup=menu_markup,
		parse_mode=ParseMode.MARKDOWN_V2
	)

	chat_data["menu"]: List[Dict[str, Optional[Message]]] = [{
		"state": MenuState.START,
		"message": reply_message,
		"inline_message": None,
		"markup": menu_markup,
		"inline_markup": None,
	}]

	return chat_data["menu"][0]


# TODO: Добавить проверку на out of range
def get_state_menu(context: ContextTypes.DEFAULT_TYPE, index: int = -1) -> Tuple[any, any, any, any, any]:
	chat_data = context.chat_data
	menu = chat_data.get("menu", [])
	if not menu:
		return None, None, None, None, None

	return menu[index].values()


def extract_state_menu(context: ContextTypes.DEFAULT_TYPE, index: int = -1) -> Optional[ValuesView]:
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


async def edit_last_message(
		query: Union[Update, CallbackQuery],
		context: ContextTypes.DEFAULT_TYPE,
		text: str,
		reply_markup: Union[ReplyKeyboardMarkup, InlineKeyboardMarkup] = None
) -> Message:

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


async def delete_messages_by_key(context: ContextTypes.DEFAULT_TYPE, key_name: str):
	"""
	Deletes messages based on a given key name from the chat data.
	:param context: The context object containing chat data.
	:param key_name: The field name of the message or message ID.
	"""
	message_id = context.chat_data.get(key_name)
	chat_id = context.chat_data.get("chat_id")
	if not message_id or not chat_id:
		context.chat_data.pop(key_name, None)
		return

	if isinstance(message_id, int):
		await context.bot.delete_message(chat_id=chat_id, message_id=message_id)

	if isinstance(message_id, dict):
		for value in message_id.values():
			await context.bot.delete_message(chat_id=chat_id, message_id=value)

	if isinstance(message_id, list):
		for value in message_id:
			await context.bot.delete_message(chat_id=chat_id, message_id=value)

	if isinstance(message_id, Message):
		if message_id:
			message_id = message_id.message_id
			await context.bot.delete_message(chat_id=chat_id, message_id=message_id)

	del context.chat_data[key_name]


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
		print(user_groups, category_list)

	group = min(user_groups, default=3)
	context.user_data["group"] = Group.get_enum(group)

	return group


def get_user_rating_data(context: ContextTypes.DEFAULT_TYPE, user: dict) -> Tuple[dict, dict, str]:
	""" Возвращаем вопросы для анкетирования, текущий детальный рейтинг в виде объекта и в виде строки """
	group = max(user.get("groups"))
	rating_questions = context.bot_data["rating_questions"][group - 1] if group else {}
	rating = user.get("average_rating", {})
	rating_text = rating_to_string(rating, rating_questions)

	return rating_questions, rating, rating_text
	

async def update_ratings(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: str,
		data: any
) -> Optional[List[dict]]:
	await delete_messages_by_key(context, "once_message_ids")

	res = await fetch_user_data(user_id, "/update_ratings", data=data, method="POST")
	if res["status_code"] == 304:
		await yourself_rate_warning_message(message)

	elif not res["data"]:
		text = "Ошибка сохранения результатов анкетирования"
		await catch_server_error(message, context, error_data=res, text=text)

	return res["data"]


async def check_required_user_group_rating(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Optional[bool]:
	chat_data = context.chat_data
	selected_user = chat_data.get('selected_user')
	rating_questions = context.bot_data.get('rating_questions')

	if not selected_user or not rating_questions:
		chat_data["error"] = "selected_user пустой или нет загруженных rating_questions."
		await empty_data_message(message)
		return None

	rates, _ = find_obj_in_list(chat_data["user_ratings"], {"receiver_id": selected_user["id"]})
	group = max(selected_user["groups"])
	questions_count = len(rating_questions[group - 1].items())
	questions_rated_count = len(rates.items()) - 1 if rates else 0

	if group == 1 and questions_rated_count < 2 or group == 2 and questions_rated_count < 6:
		saved_message = await message.reply_text(
			f"*Необходимо оценить все критерии!*\n"
			f"Отмечено: _{questions_rated_count}_ из _{questions_count}_",
			# reply_markup=continue_menu
		)
		chat_data["last_message_id"] = saved_message.message_id
		return True

	return False


async def load_cat_users(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		cat_id: str
) -> Optional[InlineKeyboardMarkup]:
	if not cat_id:
		return None

	chat_data = context.chat_data
	cat_users = chat_data.get("cat_users", {})
	if cat_id not in cat_users or not cat_users[cat_id]:
		res = await fetch_user_data(params={"category": cat_id})
		if not res["data"]:
			cat_name = chat_data.get("selected_cat", "")
			await catch_server_error(
				message,
				context,
				error_data=res,
				text=f'Ошибка получения списка поставщиков для категории "{cat_name.upper()}".',
				reply_markup=back_menu
			)
			return None

		cat_users[cat_id] = res["data"]

	return generate_inline_keyboard(
		cat_users[cat_id],
		callback_data="id",
		item_key="username",
		item_prefix=["⭐️", "total_rate"],
		prefix_callback_name="supplier_",
	)


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

	if not res["data"]:
		if res["error"]:
			text = "Ошибка загрузки списка категорий"
		else:
			text = "Список категорий пустой"

		await catch_server_error(message, context, error_data=res, text=text)

	return res["data"]


async def load_users_in_category(message: Message, context: ContextTypes.DEFAULT_TYPE, cat_id: int):
	res = await fetch_user_data(params={"category": cat_id})
	if not res["data"]:
		text = f"Ошибка загрузки пользователей для категории {cat_id} через api"
		await catch_server_error(message, context, error_data=res, text=text)

	return res["data"]


async def load_user(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: int,
		designer_id: Optional[int] = None,
):
	if not user_id:
		return None

	params = {"related_user": designer_id} if designer_id is not None else {}
	res = await fetch_user_data(user_id, params=params)
	if res["data"] is None:
		text = "Ошибка чтения данных пользователя."
		await catch_server_error(message, context, error_data=res, text=text, reply_markup=None)

	return res["data"]


async def load_regions(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[list], Optional[list]]:
	res = await fetch_data("/regions")
	if not res["data"]:
		text = "Ошибка загрузки регионов через api"
		await catch_server_error(message, context, error_data=res, text=text)
		return None, None

	return res["data"], filter_list(res["data"], "in_top", 1)


async def load_rating_questions(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		params: dict = None
) -> Tuple[Optional[list], str]:
	res = await fetch_data("/rating_questions", params=params or {})
	if not res["data"]:
		text = "Ошибка загрузки вопросов для рейтинга"
		await catch_server_error(message, context, error_data=res, text=text)

	return res["data"]


async def load_user_field_names(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		params: dict = None
) -> Tuple[Optional[list], str]:
	res = await fetch_data("/user_field_names", params=params or {})
	if not res["data"]:
		text = "Ошибка загрузки названий полей пользователя"
		await catch_server_error(message, context, error_data=res, text=text)

	return res["data"]


async def create_start_link(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Отправляем сообщение с ссылкой для начала диалога
	bot_username = context.bot.username
	invite_link = f"https://t.me/{bot_username}?start=start"

	await share_link_message(
		message,
		link=invite_link,
		link_text="Ссылка на Консьерж для дизайнеров",
		text="Нажмите на кнопку Старт для начала работы"
	)

	return invite_link


async def create_registration_link(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Создаем ссылку для регистрации
	bot_username = context.bot.username
	invite_link = f"https://t.me/{bot_username}?start=register"

	await share_link_message(
		message,
		link=invite_link,
		link_text="Ссылка на регистрацию",
		text="Ссылка на регистрацию в Консьерж для дизайнеров"
	)

	return invite_link


async def create_questionnaire_link(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
	# Создаем ссылку для анкетирования
	bot_username = context.bot.username
	invite_link = f"https://t.me/{bot_username}?start=questionnaire"

	await share_link_message(
		message,
		link=invite_link,
		link_text="Ссылка на анкетирование",
		text="Для составления рейтинга поставщиков, предлагаем пройти анкетирование."
	)

	return invite_link


async def catch_server_error(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		error_data: Dict,
		text: str = "",
		auto_send_notification: bool = True,
		reply_markup: Optional[ReplyKeyboardMarkup] = done_menu,
) -> None:
	user = message.chat

	chat_data = context.chat_data
	chat_data["error"] = error_data.get("error", "Неизвестная ошибка")
	chat_data["status_code"] = error_data.get("status_code", "unknown")
	chat_data["api_url"] = error_data.get("url", "")

	log.info('User {} got server error {} on request {}: "{}"'.format(
		user.id, chat_data["status_code"], chat_data["api_url"], chat_data["error"]
	))

	error_text = f'{chat_data["status_code"]}: {chat_data["error"]}\n'
	await message.reply_text(
		text or f"*Ошибка!*\n{error_text}\n\nПриносим свои извинения, {user.first_name}\n"
		        f"Попробуйте в другой раз.",
		reply_markup=reply_markup
	)

	if not auto_send_notification:
		await message.reply_text(
			"Вы можете известить администратора Консьерж Сервис, просто нажав на кнопку ниже.\n"
			"Спасибо!",
			reply_markup=generate_inline_keyboard(
				["Отправить уведомление"],
				callback_data="send_error"
			)
		)
	else:
		await send_error_to_admin(message, context, text=error_text)


async def send_error_to_admin(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		text: Union[str, dict] = ""
) -> None:
	user = message.from_user
	user_details = context.user_data.get('details', {
		'user_id': user.id,
		'username': user.username,
		'name': user.full_name,
	})

	chat_data = context.chat_data.copy()
	chat_data.pop("menu", None) # удалим состояние меню

	if isinstance(text, dict):
		text = ''.join('{}: {}\n'.format(key.replace("_", " "), val) for key, val in text.items())
	elif not isinstance(text, str):
		text = str(text)

	user_text = '\n'.join(f'{key.replace("_", " ")}: {val}' for key, val in user_details.items())
	chat_text = '\n'.join(
		f'{key.replace("_", " ")}: {val}' for key, val in chat_data.items()
		if isinstance(val, list) or isinstance(val, str) or isinstance(val, int)
	)

	# TODO: Добавить функционал для логирования ошибок на сервере
	await context.bot.send_message(
		chat_id=ADMIN_CHAT_ID,
		text=f'<b>Обнаружена ошибка в чат-боте Консьерж Сервис!</>\n'
		     f'{text}\n'
		     f'<b>Chat data:</b>\n<pre>{chat_text}</pre>\n'
		     f'<b>User data:</b>\n<pre>{user_text}</pre>\n',
		parse_mode=ParseMode.HTML
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

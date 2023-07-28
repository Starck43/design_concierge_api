from typing import Union, List, Dict, Optional, ValuesView, Tuple, Any

from telegram import Update, Message, ReplyKeyboardMarkup, InlineKeyboardMarkup, CallbackQuery, Bot, helpers, ChatMember
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID
from bot.constants.keyboards import BACK_KEYBOARD
from bot.constants.menus import main_menu, done_menu, back_menu
from bot.constants.messages import (
	offer_for_registration_message, share_link_message, yourself_rate_warning_message, empty_data_message
)
from bot.logger import log
from bot.states.group import Group
from bot.states.main import MenuState
from bot.utils import (
	fetch_data, filter_list, generate_inline_keyboard, fetch_user_data, find_obj_in_list, extract_fields,
	match_message_text
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
			await catch_server_error(update.message, context, error_data=res)
			return None
	else:
		user_data["details"] = res["data"]
		return True


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE, level: int = -2) -> Optional[Message]:
	""" Переход вверх по меню """
	query = update.callback_query
	if query:
		await query.answer()
	else:
		query = update

	await query.message.delete()

	current_menu = get_state_menu(context)
	current_message = current_menu[1]
	current_inline_message = current_menu[2]
	await delete_messages_by_key(context, current_message)
	await delete_messages_by_key(context, current_inline_message)

	# если нажата кнопка Назад, то вернем предыдущее состояние меню, иначе переходим в начальное состояние
	index = level if match_message_text(BACK_KEYBOARD[0], query.message.text) else 0
	prev_menu = extract_state_menu(context, index)

	if not prev_menu:
		init_menu = await init_start_menu(context)
		await delete_messages_by_key(context, "last_message_id")
		state = init_menu["state"]

	else:
		state, reply_message, inline_message, markup, inline_markup = prev_menu

		if reply_message:
			reply_message = await query.message.reply_text(
				text=reply_message.text_markdown,
				reply_markup=markup
			)
		else:
			reply_message = None

		if inline_message:
			if current_inline_message and not reply_message:
				inline_message = await context.bot.edit_message_text(
					text=inline_message.text_markdown,
					chat_id=query.message.chat_id,
					message_id=current_inline_message.message_id,
					reply_markup=inline_markup or inline_message.reply_markup
				)

			else:
				inline_message = await query.message.reply_text(
					text=inline_message.text_markdown,
					reply_markup=inline_markup or inline_message.reply_markup
				)

			last_message_id = context.chat_data.get("last_message_id")
			# если последнее сохраненное сообщение было заменено на новое выше, то не удаляем его
			if last_message_id and last_message_id != inline_message.message_id:
				await delete_messages_by_key(context, "last_message_id")
		else:
			await delete_messages_by_key(context, "last_message_id")
			inline_message = None

		context.chat_data["menu"][-1].update({
			"message": reply_message,
			"inline_message": inline_message
		})

	await delete_messages_by_key(context, "last_message_ids")

	saved_message: Message = context.chat_data.get("saved_message")
	if saved_message:
		if index == 0:
			# если поднимаемся в начало меню, то удалим сообщение "saved_message", если оно было сохранено
			await delete_messages_by_key(context, saved_message)

		else:
			try:
				await saved_message.reply_text(
					saved_message.text,
					reply_markup=saved_message.reply_markup
				)
			except TelegramError:
				pass
			del context.chat_data["saved_message"]

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


def get_state_menu(context: ContextTypes.DEFAULT_TYPE, index: int = -1) -> Tuple[Any, ...]:
	try:
		chat_data = context.chat_data
		menu = chat_data.get("menu", [])
		return tuple(menu[index].values())

	except IndexError:
		return None, None, None, None, None


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


async def delete_messages_by_key(context: ContextTypes.DEFAULT_TYPE, message: Union[Message, str, None]):
	"""
	Deletes messages based on a given key name from the chat data.
	:param context: The context object containing chat data.
	:param message: The Message or field name of the message or message ID.
	"""
	chat_id = context.chat_data.get("chat_id")
	if not message or not chat_id:
		return

	if isinstance(message, Message):
		message_id = message.message_id
		try:
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
			for value in message_id:
				await context.bot.delete_message(chat_id=chat_id, message_id=value)

	except TelegramError:
		pass

	del context.chat_data[message]


def is_designer(context: ContextTypes.DEFAULT_TYPE) -> bool:
	""" Проверим состоит ли пользователь в группе дизайнер"""
	user_groups = context.user_data["details"]["groups"]
	return 0 in user_groups


def is_outsourcer(context: ContextTypes.DEFAULT_TYPE) -> bool:
	""" Проверим состоит ли пользователь в группе аутсорсер"""
	user_groups = context.user_data["details"]["groups"]
	return 1 in user_groups


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
	context.user_data["group"] = Group.get_enum(group)

	return group


def get_user_rating_data(context: ContextTypes.DEFAULT_TYPE, user: dict) -> Tuple[dict, dict]:
	""" Возвращаем вопросы для анкетирования, подробный рейтинг в виде объекта и в виде строки """
	rating = user.get("average_rating", {})
	group = max(user.get("groups"))
	rating_questions = context.bot_data["rate_questions"][group - 1] if group else {}

	return rating_questions, rating


async def update_ratings(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_id: str,
		data: any
) -> Optional[List[dict]]:
	await delete_messages_by_key(context, "last_message_ids")

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
		message = await message.reply_text(
			f"*Необходимо оценить все критерии!*\n"
			f"Отмечено: _{questions_rated_count}_ из _{questions_count}_",
			# reply_markup=continue_menu
		)
		chat_data["last_message_id"] = message.message_id
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
			await catch_server_error(
				message,
				context,
				error_data=res,
				text=f'Ошибка получения списка поставщиков!',
				reply_markup=back_menu
			)
			return None

		cat_users[cat_id] = res["data"]

	return generate_inline_keyboard(
		cat_users[cat_id],
		callback_data="id",
		item_key="username",
		item_prefix=["⭐️", "total_rate"],
		prefix_callback_name="user_",
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
) -> Tuple[Optional[dict], Optional[Message]]:
	params = {"related_user": designer_id} if designer_id is not None else {}
	res = await fetch_user_data(user_id, params=params)
	data: dict = res["data"]
	reply_message = None

	if data is None:
		text = "Ошибка чтения данных пользователя."
		reply_message = await catch_server_error(message, context, error_data=res, text=text, reply_markup=None)

	if data:
		data.setdefault("name", data["username"])

	return data, reply_message


async def load_regions(message: Message, context: ContextTypes.DEFAULT_TYPE) -> Tuple[Optional[list], Optional[list]]:
	res = await fetch_data("/regions")
	if not res["data"]:
		text = "Ошибка загрузки регионов через api"
		await catch_server_error(message, context, error_data=res, text=text)
		return None, None

	return res["data"], filter_list(res["data"], "in_top", 1)


async def load_orders(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		id: int = "",
		params: dict = None
) -> Union[list, dict, None]:
	orders = context.chat_data.get("orders")
	if id and orders:
		# попытка найти заказ в загруженном ранее списке заказов
		data, _ = find_obj_in_list(orders, {"id": id})
		if data:
			return data

	res = await fetch_data(f"/orders/{id}", params=params)
	data = res["data"]

	if not data:
		text = f'Ошибка загрузки заказ{"а" if id else "ов"}'
		await catch_server_error(message, context, error_data=res, text=text)

	if isinstance(data, list):
		if orders is None or len(data) != len(orders):
			context.chat_data["orders"] = data

	return data


async def load_rating_questions(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
) -> Tuple[Optional[list], str]:
	res = await fetch_data("/rating/questions/")
	if not res["data"]:
		text = "Ошибка загрузки вопросов для рейтинга"
		await catch_server_error(message, context, error_data=res, text=text)

	return res["data"]


async def load_rating_authors(message: Message, context: ContextTypes.DEFAULT_TYPE, receiver_id: int) -> list:
	res = await fetch_data(f"/rating/{receiver_id}/authors/")
	if not res["data"]:
		text = "Ошибка загрузки списка голосовавших"
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
		print("approve")

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
		error_data: Dict,
		text: str = "",
		auto_send_notification: bool = True,
		reply_markup: Optional[ReplyKeyboardMarkup] = done_menu,
) -> Message:
	user = message.chat

	chat_data = context.chat_data
	chat_data["error"] = error_data.get("error", "Неизвестная ошибка")
	chat_data["status_code"] = error_data.get("status_code", "unknown")
	chat_data["api_url"] = error_data.get("url", "")

	log.info('User {} got server error {} on request {}: "{}"'.format(
		user.id, chat_data["status_code"], chat_data["api_url"], chat_data["error"]
	))

	error_text = f'{chat_data["status_code"]}: {chat_data["error"]}\n'
	reply_message = await message.reply_text(
		text or f"*Ошибка!*\n{error_text}\n\nПриносим свои извинения, {user.first_name}\n"
		        f"Попробуйте в другой раз.",
		reply_markup=reply_markup
	)

	if not auto_send_notification:
		await message.reply_text(
			"Вы можете уведомить администратора Консьерж Сервис о возникшей проблеме!\n",
			reply_markup=generate_inline_keyboard(
				["Отправить уведомление"],
				callback_data="send_error"
			)
		)
	else:
		await send_error_to_admin(message, context, text=error_text)

	return reply_message


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
	chat_data.pop("menu", None)  # удалим состояние меню

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

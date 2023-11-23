import re
from typing import Optional, List, Union

from telegram import Message, Update, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from bot.constants.keyboards import RATING_KEYBOARD
from bot.constants.messages import success_save_rating_message
from bot.constants.static import MAX_RATE, RATE_BUTTONS
from bot.entities import TGMessage
from bot.handlers.common import (
	edit_or_reply_message, send_error_to_admin, catch_server_error, delete_messages_by_key, get_section, load_user
)
from bot.utils import (
	fetch_user_data, fetch_data, find_obj_in_dict, update_inline_markup, generate_inline_markup,
	format_output_text, send_action, update_text_by_keyword, data_to_string
)


async def validate_rated_user(message: Message, context: ContextTypes.DEFAULT_TYPE, user: dict) -> Optional[bool]:
	""" Функция проверки корректности выставленных оценок """

	if not user:
		return None

	author = context.user_data["details"]
	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	warn_message_id = chat_data.get("warn_message_id")
	questions = await get_rating_questions(context, user=user)
	text = ""

	if not questions:
		text = "Ошибка проверки результата выставленной оценки"
		await send_error_to_admin(message, context, error=user, text=text)
		is_success = None

	elif user["id"] == author["id"]:
		text = 'Нельзя выставлять оценки самому себе'
		is_success = False

	else:
		rated_questions = find_obj_in_dict(local_data["selected_rating_list"], params={"receiver_id": user["id"]})
		group = max(user["groups"])  # 1 - это аутсорсеры (2 вопроса), 2 - поставщики (6 вопросов)
		questions_count = len(questions.items())
		rated_questions_count = len(rated_questions.items()) - 1 if rated_questions else 0

		if group == 1 and rated_questions_count < 2 or group == 2 and rated_questions_count < 6:
			text = f"*Необходимо оценить все критерии!*\n_Выполнено: {rated_questions_count}_ из _{questions_count}_"
			is_success = False

		else:
			is_success = True

	if not is_success:
		message_id = await edit_or_reply_message(context, text=text, message=warn_message_id, message_type="warn")
		chat_data["warn_message_id"] = message_id

	return is_success


async def update_ratings(message: Message, context: ContextTypes.DEFAULT_TYPE, rating_data: list) -> Optional[dict]:
	user_id = context.user_data["details"]["user_id"]
	res = await fetch_user_data(user_id, "/update_ratings", data=rating_data, method="POST")
	if res["status_code"] == 304:
		return None

	elif res["error"]:
		res.setdefault("request_body", rating_data)
		text = "Ошибка сохранения результатов анкетирования"
		await catch_server_error(message, context, error=res, text=text)

	return res["data"]


async def get_rating_questions(
		context: ContextTypes.DEFAULT_TYPE, 
		user: dict = None
) -> Union[list, dict]:
	""" Функция загрузки вопросов для анкетирования для своей группы пользователей (поставщик или аутсорсер) """

	question_groups = context.bot_data.setdefault("rating_questions", [])
	if not question_groups:
		res = await fetch_data("/rating/questions/")
		if res["data"]:
			question_groups = context.bot_data["rating_questions"] = res["data"]

	if question_groups and user:
		group = max(user.get("groups") or 0)  # определим группу пользователя для получения своих вопросов
		return question_groups[group - 1] if group > 0 else {}

	return question_groups


async def load_voted_users(message: Message, context: ContextTypes.DEFAULT_TYPE, receiver_id: int) -> list:
	res = await fetch_data(f"/rating/{receiver_id}/authors/")
	if res["status_code"] != 200:
		text = "Ошибка загрузки списка голосовавших"
		await send_error_to_admin(message, context, error=res, text=text)

	return res["data"]


def rating_to_message_text(rating_data: dict, questions: dict, rate_value: int = 5) -> str:
	if not rating_data or not questions:
		return ""

	result = ""
	for question, val in rating_data.items():
		if val is None:
			continue

		name = questions.get(question)
		if not name:
			continue

		rate = min(round(val), rate_value)
		level = rate / rate_value

		if level > RATE_BUTTONS[0][1]:
			button = RATE_BUTTONS[0][0]
		elif level > RATE_BUTTONS[1][1]:
			button = RATE_BUTTONS[1][0]
		else:
			button = RATE_BUTTONS[2]

		empty_rate = RATE_BUTTONS[3] * (rate_value - rate)
		result += f"{name} ({rate}/{rate_value}):\n{button * rate}{empty_rate}\n\n"

	return result


async def show_user_rating_questions(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user_detail_rating: dict,
		title: str,
		reply_markup: Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, None] = None,
		save_button_data: Optional[tuple] = None
) -> None:
	""" Вывод списка сообщений со шкалами оценок пользователя для выставления рейтинга """

	chat_data = context.chat_data
	selected_user = chat_data["selected_user"]
	rating_questions = await get_rating_questions(context, user=selected_user)
	question_list = rating_questions.keys()
	buttons = [[RATE_BUTTONS[3] for _ in range(MAX_RATE)]]

	await delete_messages_by_key(context, "last_message_ids")
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	last_message_ids["rating_title"] = await edit_or_reply_message(
		context,
		text=title,
		message=chat_data.get("last_message_id"),
		reply_markup=reply_markup
	)

	for i, question in enumerate(question_list, 1):
		current_rate = int(user_detail_rating.get(question) or 0)
		subtitle = f'{i}. *{rating_questions[question]}* ({current_rate}/{MAX_RATE})'
		callback_data = [f'rate__{selected_user["id"]}__{question}__{rate}' for rate in range(1, MAX_RATE + 1)]

		# если это последняя кнопка рейтинга, то добавим в конец кнопку сохранения рейтинга
		if save_button_data and i == len(question_list):
			buttons += [save_button_data[0]]
			callback_data += [save_button_data[1]]

		rate_markup = generate_inline_markup(buttons, callback_data=callback_data, item_key="username")

		# если у пользователя есть выставленный рейтинг, то обновим клавиатуру
		if user_detail_rating:
			rate_markup = update_inline_markup(
				inline_keyboard=rate_markup.inline_keyboard,
				active_value=str(current_rate),
				button_type='rate'
			)

		# отображение сообщения с вопросом рейтинга
		_message = await message.reply_text(text=subtitle, reply_markup=rate_markup)
		last_message_ids[question] = _message.message_id


async def show_total_detail_rating(message: Message, context: ContextTypes.DEFAULT_TYPE, user: dict) -> None:
	""" Сообщение в виде детального графического рейтинга по каждой оценке с кнопкой участников """

	temp_messages = context.chat_data.setdefault("temp_messages", {})
	user_is_owner = context.user_data["details"]["id"] == user["id"]  # когда пользователь просматривает себя
	detail_rating = user["detail_rating"]
	questions = await get_rating_questions(context, user=user)
	message_text = rating_to_message_text(rating_data=detail_rating, questions=questions, rate_value=MAX_RATE)
	# выведем общий детализированный рейтинг
	if not message_text:
		if user_is_owner:
			return

		rating_text = "Оцените поставщика, если уже работали с ним"
		buttons = [RATING_KEYBOARD[0]]
		callback_data = "update_rating"

	else:
		rating_text = "*Общий рейтинг:*\n\n" + message_text
		buttons = f'Участники рейтинга ({user["voted_users_count"]})'
		callback_data = f'voted_list_for_user_{user["id"]}'
		if not user_is_owner:
			is_voted = bool(user.get("related_detail_rating"))
			buttons = [buttons, RATING_KEYBOARD[int(is_voted)]],
			callback_data = [callback_data, "update_rating"]

	inline_markup = generate_inline_markup(buttons, callback_data=callback_data, vertical=True)
	temp_messages["related_user_rating"] = await edit_or_reply_message(
		context,
		text=rating_text,
		message=temp_messages.get("related_user_rating"),
		reply_markup=inline_markup
	)


@send_action(ChatAction.TYPING)
async def answer_rating_questions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк вывода на экран сообщений для выставления рейтинга """

	# TODO: после сохранения надо обновить last_message_id
	query = update.callback_query
	await query.answer()

	chat_data = context.chat_data
	selected_user = chat_data["selected_user"]
	local_data = chat_data.setdefault("local_data", {})
	related_detail_rating = selected_user.get("related_detail_rating") or {}

	# вывод оценок для выставления рейтинга
	rating_title = f'Проставьте оценки по каждому вопросу от 1 до {MAX_RATE}'
	if related_detail_rating:
		local_data["selected_rating_list"] = [related_detail_rating]  # подготовим список с рейтингом для изменения
		rating_dict = related_detail_rating.copy()
		rating_dict.pop('author_id', None)
		rating_dict.pop('receiver_id', None)
		rating_dict = list(rating_dict.values())
		if rating_dict:
			rating_title += format_output_text(
				"_Ваш текущий рейтинг: _",
				value=f'{round(sum(rating_dict) / len(rating_dict), 1)}',
				default_sep="⭐"
			)

	await show_user_rating_questions(
		query.message,
		context,
		user_detail_rating=related_detail_rating,
		title=rating_title,
		save_button_data=("✅ Сохранить результаты", "save_rates")
	)


async def select_rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	user_id = int(query.data.split('__')[1])
	question = query.data.split('__')[2]
	rate = int(query.data.split('__')[3])

	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	if not local_data.get("selected_rating_list"):
		current_rating = {'receiver_id': user_id}
		local_data["selected_rating_list"] = [current_rating]

	else:
		current_rating = find_obj_in_dict(local_data["selected_rating_list"], params={"receiver_id": user_id})
		if not current_rating:
			current_rating = {'receiver_id': user_id}
			local_data["selected_rating_list"].append(current_rating)

	if current_rating.get(question) == rate:
		del current_rating[question]
		active_value = '0'

	else:
		current_rating[question] = rate
		active_value = rate

	# изменим заголовок вопроса и его кнопки
	title = re.sub(r"\d+/", r"{}/".format(active_value), query.message.text_markdown)

	keyboard = query.message.reply_markup.inline_keyboard
	rate_markup = update_inline_markup(keyboard, active_value=active_value, button_type='rate')
	await query.message.edit_text(title, reply_markup=rate_markup)


@send_action(ChatAction.TYPING)
async def change_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк сохранения/обновления рейтинга поставщика в карточке пользователя """

	query = update.callback_query
	await query.answer()

	local_data = context.chat_data.setdefault("local_data", {})
	user = context.chat_data["selected_user"]
	section = get_section(context)
	success = await validate_rated_user(query.message, context, user=user)
	if not success:
		return

	# Почистим все сообщения с вопросами рейтинга
	await delete_messages_by_key(context, "last_message_ids")

	# обновим данные на сервере
	res = await update_ratings(query.message, context, rating_data=local_data.get("selected_rating_list", []))
	local_data.pop("selected_rating_list", None)
	if not res:
		return

	rated_user = res[0]

	user = await load_user(query.message, context, user_id=rated_user["receiver_id"], with_details=True)
	if user:
		context.chat_data["selected_user"] = user
	user["related_total_rating"] = rated_user["related_total_rating"]
	await delete_messages_by_key(context, "warn_message_id")

	# обновим рейтинг в карточке пользователя
	user_details_message: Message = section["messages"].pop(1)
	modified_text = update_text_by_keyword(
		text=user_details_message.text,
		keyword=f'*{user["name"]}',
		replacement=f'*{user["name"]} ⭐{user["total_rating"]}*'
	)
	message = await edit_or_reply_message(
		context,
		text=modified_text,
		message=user_details_message.message_id,
		return_only_id=False
	)
	section["messages"].insert(1, TGMessage.create_message(message))

	# выведем успешное сообщение вместо заголовка выставления рейтинга
	message = await success_save_rating_message(query.message, user)
	context.chat_data["last_message_id"] = message.message_id

	await show_total_detail_rating(query.message, context, user=user)


async def show_voted_designers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк отображения списка авторов, выставивших рейтинг для текущего пользователя """

	query = update.callback_query
	await query.answer()

	user_id = int(query.data.lstrip("voted_list_for_user_"))
	temp_messages = context.chat_data.setdefault("temp_messages", {})
	if temp_messages.get("voted_list"):
		return

	voted_users_list = await load_voted_users(query.message, context, receiver_id=user_id)
	if voted_users_list:
		text = data_to_string(voted_users_list, field_names="author_name", prefix="- ")
		temp_messages["voted_list"] = await query.message.reply_text('*В рейтинге участвовали:*\n\n' + f'_{text}_')

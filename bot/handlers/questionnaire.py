from typing import Optional, Union

from telegram import Update, CallbackQuery
from telegram.ext import ContextTypes

from bot.constants.static import MAX_RATE
from bot.constants.menus import continue_menu
from bot.constants.messages import (
	offer_to_cancel_action_message, failed_questionnaire_message, empty_questionnaire_list_message,
	success_questionnaire_message
)
from bot.handlers.common import (
	load_categories, delete_messages_by_key, edit_or_reply_message, load_cat_users, regenerate_inline_keyboard
)
from bot.handlers.rating import validate_rated_user, update_ratings, show_user_rating_questions
from bot.logger import log
from bot.states.questionnaire import QuestState
from bot.utils import (
	find_obj_in_list, update_inline_markup, generate_inline_markup, remove_duplicates,
	format_output_text, extract_fields
)


async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
	chat_data = context.chat_data
	temp_messages = chat_data.setdefault("temp_messages", {})
	chat_data["previous_state"] = QuestState.START
	chat_data["current_state"] = QuestState.SELECT_SUPPLIERS
	chat_data["status"] = "questionnaire"

	user = update.message.from_user
	log.info(f"User {user.full_name} (ID:{user.id}) started questionnaire.")

	# TODO: переместить логику сохранения categories в саму функцию load_categories
	categories = await load_categories(update.message, context, groups=[1, 2])
	if not categories:
		return QuestState.DONE

	message = await update.message.reply_text(
		"*Первый этап*\n"
		"_Отметьте компании с которыми работали:_",
		reply_markup=continue_menu
	)
	temp_messages["stage_1"] = message.message_id

	return await show_users_in_category(update, context)


async def cancel_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	chat_data["previous_state"] = chat_data["current_state"]
	chat_data["current_state"] = QuestState.CANCEL_QUESTIONNAIRE

	await offer_to_cancel_action_message(update.message)

	return chat_data["current_state"]


async def end_questionnaire(update: Union[Update, CallbackQuery], context: ContextTypes):
	user = update.message.from_user
	chat_data = context.chat_data

	if chat_data.get("error"):
		log.info(f"User {user.full_name} (ID:{user.id}) finished questionnaire with error.")

	else:
		log.info(f"User {user.full_name} (ID:{user.id}) finished questionnaire.")

		# продолжим диалог, если пользователь зарегистрировался или начал уже беседу
		# 'priority_group' сохраняется в этих двух состояниях и удобно используется для проверки
		if context.user_data.get("priority_group"):
			chat_data["status"] = "dialog"

	# TODO: заменить переменные на local_data
	chat_data.pop("selected_users", None)
	chat_data.pop("selected_user_index", None)
	chat_data.pop("selected_cat_index", None)
	chat_data.pop("questionnaire_cat_users", None)
	chat_data.pop("current_state", None)
	chat_data.pop("previous_state", None)
	await delete_messages_by_key(context, "temp_messages")
	await delete_messages_by_key(context, "last_message_ids")

	return QuestState.DONE


async def continue_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data
	await update.message.delete()

	if chat_data["current_state"] == QuestState.SELECT_SUPPLIERS:
		return await show_users_in_category(update, context, chat_data["selected_cat_index"] + 1)

	else:
		success = await validate_rated_user(update.message, context, user=chat_data["selected_user"])
		if success is None:
			return await end_questionnaire(update, context)

		elif success:
			return await show_rating_questions(update, context, chat_data["selected_user_index"] + 1)


async def show_users_in_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_index: int = 0):
	chat_data = context.chat_data
	temp_messages = chat_data.setdefault("temp_messages", {})

	# если достигли конца списка категорий
	if cat_index == len(chat_data["categories"]):
		# удалим дублирующихся поставщиков в списке отобранных для анкетирования
		remove_duplicates(chat_data["selected_users"], "id")
		users = extract_fields(chat_data["selected_users"], field_names="username")
		text = f'{format_output_text("", users, tag="_")}'

		message_id = await edit_or_reply_message(context, text=text, message=chat_data.get("last_message_id"))
		temp_messages["selected_users"] = message_id
		chat_data["last_message_id"] = None

		chat_data.pop("selected_cat_index", None)
		chat_data["previous_state"] = chat_data["current_state"]
		chat_data["current_state"] = QuestState.CHECK_RATES

		message = await update.message.reply_text(
			"*Последний этап*\n"
			"_Оцените выбранные компании по нескольким критериям:_",
			reply_markup=None
		)
		temp_messages["stage_2"] = message.message_id

		# перейдем к рейтингу по списку отобранных компаний
		return await show_rating_questions(update, context)

	chat_data["selected_cat_index"] = cat_index
	cat = chat_data["categories"][cat_index]
	cat_id, cat_name = cat["id"], cat["name"]

	chat_data["questionnaire_cat_users"] = await load_cat_users(update.message, context, cat_id)
	if not chat_data["questionnaire_cat_users"]:
		return QuestState.DONE

	title = f'{cat_index + 1}/{len(chat_data["categories"])} *{cat_name.upper()}*'
	inline_markup = generate_inline_markup(
		chat_data["questionnaire_cat_users"],
		callback_data="id",
		item_key="username"
	)

	chat_data["last_message_id"] = await edit_or_reply_message(
		context,
		text=title,
		message=chat_data.get("last_message_id"),
		reply_markup=inline_markup
	)

	return chat_data["current_state"]


async def select_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Добавление поставщиков в список для анкетирования
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data

	chat_data.setdefault("selected_users", [])
	cat_index = chat_data["selected_cat_index"]
	selected_cat = chat_data["categories"][cat_index]
	params = {"id": int(query.data), "category": selected_cat["id"]}
	selected_user, _ = find_obj_in_list(chat_data["questionnaire_cat_users"], params)

	if selected_user in chat_data["selected_users"]:
		chat_data["selected_users"].remove(selected_user)
	else:
		chat_data["selected_users"].append(selected_user)

	await regenerate_inline_keyboard(query.message, active_value=query.data, button_type="checkbox")
	return chat_data["current_state"]


async def show_rating_questions(update: Update, context: ContextTypes.DEFAULT_TYPE, user_index: int = 0) -> str:
	""" Функция вывода вопросов анкетирования по каждому поставщику """
	chat_data = context.chat_data
	selected_users = chat_data["selected_users"]
	local_data = context.chat_data.setdefault("local_data", {})

	# если достигнут конец списка или список отобранных поставщиков пуст
	if user_index == len(selected_users):
		if not selected_users:
			message = await empty_questionnaire_list_message(update.message)
			chat_data["last_message_id"] = message.message_id

		else:  # сохраним результаты анкетирования
			res = await update_ratings(update.message, context, rating_data=local_data.get("selected_rating_list", []))
			if res:
				message = await success_questionnaire_message(update.message)
				chat_data["last_message_id"] = message.message_id

		local_data.pop("selected_rating_list", None)
		return await end_questionnaire(update, context)  # завершение опроса

	chat_data["selected_user_index"] = user_index
	chat_data["selected_user"] = chat_data["selected_users"][user_index]

	title = f'*{user_index + 1}/{len(selected_users)}* `{chat_data["selected_user"]["username"]}`\n'
	await show_user_rating_questions(
		update.message,
		context,
		user_detail_rating={},
		title=title,
		reply_markup=continue_menu
	)

	# await update.message.delete()
	return chat_data["current_state"]


async def confirm_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()

	button_data = query.data
	chat_data = context.chat_data
	await query.message.delete()

	if button_data == 'yes':
		message = await failed_questionnaire_message(query.message)
		chat_data["last_message_id"] = message.message_id
		return await end_questionnaire(query, context)

	else:
		chat_data["current_state"] = chat_data["previous_state"]
		return chat_data["current_state"]

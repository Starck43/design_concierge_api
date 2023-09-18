from typing import Optional, Union

from telegram import Update, CallbackQuery, Message, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from bot.constants.menus import continue_menu
from bot.constants.messages import (
	offer_to_cancel_action_message, failed_questionnaire_message, empty_questionnaire_list_message,
	success_questionnaire_message
)
from bot.handlers.common import (
	load_categories, load_rating_questions, load_users_in_category, update_ratings, check_required_user_group_rating,
	delete_messages_by_key, get_user_rating_data
)
from bot.logger import log
from bot.states.questionnaire import QuestState
from bot.utils import (
	find_obj_in_list, update_inline_keyboard, find_obj_in_dict, generate_inline_keyboard, remove_duplicates,
	format_output_text, extract_fields
)


async def start_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.message.from_user
	chat_data = context.chat_data

	chat_data["previous_state"] = QuestState.START
	chat_data["current_state"] = QuestState.SELECT_SUPPLIERS
	chat_data["status"] = "questionnaire"
	log.info(f"User {user.full_name} (ID:{user.id}) started questionnaire.")

	chat_data.setdefault("categories", await load_categories(update.message, context, group=[1, 2]))
	if not chat_data["categories"]:
		return QuestState.DONE

	# подгрузим группы вопросов для рейтинга
	context.bot_data.setdefault("rating_questions", await load_rating_questions(update.message, context))
	if not context.bot_data.get("rating_questions"):
		return QuestState.DONE

	await update.message.reply_text(
		"*Первый этап*\n"
		"_Отметьте компании с которыми работали:_",
		reply_markup=continue_menu
	)

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

	chat_data.pop("user_ratings", None)
	chat_data.pop("selected_users", None)
	chat_data.pop("selected_user_index", None)
	chat_data.pop("selected_cat_index", None)
	chat_data.pop("questionnaire_cat_users", None)
	chat_data.pop("current_state", None)
	chat_data.pop("previous_state", None)
	return QuestState.DONE


async def continue_questionnaire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	chat_data = context.chat_data

	await update.message.delete()

	if chat_data["current_state"] == QuestState.SELECT_SUPPLIERS:
		return await show_users_in_category(update, context, chat_data["selected_cat_index"] + 1)

	else:
		required = await check_required_user_group_rating(update.message, context)
		if required is None:
			return await end_questionnaire(update, context)
		elif not required:
			return await show_rating_questions(update, context, chat_data["selected_user_index"] + 1)


async def show_users_in_category(update: Update, context: ContextTypes.DEFAULT_TYPE, cat_index: int = 0):
	chat_data = context.chat_data

	# если достигли конца списка категорий
	if cat_index == len(chat_data["categories"]):
		# удалим дублирующихся поставщиков в списке отобранных для анкетирования
		remove_duplicates(chat_data["selected_users"], "id")
		users = extract_fields(chat_data["selected_users"], field_names="username")

		await chat_data["saved_message"].edit_text(
			f'{format_output_text("", users , value_tag="_")}',
			reply_markup=None
		)
		del chat_data["saved_message"]
		chat_data["previous_state"] = chat_data["current_state"]
		chat_data["current_state"] = QuestState.CHECK_RATES

		await update.message.reply_text(
			"*Последний этап*\n"
			"_Оцените выбранные компании по нескольким критериям:_",
			reply_markup=None
		)
		chat_data.pop("selected_cat_index", None)
		return await show_rating_questions(update, context)

	else:
		chat_data["selected_cat_index"] = cat_index
		cat = chat_data["categories"][cat_index]
		cat_id, cat_name = cat["id"], cat["name"]

		chat_data["questionnaire_cat_users"] = await load_users_in_category(update.message, context, cat_id)
		if not chat_data["questionnaire_cat_users"]:
			return QuestState.DONE

		title = f'{cat_index + 1}/{len(chat_data["categories"])} *{cat_name.upper()}*'
		inline_markup = generate_inline_keyboard(
			chat_data["questionnaire_cat_users"],
			callback_data="id",
			item_key="username")

		if not chat_data.get("saved_message"):
			chat_data["saved_message"]: Message = await update.message.reply_text(title, reply_markup=inline_markup)
		else:
			await chat_data["saved_message"].edit_text(title, reply_markup=inline_markup)

	return chat_data["current_state"]


async def show_rating_questions(update: Update, context: ContextTypes.DEFAULT_TYPE, user_index: int = 0) -> str:
	chat_data = context.chat_data

	# если достигнут конец списка
	if user_index == len(chat_data["selected_users"]):
		if not chat_data["selected_users"]:
			await empty_questionnaire_list_message(update.message)

		# сохраним результаты анкетирования
		res = await update_ratings(update.message, context)
		if res:
			await success_questionnaire_message(update.message)

		await delete_messages_by_key(context, "last_message_ids")

		return await end_questionnaire(update, context)

	chat_data["selected_user_index"] = user_index
	chat_data["selected_user"] = chat_data["selected_users"][user_index]

	title = f'`{user_index + 1}/{len(chat_data["selected_users"])}` *{chat_data["selected_user"]["username"]}*'
	await show_user_rating_messages(update.message, context, title=title, reply_markup=continue_menu)

	# await update.message.delete()
	return chat_data["current_state"]


async def show_user_rating_messages(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		title: str = None,
		reply_markup: Union[InlineKeyboardMarkup, ReplyKeyboardMarkup, None] = None,
		rate_value: int = 8
) -> Optional[Message]:

	chat_data = context.chat_data
	selected_user = chat_data["selected_user"]
	rating_questions, avg_rating = get_user_rating_data(context, selected_user)
	symbols = ['⬜️' for _ in range(rate_value)]

	await delete_messages_by_key(context, "last_message_ids")
	saved_message = await message.reply_text(text=title or selected_user["username"], reply_markup=reply_markup)
	chat_data["last_message_ids"] = [saved_message.message_id]

	for i, question in enumerate(rating_questions.keys()):
		current_rate = int(avg_rating.get(question) or 0)
		subtitle = f'{i+1}. *{rating_questions[question]}* ({current_rate}/{rate_value})'

		rate_markup = generate_inline_keyboard(
			data=[symbols],
			callback_data=[f'rate__{selected_user["id"]}__{question}__{rate}' for rate in range(1, rate_value + 1)],
			item_key="username"
		)

		if avg_rating:
			rate_markup = update_inline_keyboard(
				rate_markup.inline_keyboard,
				active_value=str(current_rate),
				button_type='rate'
			)

		saved_message = await message.reply_text(text=subtitle, reply_markup=rate_markup)
		chat_data["last_message_ids"].append(saved_message.message_id)

	return saved_message


async def select_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	# Добавление поставщиков в список для анкетирования
	query = update.callback_query

	await query.answer()
	button_data = query.data
	chat_data = context.chat_data

	chat_data.setdefault("selected_users", [])
	cat_index = chat_data["selected_cat_index"]
	selected_cat = chat_data["categories"][cat_index]
	params = {"id": int(button_data), "category": selected_cat["id"]}
	selected_user, _ = find_obj_in_list(chat_data["questionnaire_cat_users"], params)

	if selected_user in chat_data["selected_users"]:
		chat_data["selected_users"].remove(selected_user)
	else:
		chat_data["selected_users"].append(selected_user)

	updated_keyboard = update_inline_keyboard(
		query.message.reply_markup.inline_keyboard,
		active_value=button_data,
		button_type='checkbox'
	)
	await query.message.edit_reply_markup(reply_markup=updated_keyboard)

	return chat_data["current_state"]


async def confirm_cancel_questionnaire_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	button_data = query.data
	chat_data = context.chat_data

	await query.message.delete()

	if button_data == 'yes':
		await failed_questionnaire_message(query.message)
		return await end_questionnaire(query, context)
	else:
		chat_data["current_state"] = chat_data["previous_state"]
		return chat_data["current_state"]


async def set_user_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	await query.answer()
	chat_data = context.chat_data

	user_id = int(query.data.split('__')[1])
	key = query.data.split('__')[2]
	rate = int(query.data.split('__')[3])

	if "user_ratings" not in chat_data:
		chat_data["user_ratings"] = []
		new_dict = {'receiver_id': user_id}
		chat_data["user_ratings"].append(new_dict)

	else:
		new_dict = find_obj_in_dict(chat_data["user_ratings"], params={"receiver_id": user_id})
		if not new_dict:
			new_dict = {'receiver_id': user_id}
			chat_data["user_ratings"].append(new_dict)

	if key in new_dict and new_dict[key] == rate:
		del new_dict[key]
		active_value = '0'

	else:
		new_dict[key] = rate
		active_value = rate

	updated_keyboard = update_inline_keyboard(
		query.message.reply_markup.inline_keyboard,
		active_value=active_value,
		button_type='rate'
	)

	await query.message.edit_reply_markup(reply_markup=updated_keyboard)
	# return chat_data["current_state"]

import re
from typing import Optional

from telegram import Update, Message
from telegram.ext import (
	ConversationHandler, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
)

from bot.constants.keyboards import START_QUESTIONNAIRE_KEYBOARD, DONE_KEYBOARD
from bot.constants.messages import offer_for_questionnaire_message
from bot.constants.patterns import DONE_PATTERN, CONTINUE_PATTERN, CANCEL_PATTERN, START_QUESTIONNAIRE_PATTERN, \
	REPEAT_QUESTIONNAIRE_PATTERN
from bot.handlers.common import user_authorization, create_questionnaire_link
from bot.handlers.rating import select_rate_callback
from bot.handlers.done import done
from bot.handlers.questionnaire import (
	select_users_callback, confirm_action_callback, continue_questionnaire,
	cancel_questionnaire, start_questionnaire
)
from bot.states.questionnaire import QuestState
from bot.utils import generate_reply_markup


async def questionnaire_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	"""Начало диалога по команде /questionnaire или сообщении questionnaire"""
	chat_data = context.chat_data
	chat_data["previous_state"] = ConversationHandler.END
	chat_data["current_state"] = QuestState.START
	chat_data["chat_id"] = update.effective_chat.id

	parameters = context.args
	if not update.message:
		query = update.callback_query
		if not query:
			return ConversationHandler.END
		await query.answer()
		update = query

	# Проверим, зарегистрирован ли пользователь
	has_authorized = await user_authorization(update, context)
	if has_authorized is None:
		return QuestState.DONE
	elif not has_authorized:
		return ConversationHandler.END

	if parameters and parameters[0].lower() != "questionnaire":
		await create_questionnaire_link(update.message, context)
		return ConversationHandler.END

	reply_markup = generate_reply_markup([START_QUESTIONNAIRE_KEYBOARD, DONE_KEYBOARD])
	saved_message: Message = chat_data.get("saved_message")
	if saved_message:
		await saved_message.edit_reply_markup(None)
		del chat_data["saved_message"]

	await offer_for_questionnaire_message(update.message, reply_markup)

	return chat_data["current_state"]


start_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(
		re.compile(START_QUESTIONNAIRE_PATTERN, re.I)
	),
	start_questionnaire
)

repeat_questionnaire_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(
		re.compile(REPEAT_QUESTIONNAIRE_PATTERN, re.I)
	),
	start_questionnaire
)

done_handler = MessageHandler(
	filters.TEXT & ~filters.COMMAND & filters.Regex(
		re.compile(DONE_PATTERN, re.I)
	),
	done
)

continue_questionnaire_handler = MessageHandler(
	filters.TEXT & filters.Regex(
		re.compile(CONTINUE_PATTERN, re.I)
	),
	continue_questionnaire
)

cancel_handler = MessageHandler(
	filters.TEXT & filters.Regex(
		re.compile(CANCEL_PATTERN, re.I)
	),
	cancel_questionnaire
)

questionnaire_dialog = ConversationHandler(
	allow_reentry=True,
	entry_points=[
		CommandHandler('questionnaire', questionnaire_conversation),
		CallbackQueryHandler(questionnaire_conversation, pattern="^questionnaire$"),
	],
	states={
		QuestState.START: [
			start_handler,
			done_handler,
		],
		QuestState.SELECT_SUPPLIERS: [
			CallbackQueryHandler(select_users_callback),
			continue_questionnaire_handler,
		],
		QuestState.CHECK_RATES: [
			CallbackQueryHandler(select_rate_callback, pattern="^rate"),
			continue_questionnaire_handler,
		],
		QuestState.CANCEL_QUESTIONNAIRE: [
			CallbackQueryHandler(confirm_action_callback),
		],
		QuestState.DONE: [
			done_handler,
			repeat_questionnaire_handler
		],
	},
	fallbacks=[
		cancel_handler
	]
)

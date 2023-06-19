from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from bot.logger import log


# TODO: Необходимо протестировать!!!
async def send_error_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	await query.answer()
	user = update.effective_user
	user_details = context.user_data.get('details', {})
	user_details.update({
		'user_id': user.id,
		'username': user.full_name,
	})
	error_message = user_details.get('error', "Тип ошибки не установлен")

	# sending error message to admin
	admin_chat_id = 'ADMIN_CHAT_ID'  # replace with actual chat id of admin
	error_text = f"Обнаружена ошибка в чат-боте Консьерж Сервис:\n\n" \
	             f"{error_message}\n\n" \
	             f"Данные отправителя: {user_details}"
	await context.bot.send_message(chat_id=admin_chat_id, text=error_text)

	# sending error message to user
	user_chat_id = update.effective_user.id
	error_text = f"{update.effective_user.full_name}, спасибо за обратную связь!\n" \
	             f"Сообщение уже отправлено администратору Консьерж Сервис\n" \
	             f"Приносим свои извинения за предоставленные неудобства."
	await context.bot.send_message(chat_id=user_chat_id, text=error_text)


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Display the gathered info and end the conversation."""
	user_data = context.user_data
	log.info("%s завершил диалог.", update.effective_user.full_name)

	if "details" in user_data:
		message_text = 'Были рады, если помогли. Обращайтесь! 👋'

		if "choice" in user_data:
			del user_data["choice"]

		if "question" in user_data:
			del user_data["question"]

	else:
		message_text = 'До свидания! 👋'

	await update.message.reply_text(message_text, reply_markup=ReplyKeyboardRemove())
	return ConversationHandler.END

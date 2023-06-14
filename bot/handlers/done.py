from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from bot.logger import log


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

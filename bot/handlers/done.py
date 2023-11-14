from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from bot.logger import log


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Display the gathered info and end the conversation."""
	user_data = context.user_data
	user = update.effective_user
	log.info(f"User {user.full_name} (ID:{user.id}) has finished dialog.")

	if "details" in user_data:
		message_text = f'Был рад, {user_data["details"]["username"]}, если помог. Обращайтесь! 👋'

	else:
		context.user_data.clear()
		message_text = 'До свидания! 👋'

	await update.message.reply_text(message_text, reply_markup=ReplyKeyboardRemove())
	context.chat_data.clear()

	return ConversationHandler.END

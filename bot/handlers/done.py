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

		# if "choice" in user_data:
		# 	del user_data["choice"]
		#
		# if "question" in user_data:
		# 	del user_data["question"]

	else:
		context.user_data.clear()
		message_text = 'До свидания! 👋'

	await update.message.reply_text(message_text, reply_markup=ReplyKeyboardRemove())
	context.chat_data.clear()
	context.chat_data.pop("sub_state", None)
	context.chat_data.pop("saved_message", None)
	context.chat_data.pop("last_message_id", None)
	context.chat_data.pop("selected_user", None)

	return ConversationHandler.END

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.common import delete_messages_by_key, edit_or_reply_message
from bot.logger import log


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Display the gathered info and end the conversation."""
	user_data = context.user_data
	user = update.effective_user

	await delete_messages_by_key(context, "last_message_ids")
	log.info(f"User {user.full_name} (ID:{user.id}) has finished dialog.")

	if "details" in user_data:
		message_text = f'Был рад, {user.first_name}, если помог. Обращайтесь! 👋'

	else:
		context.user_data.clear()
		message_text = 'До свидания! 👋'

	await edit_or_reply_message(
		context,
		text=message_text,
		reply_markup=ReplyKeyboardRemove(),
		lifetime=3
	)

	context.chat_data.clear()

	return ConversationHandler.END

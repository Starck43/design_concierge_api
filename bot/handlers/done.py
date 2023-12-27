from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.common import delete_messages_by_key, edit_or_reply_message, post_user_log_data
from logger import log


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Display the gathered info and end the conversation."""
	user_data = context.user_data
	user = update.effective_user
	user_name = user_data.get("details", {}).get("name") or user.full_name

	await delete_messages_by_key(context, "last_message_ids")
	message = f"User {user_name} (ID:{user.id}) has finished dialog"
	log.info(message)
	await post_user_log_data(context, status_code=4, message=message)

	if "details" in user_data:
		message_text = f'Был рад, {user.first_name}, если помог. Обращайтесь! 👋'

	else:
		context.user_data.clear()
		message_text = 'До свидания! 👋'

	message_text += "\nДля повторного входа наберите *start*"
	await edit_or_reply_message(
		context,
		text=message_text,
		reply_markup=ReplyKeyboardRemove(),
		lifetime=5
	)

	context.chat_data.clear()

	return ConversationHandler.END

from telegram import Update
from telegram.ext import ContextTypes


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Echo the user message."""
	# chat_id = update.effective_chat.id
	await update.message.reply_text(
		"Привет!\nЗдесь Вы найдете все последние новости канала",
	)
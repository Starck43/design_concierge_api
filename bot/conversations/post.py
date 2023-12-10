import re

from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, filters

from bot.constants.keyboards import SEND_CONFIRMATION_KEYBOARD
from bot.constants.patterns import CANCEL_POST_PATTERN
from bot.handlers.posts import create_new_post, cancel_post, send_post, process_post_photo, process_post_text
from bot.states.post import PostState

cancel_post_handler = MessageHandler(
	filters.TEXT & filters.Regex(re.compile(CANCEL_POST_PATTERN, re.I)), cancel_post,
)

post_dialog = ConversationHandler(
	entry_points=[CommandHandler("post", create_new_post)],
	states={
		PostState.CHOOSING: [
			MessageHandler(
				filters.TEXT & ~filters.COMMAND & filters.Regex(SEND_CONFIRMATION_KEYBOARD[0]),
				send_post
			),
			MessageHandler(
				filters.PHOTO,
				process_post_photo
			),
			MessageHandler(
				filters.TEXT & ~filters.COMMAND & ~filters.Regex(re.compile(CANCEL_POST_PATTERN, re.I)),
				process_post_text
			),
		],
	},
	fallbacks=[cancel_post_handler],
)

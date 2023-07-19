# from telegram import __version__ as TG_VER
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, Defaults, CallbackQueryHandler, MessageHandler, filters

from bot.bot_settings import BOT_TOKEN
from bot.conversations.main import main_dialog
from bot.conversations.post import post_dialog
from bot.conversations.questionnaire import questionnaire_dialog
from bot.conversations.registration import registration_dialog
from bot.handlers.about import about
from bot.handlers.common import send_error_message_callback
from bot.handlers.helper import helper
from bot.handlers.location import update_geolocation_data_choice

try:
	from telegram import __version_info__, Update
except ImportError:
	__version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]


def telegram_bot_main():
	"""Start the bot."""
	defaults = Defaults(parse_mode=ParseMode.MARKDOWN, protect_content=True)
	app = Application.builder().token(BOT_TOKEN).defaults(defaults).build()

	app.add_handler(CommandHandler('help', helper))
	app.add_handler(CommandHandler('about', about))

	# survey_answer_handler = CallbackQueryHandler(handle_poll_result, pattern=r'^poll:')

	# app.add_handler(survey_answer_handler)
	app.add_handler(MessageHandler(filters.LOCATION, update_geolocation_data_choice))
	app.add_handler(CallbackQueryHandler(send_error_message_callback, pattern='send_error'))
	app.add_handler(questionnaire_dialog)
	app.add_handler(registration_dialog)
	app.add_handler(main_dialog)
	app.add_handler(post_dialog)

	return app


if __name__ == "__main__":
	# telegram_bot_main()
	dispatcher = telegram_bot_main()
	dispatcher.run_polling()

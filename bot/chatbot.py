from warnings import filterwarnings

# from telegram import __version__ as TG_VER
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, Defaults
from telegram.warnings import PTBUserWarning

from bot.bot_settings import BOT_TOKEN
from bot.conversations.main import done_handler, main_dialog
from bot.conversations.post import post_dialog
from bot.conversations.registration import registration_dialog, cancel_reg_handler
from bot.handlers.about import about
from bot.handlers.helper import helper

try:
	from telegram import __version_info__
except ImportError:
	__version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

# if __version_info__ < (20, 0, 0, "alpha", 1):
# 	raise RuntimeError(
# 		f"This example is not compatible with your current PTB version {TG_VER}. To view the "
# 		f"{TG_VER} version of this example, "
# 		f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
# 	)

filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)


def telegram_bot_main():
	"""Start the bot."""
	defaults = Defaults(parse_mode=ParseMode.MARKDOWN, protect_content=True)
	app = Application.builder().token(BOT_TOKEN).defaults(defaults).build()

	app.add_handler(CommandHandler('help', helper))
	app.add_handler(CommandHandler('about', about))

	# survey_answer_handler = CallbackQueryHandler(handle_poll_result, pattern=r'^poll:')
	# app.add_handler(survey_answer_handler)
	app.add_handler(registration_dialog)
	app.add_handler(main_dialog)
	app.add_handler(post_dialog)
	# TODO: Надо будет убрать handlers и использовать из диалога registration_dialog и main_dialog
	app.add_handler(cancel_reg_handler)
	app.add_handler(done_handler)

	return app


if __name__ == "__main__":
	# telegram_bot_main()
	dispatcher = telegram_bot_main()
	dispatcher.run_polling()

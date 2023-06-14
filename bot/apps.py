from django.apps import AppConfig


class BotConfig(AppConfig):
	default_auto_field = "django.db.models.BigAutoField"
	name = "bot"

	# def ready(self):
	# 	from bot import chatbot
	# 	chatbot.telegram_bot_main()

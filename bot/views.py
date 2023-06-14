import json

from django.http import HttpResponse, HttpResponseBadRequest
from django.views import View
from telegram import Update
from telegram.ext import CallbackContext

from bot.chatbot import telegram_bot_main


def bot_webhook(request, app):
	if request.method == 'POST':
		json_data = json.loads(request.body.decode('utf-8'))
		update = Update.de_json(json_data, app)
		context = CallbackContext(app, update)
		app.process_update(update, context)
	return HttpResponse()


class TelegramBotView(View):
	@staticmethod
	def post(request, *args, **kwargs):
		app = telegram_bot_main()
		return bot_webhook(request, app)

	@staticmethod
	def get(request, *args, **kwargs):
		return HttpResponseBadRequest()
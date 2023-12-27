from os import path
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
env.read_env(path.join(BASE_DIR, 'bot.env'))

# bot definitions
SERVER_URL = env.str('SERVER_URL')
BOT_TOKEN = env.str('TOKEN')
ADMIN_CHAT_ID = env.str('ADMIN_CHAT_ID')
CHANNEL_ID = env.str('CHANNEL_ID')
TRADE_GROUP_ID = env.str('TRADE_GROUP_ID')
SANDBOX_GROUP_ID = env.str('SANDBOX_GROUP_ID')
YANDEX_TOKEN = env.str('YANDEX_TOKEN')
SMS_TOKEN = env.str('SMS_TOKEN')

# chat gpt settings
CHAT_GPT_API_KEY = env.str('CHAT_GPT_API_KEY')
CHAT_GPT_MODEL = 'text-davinci-003'
CHAT_GPT_BOT_PERSONALITY = 'Answer in a professional tone, '

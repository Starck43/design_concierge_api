import os

import django
import environ
from os import path
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "crm.settings")
django.setup()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
env.read_env(path.join(BASE_DIR, '.env'))

# bot definition
SERVER_URL = env.str('SERVER_URL')
BOT_TOKEN = env.str('TOKEN')
CHANNEL_ID = env.str('CHANNEL_ID')
ADMIN_CHAT_ID = env.str('ADMIN_CHAT_ID')
YANDEX_TOKEN = env.str('YANDEX_TOKEN')

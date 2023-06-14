from telegram.error import TelegramError
from telegram.ext import ExtBot


async def check_user_in_channel(channel_id: int, user_id: int, bot: ExtBot) -> bool:
	"""Проверяет наличие пользователя в группе"""
	try:
		member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
		return bool(member)
	except TelegramError:
		return False


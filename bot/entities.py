from typing import Union, List

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove, Message
from telegram.ext import ContextTypes


class TGMessage:
	def __init__(
			self,
			message_id: int = None,
			text: str = None,
			reply_markup: Union[ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove, None] = None,
			**kwargs
	):
		super().__init__(**kwargs)
		self.message_id = message_id
		self.text = text
		self.reply_markup = reply_markup

	@classmethod
	async def display_section_messages(cls, context: ContextTypes.DEFAULT_TYPE, section: dict):
		tg_messages = []
		reply_markup = section.get("reply_markup")
		for message in section.get("messages", []):
			if isinstance(message, cls) and message.text:
				_message = await context.bot.send_message(
					chat_id=context.chat_data.get("chat_id"),
					text=f'*{message.text.upper()}*' if not message.reply_markup and reply_markup else message.text,
					reply_markup=message.reply_markup or reply_markup
				)
				# единожды добавим к сообщению без reply_markup нижнюю клавиатуру
				if not message.reply_markup and reply_markup:
					reply_markup = None
				tg_messages.append(cls.create_message(_message))

		# сохраним новые сообщения, которые отобразили в текущем разделе в messages
		section["messages"] = tg_messages

	@classmethod
	def create_message(cls, message: Message):
		return cls(
			message_id=message.message_id,
			text=message.text_markdown,
			reply_markup=message.reply_markup
		)

	@classmethod
	def create_list(cls, message: Union[Message, List[Message]], only_ids: bool = False):
		messages = message if isinstance(message, list) else [message]
		_messages = []

		for message in messages:
			if isinstance(message, TGMessage):
				_messages.append(message.message_id if only_ids else message)

			elif isinstance(message, Message):
				_messages.append(message.message_id if only_ids else cls.create_message(message))

			elif isinstance(message, int):
				_messages.append(message)

		return _messages

	def to_dict(self):
		return {
			'message_id': self.message_id,
			'text': self.text,
			'reply_markup': self.reply_markup,
		}

	def __repr__(self):
		return f'\n\tTGMessage(message_id={self.message_id}, text="{self.text}", reply_markup={self.reply_markup})'

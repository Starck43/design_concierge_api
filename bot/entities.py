from typing import Union, List

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove, Message


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

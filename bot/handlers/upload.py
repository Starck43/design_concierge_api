from typing import Union, Optional

from telegram import Update, InputMediaPhoto, InputMediaDocument, ReplyKeyboardMarkup, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID
from bot.constants.messages import check_file_size_message
from bot.handlers.common import get_section
from bot.logger import log
from bot.states.main import MenuState
from bot.utils import generate_inline_markup, fetch_user_data


async def prepare_shared_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	""" Функция-обработчик медиа сообщений. Всегда вызывается при добавлении файлов к сообщению """

	message = update.message
	chat_data = context.chat_data
	local_data = context.chat_data.setdefault("local_data", {})
	upload_files = context.chat_data.setdefault('upload_files', {'photo': [], 'document': []})
	section = get_section(context)

	# если пользователь в разделе техподдержка, то не будем выводить инлайн кнопку для отправки
	if not section["state"] == MenuState.SUPPORT:
		button = generate_inline_markup(["Отправить файлы"], callback_data="upload_files")
	else:
		button = section["reply_markup"]

	oversize_message = await check_file_size_message(message)
	if oversize_message:
		chat_data["last_message_id"] = oversize_message.message_id
		return section["state"]

	if message.photo:
		photo = message.photo[-1]
		upload_files['photo'].append({"id": photo.file_id, "caption": message.caption})

	elif message.document:
		document = message.document
		upload_files['document'].append({"id": document.file_id, "caption": message.caption})

	if message.photo or message.document:
		if message.media_group_id and not message.media_group_id == local_data.get("media_group_id"):
			text = f'Файлы подготовлены к отправке!'
			local_data.update({"message.media_group_id": message.media_group_id})
			section["messages"].append(message.message_id)

		elif not message.media_group_id:
			text = f'Файл подготовлен к отправке!'
			section["messages"].append(message.message_id)

		else:
			text = None

	else:
		text = f'Неверный формат файла!'

	if text:
		message = await message.reply_text(text, reply_markup=button)
		chat_data["last_message_id"] = message.message_id
		section["messages"].append(message.message_id)

	return section["state"]


async def upload_files_callback(
		update: Update,
		context: ContextTypes.DEFAULT_TYPE,
		text: str = None,
		reply_markup: Optional[InlineKeyboardMarkup] = None
) -> str:
	""" Колбэк отправки медиа сообщения администратору и сохранения файлов отправителя на сервере """
	query = update.callback_query
	if query:
		await query.answer()
		user = query.from_user
	else:
		query = update
		user = update.effective_user

	chat_data = context.chat_data
	section = get_section(context)

	files = chat_data.get('upload_files')
	if not files:
		message = await query.message.reply_text(f'⚠️ Файлы не были добавлены сюда перед отправкой!')
		chat_data["last_message_id"] = message.message_id
		return section["state"]

	media = {"photo": [], "document": []}
	url_list = []

	for file in files['photo']:
		# подготовим список ссылок для загрузки по ним файлов на сервере
		file_obj = await context.bot.get_file(file["id"])
		url_list.append(file_obj.file_path)
		# подготовим медиа файлы типа фото для отправки администратору в чате
		media["photo"].append(InputMediaPhoto(file["id"], caption=file["caption"]))

	for file in files['document']:
		# подготовим список ссылок для загрузки по ним файлов на сервере
		file_obj = await context.bot.get_file(file["id"])
		url_list.append(file_obj.file_path)
		# подготовим медиа файлы типа документ для отправки администратору в чате
		media["document"].append(InputMediaDocument(file["id"], caption=file["caption"]))

	if media["photo"]:
		await context.bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media["photo"])

	if media["document"]:
		await context.bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media["document"])

	# отправка текста сообщения с кнопкой Ответить
	title = text or f'🗳 *Файлы пришли от @{context.user_data["details"]["username"]}*\nID:{user.id}'
	await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f'{title}', reply_markup=reply_markup)

	# сохраним прикрепленные файлы пользователя на сервере
	res = await fetch_user_data(user.id, 'upload/', data={'files': url_list}, method="POST")
	if res["status_code"] == 201:

		message_text = res["data"].get("message", "Файлы получены!")
		message = await query.message.reply_text(f'*✅ {message_text}*')
		chat_data["last_message_id"] = message.message_id
		chat_data["upload_files"].clear()
		log.info(f'Media files were uploaded on server for user {user.full_name} (ID:{user.id})')

	else:
		log.info(f'Failed to upload files on server for user {user.full_name} (ID:{user.id})')

		# если пользователь в разделе техподдержка, то не будем выводить инлайн кнопку
		if not section["state"] == MenuState.SUPPORT:
			button = generate_inline_markup(["Написать в техподдержку"], callback_data="message_for_admin")
		else:
			button = None

		await query.message.reply_text(
			'*❗️Файлы отправлены с ошибкой!*\n'
			'_Повторите или сообщите о проблеме в разделе "Мой профиль"_',
			reply_markup=button
		)

	return section["state"]


async def share_files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	context.chat_data.setdefault('upload_files', {'photo': [], 'document': []})

	await query.message.edit_text(
		"📎 Добавьте документы или фото на вашем устройстве.",
		reply_markup=None
	)
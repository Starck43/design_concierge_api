import requests
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes

from bot.bot_settings import SERVER_URL, ADMIN_CHAT_ID
from bot.constants.messages import check_file_size_message
from bot.handlers.common import delete_messages_by_key
from bot.logger import log
from bot.utils import generate_inline_keyboard, replace_double_slashes


async def share_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
	chat_data = context.chat_data
	upload_files = chat_data['upload_files']

	await delete_messages_by_key(context, "last_message_id")
	oversize_message = await check_file_size_message(update.message, update.message.document or update.message.photo[-1])

	if oversize_message:
		chat_data["last_message_id"] = oversize_message.message_id
		return

	if update.message.photo:
		photo = update.message.photo[-1]
		upload_files['photo'].append(photo.file_id)

	elif update.message.document:
		document = update.message.document
		upload_files['document'].append(document.file_id)

	else:
		message = await update.message.reply_text("Недопустимый тип файла!\n")
		chat_data["last_message_id"] = message.message_id
		return

	button = generate_inline_keyboard(
		["Отправить файлы"],
		callback_data="upload_files",
	)
	message = await update.message.reply_text(
		"Файл(ы) добавлен!\n"
		"Когда закончите - нажмите кнопку _Отправить_",
		reply_markup=button
	)
	chat_data["last_message_id"] = message.message_id


async def share_files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query
	context.chat_data.setdefault('upload_files', {'photo': [], 'document': []})

	await query.message.edit_text(
		"📎 Откройте документы или фото на вашем устройстве.",
		reply_markup=None
	)


async def upload_files_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	query = update.callback_query

	user = query.from_user
	files = context.chat_data['upload_files']
	file_ids = files['photo'] + files['document']
	error_file_list = []
	url_list = []

	for file_id in file_ids:
		file_obj = await context.bot.get_file(file_id)
		file_path = file_obj.file_path
		url_list.append(file_path)

	# TODO: Доделать api для выгрузки файлов на сервер
	api_url = replace_double_slashes(f'{SERVER_URL}/api/upload')
	response = requests.post(api_url, files={'file': url_list}) # await fetch(api_url, data={'files': url_list}, method="POST")

	if response.status_code == 200:
		await query.message.reply_text(
			"*Файлы успешно отправлены!*\n"
			"После рассмотрения Вы получите ответ.\n"
		)

		title = f'Файлы от пользователя {context.user_data["details"]["name"]} ID:{user.id}'
		if files['photo']:
			media = [InputMediaPhoto(photo_id, caption=title) for photo_id in files['photo']]
			await context.bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media)
		if files['document']:
			for document_id in files['document']:
				await context.bot.send_document(chat_id=ADMIN_CHAT_ID, document=document_id, caption=title)

	else:
		log.info(f'Failed to upload files on server for user {user.full_name} (ID:{user.id}')

		button = generate_inline_keyboard(
			["Написать администратору"],
			callback_data="message_for_admin",
		)
		await query.message.reply_text(
			"*Файлы отправлены с ошибкой!*\n"
			"Повторите процесс или сообщите о проблеме администратору\n",
			reply_markup=button
		)

	context.chat_data.pop("upload_files", None)

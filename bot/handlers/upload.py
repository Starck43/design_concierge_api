from telegram import Update, InputMediaPhoto
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID
from bot.constants.messages import check_file_size_message
from bot.handlers.common import delete_messages_by_key
from bot.logger import log
from bot.utils import generate_inline_markup, fetch_user_data


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

	button = generate_inline_markup(
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
	files = context.chat_data.get('upload_files')
	if not files:
		await query.message.reply_text(f'*Необходимо добавить файлы для отправки!*')
		return

	file_ids = files['photo'] + files['document']
	url_list = []

	for file_id in file_ids:
		file_obj = await context.bot.get_file(file_id)
		file_path = file_obj.file_path
		url_list.append(file_path)

	res = await fetch_user_data(user.id, 'upload/', data={'files': url_list}, method="POST")
	if res["status_code"] == 201:
		message = res["data"]["message"]
		saved_files = res["data"]["saved_files"]
		if saved_files:
			post_message = 'После рассмотрения Вы получите ответ.'
		else:
			post_message = 'Рекомендуем повторить отправку файлов еще раз или дождитесь ответа от администратора.'

		await query.message.reply_text(f'*{message}*\n{post_message}')

		title = f'Файлы отправлены пользователем {context.user_data["details"]["name"]} ID:{user.id}'
		if files['photo']:
			media = [InputMediaPhoto(photo_id, caption=title) for photo_id in files['photo']]
			await context.bot.send_media_group(chat_id=ADMIN_CHAT_ID, media=media)

		if files['document']:
			for document_id in files['document']:
				await context.bot.send_document(chat_id=ADMIN_CHAT_ID, document=document_id, caption=title)

		context.chat_data.pop("upload_files", None)

	else:
		log.info(f'Failed to upload files on server for user {user.full_name} (ID:{user.id})')

		button = generate_inline_markup(
			["Написать администратору"],
			callback_data="message_for_admin",
		)

		await query.message.reply_text(
			"*Файлы отправлены с ошибкой!*\n"
			"Повторите процесс или сообщите о проблеме администратору\n",
			reply_markup=button
		)

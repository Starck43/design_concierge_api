from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.bot_settings import ADMIN_CHAT_ID
from bot.constants.keyboards import SEND_CONFIRMATION_KEYBOARD, REPLY_KEYBOARD
from bot.constants.patterns import CANCEL_PATTERN, SEND_PATTERN
from bot.handlers.common import (
	get_section, go_back_section, edit_or_reply_message, load_support_data, update_support_data
)
from bot.handlers.upload import upload_files_callback
from bot.states.main import MenuState
from bot.utils import generate_inline_markup, generate_reply_markup, match_query


async def ask_question_to_admin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
	user_details = context.user_data["details"]
	chat_data = context.chat_data
	local_data = chat_data.setdefault("local_data", {})
	upload_files = chat_data.get("upload_files", {})

	section = get_section(context)
	state = section["state"]
	query_message = update.message.text
	message = None

	if match_query(CANCEL_PATTERN, query_message):
		state = await go_back_section(update, context, "back")
		message = await update.message.reply_text(
			"❕Отправка сообщения была прервана!",
			reply_markup=section["reply_markup"]
		)

	# если это ответ на сообщение пользователя через колбэк
	elif local_data.get("reply_to_message"):
		name = local_data["reply_to_message"].get("name")
		chat_id = local_data["reply_to_message"].get("chat_id")
		reply_to_message_id = local_data["reply_to_message"].get("reply_to_message_id")
		answer_text = f'*🔔 Ответ от техподдержки:*\nНомер обращения: *#{reply_to_message_id}*\n'

		try:
			await context.bot.send_message(
				chat_id=chat_id,
				text=f"{answer_text}`{query_message}`",
				reply_to_message_id=reply_to_message_id
			)

		except TelegramError:
			question_text = local_data["reply_to_message"].get("question", "")
			await context.bot.send_message(chat_id=chat_id, text=f'{answer_text}_“{question_text}”_\n`{query_message}`')

		# сохраним обращение на сервере
		user_message = await update_support_data(
			update.message,
			context,
			user_id=chat_id,
			message_id=reply_to_message_id,
			data={"answer": query_message}
		)
		if user_message and user_message["is_replied"]:
			text = "Сообщение обновлено. Обращение закрыто!"
		else:
			text = "❗️Сообщение не обновилось на сервере!"

		message = await update.message.reply_text(
			f'✅ Ответ отправлен пользователю:\n*{name}*\n_{text}_\nНомер обращения: *#{reply_to_message_id}*',
			reply_markup=section["reply_markup"]
		)
		section["messages"].append(message.message_id)
		local_data["reply_to_message"].clear()

	# обращение через подраздел Профиль -> Техподдержка
	elif local_data.get("message_for_admin"):
		menu_markup = generate_reply_markup([SEND_CONFIRMATION_KEYBOARD])
		section["reply_markup"] = menu_markup
		message_for_admin = local_data["message_for_admin"]
		no_attached_files = not (upload_files.get("photo") or upload_files.get("document"))

		# текст прилетел впервые после ввода сообщения
		if not message_for_admin["question"]:
			message_for_admin["question"] = query_message
			message_for_admin["message_id"] = update.message.message_id

			# если нет прикрепленных файлов
			if no_attached_files:
				message = await update.message.reply_text(
					text=f'Если еще необходимо поделиться медиа файлами, то добавьте их сюда перед отправкой',
					reply_markup=menu_markup
				)
				chat_data["last_message_id"] = message.message_id
				return state

		elif not match_query(SEND_PATTERN, query_message):
			message = await edit_or_reply_message(
				context,
				text=f'Сообщение уже создано, осталось только отправить',
				message=chat_data.get("last_message_id"),
				message_type="info",
				return_message_id=False,
				reply_markup=menu_markup
			)
			chat_data["last_message_id"] = message.message_id
			return state

		# далее начинается подготовка к отправке уведомления и регистрация обращения на сервере
		message_id = message_for_admin["message_id"]
		message_text = f'🔔 Вопрос в техподдержку от *@{user_details["name"]}* (ID:{user_details["user_id"]})\n'
		message_text += f'*#{message_id}*: {message_for_admin["question"]}'

		inline_markup = generate_inline_markup(
			REPLY_KEYBOARD,
			callback_data=f'reply_to_{user_details["user_id"]}__message_id_{message_id}'
		)
		# сохраним обращение пользователя с вопросом в БД
		user_message = await update_support_data(
			update.message,
			context,
			user_id=user_details["user_id"],
			message_id=message_id,
			data={"question": message_for_admin["question"]}
		)

		# если нет прикрепленных файлов, то отправим администратору только текст сообщения
		if no_attached_files:
			await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message_text, reply_markup=inline_markup)

		# если были приложены файлы, то отправим и файлы и текст сообщения одним медиа сообщением
		else:
			if not user_message:
				message_text += f'\nСообщение отправлено без регистрации в базе данных!'
			await upload_files_callback(update, context, text=message_text, reply_markup=inline_markup)

		message_for_admin.clear()
		state = await go_back_section(update, context, "back")
		section = get_section(context)

		# TODO: добавить дату обращения и дату ответа к сообщениям
		message = await update.message.reply_text(
			text=f'✅ Создано новое обращение с номером *#{message_id}*\n'
			     f'После рассмотрения Вам придет ответ.',
			reply_markup=section["reply_markup"]
		)
		context.chat_data["last_message_id"] = message.message_id

	# отправим введенный текст сразу администратору бота, если пользователь не находится в секции Техподдержка
	elif not section["state"] == MenuState.SUPPORT:
		message_id = update.message.message_id
		message_text = f'🔔 Сообщение администратору от *{user_details["name"]}* (ID:{user_details["user_id"]})\n\n' \
		               f'`{query_message}`'
		# обновим сообщение на сервере
		user_message = await update_support_data(
			update.message,
			context,
			user_id=user_details["user_id"],
			message_id=message_id,
			data={"question": query_message}
		)
		if user_message:
			text = f"Номер обращения: *#{message_id}*"
		else:
			text = "_Номер регистрации не присвоен!_"

		inline_markup = generate_inline_markup(
			REPLY_KEYBOARD,
			callback_data=f'reply_to_{user_details["user_id"]}__message_id_{message_id}'
		)
		await context.bot.send_message(
			chat_id=ADMIN_CHAT_ID,
			text=f'{message_text}\n{text}',
			reply_markup=inline_markup
		)

		context.chat_data["last_message_id"] = await edit_or_reply_message(
			context,
			text=f"✅ Ваш вопрос отправлен администратору Консьерж Сервис!\n{text}",
			message=chat_data.get("last_message_id"),
			reply_markup=section["reply_markup"]
		)

	if message:
		section["messages"].append(message.message_id)

	return state


async def reply_to_user_message_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк ответа администратором на сообщение от пользователя """

	query = update.callback_query
	await query.answer()

	query_data = query.data.rsplit("__")
	user_id = query_data[0].lstrip("reply_to_")
	message_id = int(query_data[1].lstrip("message_id_"))

	section = get_section(context)
	local_data = context.chat_data.setdefault("local_data", {})
	user_message = await load_support_data(query.message, context, message_id=message_id, user_id=user_id)
	if user_message and user_message["is_replied"]:
		message = await query.message.reply_text(
			f'Вопрос был ранее закрыт!\nОбращение: *#{user_message.get("message_id")}*',
			reply_markup=section["reply_markup"]
		)
		section["messages"].append(message.message_id)
		return section["state"]

	else:
		message = await query.message.reply_text(f'Что ответить пользователю?')

	reply_to_message = local_data.setdefault('reply_to_message', {**user_message})
	reply_to_message["reply_to_message_id"] = user_message["message_id"]
	reply_to_message["message_id"] = message.message_id  # сохраним id сообщения для замены на новое после ответа

	return MenuState.SUPPORT

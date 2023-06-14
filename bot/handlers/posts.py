from telegram import Update, InputMediaPhoto
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ConversationHandler

from bot.bot_settings import CHANNEL_ID
from bot.constants.menus import main_menu, post_menu
from bot.utils import allowed_roles, generate_reply_keyboard
from bot.states.post import PostState


@allowed_roles(['creator', 'administrator'], channel_id=CHANNEL_ID)
async def create_new_post(update: Update, context: CallbackContext):
	context.user_data['post'] = {'text': '', 'photo': []}

	await update.message.reply_text(
		"Новый пост.\n"
		"Для добавления контента используйте меню.",
		reply_markup=post_menu
	)

	return PostState.CHOOSING


async def process_post_text(update, context):
	text = update.message.text
	post_data = context.user_data['post']

	if post_data['text'] == "":
		post_text = "Текст добавлен"
	else:
		post_text = "Текст заменен на новый"

	post_data.update({'text': text})

	await update.message.reply_text(
		post_text,
		reply_markup=post_menu
	)

	return PostState.CHOOSING


async def process_post_photo(update, context):
	photo = update.message.photo[-1]
	context.user_data['post']['photo'].append(photo.file_id)
	await update.message.reply_text(
		"Фото добавлено к посту.",
		reply_markup=post_menu
	)

	return PostState.CHOOSING


async def send_post(update, context) -> str:
	post = context.user_data['post']
	text = post['text']
	photo_ids = post['photo']

	if not text and not photo_ids:
		await update.message.reply_text("Пожалуйста, добавьте текст или фото к посту.")
		return PostState.CHOOSING

	media = [InputMediaPhoto(photo_id, caption=text, parse_mode=ParseMode.HTML) for photo_id in photo_ids]
	await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media)
	await update.message.reply_text("Пост успешно отправлен в канал.")

	context.user_data.clear()
	return ConversationHandler.END


async def cancel_post(update: Update, context: CallbackContext):
	user_group = context.user_data["details"]["group"]
	keyboard = main_menu.get(user_group, None)
	menu_markup = generate_reply_keyboard(keyboard)
	await update.message.reply_text(
		"Отправка поста отменена.",
		reply_markup=menu_markup
	)
	context.user_data.clear()
	return ConversationHandler.END

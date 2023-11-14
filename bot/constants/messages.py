from typing import List, Optional, Union

from telegram import (
	Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Document, PhotoSize
)
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	CONFIRM_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SUBMIT_REG_KEYBOARD, CANCEL_REG_KEYBOARD, START_REG_KEYBOARD,
	SEGMENT_KEYBOARD, REG_GROUP_KEYBOARD, REPEAT_KEYBOARD
)
from bot.constants.menus import continue_reg_menu, cancel_reg_menu, start_menu, done_menu
from bot.utils import (
	generate_inline_markup, generate_reply_markup, data_list_to_string, fetch_user_data
)


async def offer_for_registration_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "ℹ️ Чтобы начать пользоваться Консьерж Сервис, необходимо пройти регистрацию!",
		reply_markup=generate_reply_markup([START_REG_KEYBOARD])
	)


async def denied_access_message(message: Message) -> None:
	# TODO: Создать логику отправки сообщений администратору
	inline_markup = generate_inline_markup(
		["Написать администратору"],
		callback_data="message_for_admin",
	)
	await message.reply_text(
		f'*Доступ в Консьерж для Дизайнера закрыт!*',
		reply_markup=done_menu
	)
	await message.reply_text(
		f'Можете задать вопрос администратору сервиса.',
		reply_markup=inline_markup
	)


async def submit_reg_data_message(message: Message) -> Message:
	inline_markup = generate_inline_markup(
		[SUBMIT_REG_KEYBOARD + CANCEL_REG_KEYBOARD],
		callback_data=["approve", "cancel"],
		vertical=True
	)

	return await message.reply_text(
		f'ℹ️ В случае отмены Вам придется заново пройти регистрацию.\n'
		f'Если захотите что-то изменить, то в будущем у Вас появится такая возможность.\n',
		reply_markup=inline_markup
	)


async def success_registration_message(message: Message) -> None:
	await message.reply_text(
		f'*Спасибо за регистрацию!*\n'
		f'Вам предоставлен доступ в Консьерж Сервис.',
		reply_markup=start_menu
	)


async def restricted_registration_message(message: Message) -> None:
	await message.reply_text(
		f'*Спасибо за регистрацию!*\n'
		f'_В настоящий момент доступ в Консьерж Сервис ограничен, '
		f'так как Вы не указали при регистрации ссылку на свои ресурсы\n'
		f'Вы можете самостоятельно добавить ссылку в своем профиле '
		f'или прикрепить нам фото документов, подтверждающих что Вы являетесь дизайнером или архитектором_',
		reply_markup=start_menu
	)


# async def fail_registration_message(
# 		message: Message,
# 		reply_markup: Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]] = None,
# 		text: str = None,
# ) -> None:
# 	await message.reply_text(
# 		text or "⚠️ Регистрация не была завершена из-за ошибки.\n"
# 		        "Попробуйте повторить регистрацию снова или сообщите о проблеме администратору Консьерж Сервис!",
# 		reply_markup=reply_markup
# 	)


async def yet_registered_message(message: Message) -> Message:
	return await message.reply_text(
		'*Вы уже зарегистрированы!*\n'
		'Можете начать пользоваться Консьерж Сервис\n',
		reply_markup=start_menu
	)


async def interrupt_reg_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or "*❌ Регистрация отменена!*\n",
		reply_markup=ReplyKeyboardRemove()
	)


async def share_link_message(message: Message, link: str, link_text: str, text: str) -> None:
	inline_markup = InlineKeyboardMarkup([[InlineKeyboardButton(link_text, url=link, callback_data="share_link")]])
	await message.reply_text(text, reply_markup=inline_markup)


async def introduce_reg_message(message: Message) -> Message:
	await message.reply_text(
		"Для начала давайте познакомимся.",
		reply_markup=cancel_reg_menu,
	)

	return await message.reply_text(
		"Кого Вы представляете?",
		reply_markup=generate_inline_markup(REG_GROUP_KEYBOARD),
	)


async def select_categories_message(
		message: Message,
		category_list: List,
		title: str = None,
		message_id: Optional[int] = None
) -> Optional[Message]:
	if message_id is None:
		inline_markup = generate_inline_markup(
			category_list,
			item_key="name",
			callback_data="id",
			callback_data_prefix="category_",
			vertical=True
		)
		return await message.reply_text(
			title or 'Список категорий:',
			reply_markup=inline_markup,
		)

	else:
		categories = data_list_to_string(category_list, field_names="name", separator="\n☑️ ")

		await message.get_bot().edit_message_text(
			title or f'*Выбранные категории:*'
			         f'\n☑️ {categories}',
			chat_id=message.chat_id,
			message_id=message_id,
		)


async def required_category_warn_message(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
		text: str = None
) -> Message:
	message = await message.reply_text(
		text or "⚠️ Необходимо выбрать хотя бы одну категорию!",
		reply_markup=reply_markup,
	)
	context.chat_data["warn_message_id"] = message.message_id
	return message


async def only_in_list_warn_message(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
		text: str = None
) -> Message:
	message = await message.reply_text(
		text or '⚠️ Можно выбрать категорию только из списка!\n',
		reply_markup=reply_markup,
	)
	context.chat_data["warn_message_id"] = message.message_id
	return message


async def not_validated_warn_message(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
		text: str = None
) -> Message:
	message = await message.reply_text(
		text or "⚠️ Ответ должен обязательно содержать число!\n",
		reply_markup=reply_markup,
	)
	context.chat_data["warn_message_id"] = message.message_id
	return message


async def show_main_region_message(message: Message, text: str = None) -> Message:
	reply_markup = generate_reply_markup(
		[CANCEL_REG_KEYBOARD],
		one_time_keyboard=False,
		share_location=True
	)

	return await message.reply_text(
		text or "Укажите свой основной регион или поделитесь местоположением для автоопределения.",
		reply_markup=reply_markup,
	)


async def show_additional_regions_message(message: Message) -> Message:
	return await message.reply_text(
		text="Добавьте дополнительные регионы в которых Вы, возможно, работаете и нажмите *Продолжить*",
		reply_markup=continue_reg_menu
	)


async def added_new_region_message(message: Message, text: str) -> None:
	await message.reply_text(
		f'☑️ _{text.upper()} добавлен!_',
		reply_markup=continue_reg_menu
	)


async def update_top_regions_message(context: ContextTypes.DEFAULT_TYPE) -> None:
	chat_data = context.chat_data
	top_regions_list = chat_data["top_regions"]

	if not top_regions_list:
		if "last_message_id" in chat_data:
			await context.bot.delete_message(
				chat_id=chat_data["chat_id"],
				message_id=chat_data["last_message_id"],
			)

			del chat_data["last_message_id"]
		return

	inline_markup = generate_inline_markup(
		top_regions_list,
		item_key="name",
		callback_data="id",
		callback_data_prefix="region_"
	)

	if "last_message_id" not in chat_data:
		message = await context.bot.send_message(
			chat_id=chat_data["chat_id"],
			text=f'Можете выбрать регион из списка ниже или ввести свой:',
			reply_markup=inline_markup,
		)
		chat_data["last_message_id"] = message.message_id  # Сохраним для изменения сообщения

	else:
		await context.bot.edit_message_reply_markup(
			chat_id=chat_data["chat_id"],
			message_id=chat_data["last_message_id"],
			reply_markup=inline_markup
		)


async def confirm_region_message(message: Message, text: str = None) -> Message:
	inline_markup = generate_inline_markup(
		[CONFIRM_KEYBOARD],
		callback_data=["yes", "no"],
		callback_data_prefix="choose_region_"
	)
	return await message.reply_text(
		f'{text}, все верно?',
		reply_markup=inline_markup
	)


async def region_selected_warn_message(message: Message, context: ContextTypes.DEFAULT_TYPE, text: str = None) -> None:
	message = await message.reply_text(
		f'⚠️ *{text}* был уже выбран!\n',
		reply_markup=continue_reg_menu,
	)
	context.chat_data["warn_message_id"] = message.message_id


async def not_found_region_message(message: Message, context: ContextTypes.DEFAULT_TYPE, text: str = None) -> None:
	message = await message.reply_text(
		f"⚠️ Регион с названием '{text or message.text}' не найден!\n"
		f"Введите корректное название региона.\n",
		reply_markup=continue_reg_menu,
	)
	context.chat_data["warn_message_id"] = message.message_id


async def not_detected_region_message(message: Message, context: ContextTypes.DEFAULT_TYPE, text: str = None) -> None:
	message = await message.reply_text(
		text or "⚠️ Не удалось определить местоположение.\n"
		        "Введите регион самостоятельно.",
		reply_markup=continue_reg_menu,
	)
	context.chat_data["warn_message_id"] = message.message_id


async def required_region_warn_message(message: Message, context: ContextTypes.DEFAULT_TYPE, text: str = None) -> None:
	message = await message.reply_text(
		text or '⚠️ Необходимо указать хотя бы один регион!',
		reply_markup=cancel_reg_menu,
	)
	context.chat_data["warn_message_id"] = message.message_id


async def offer_to_input_socials_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or 'Укажите свой сайт или соцсеть или другой ресурс, где можно увидеть ваши работы:',
		reply_markup=continue_reg_menu,
	)


async def incorrect_socials_warn_message(message: Message) -> None:
	await message.reply_text(
		'⚠️ Адрес должен начинаться с "http"',
		reply_markup=continue_reg_menu,
	)


async def offer_to_select_segment_message(message: Message) -> Message:
	buttons = generate_inline_markup(
		SEGMENT_KEYBOARD,
		callback_data_prefix="segment_",
		vertical=True
	)

	return await message.reply_text(
		"🎯 Укажите сегмент, в котором Вы работаете:",
		reply_markup=buttons
	)


async def offer_to_input_address_message(message: Message) -> Message:
	return await message.reply_text(
		"*Введите свой адрес:*",
		reply_markup=continue_reg_menu,
	)


async def success_save_rating_message(message: Message, user_data: dict) -> Message:
	return await message.reply_text(
		f'Рейтинг успешно сохранен!\n'
		f'Спасибо за оценку ♥️\n\n'
		f'*Личный рейтинг:* ⭐_{user_data["related_total_rating"]}_\n️'
		f'*Общий рейтинг:* ⭐_{user_data["total_rating"]}️_\n'
	)


async def yourself_rate_warning_message(message: Message) -> Message:
	return await message.reply_text(
		f'*⚠️ Нельзя выставлять оценки самому себе!*',
	)


async def add_new_user_message(message: Message, category: dict) -> Message:
	inline_markup = generate_inline_markup(
		["🆕 Добавить компанию"],
		callback_data=str(category["group"]),
		callback_data_prefix="add_new_user_",
	)

	return await message.reply_text(
		f'Порекомендовать компанию в категории *{category["name"].upper()}*',
		reply_markup=inline_markup
	)


async def verify_by_sms_message(message: Message) -> Message:
	await message.reply_text(
		"Введите полученный код из смс:",
		reply_markup=cancel_reg_menu,
	)
	button = generate_inline_markup([REPEAT_KEYBOARD], callback_data="input_phone")
	return await message.reply_text(
		f'_Если смс код не пришел или ошибка в номере, то повторите операцию._',
		reply_markup=button,
	)


async def continue_reg_message(message: Message, text: str = None) -> None:
	await message.reply_text(
		text or "Возможно, с Вами свяжутся по указанному номеру, чтобы удостовериться что это именно Вы\n"
		        "_Нажмите Продолжить для завершения регистрации_",
		reply_markup=continue_reg_menu
	)


async def offer_to_cancel_action_message(message: Message, text: str = None) -> Message:
	inline_markup = generate_inline_markup([CONFIRM_KEYBOARD], callback_data=["yes", "no"])
	return await message.reply_text(
		text or '*❗Несохраненные данные будут утеряны❗️*\n'
		        'Все равно продолжить?',
		reply_markup=inline_markup,
	)


async def share_files_message(message: Message, text: str) -> Message:
	inline_markup = generate_inline_markup(
		["Прикрепить файлы"],
		callback_data="share_files",
	)
	return await message.reply_text(text, reply_markup=inline_markup)


async def check_file_size_message(message: Message, file: Union[Document, PhotoSize] = None, limit: int = 5) -> Message:
	if file and file.file_size > limit * 1024 * 1024:  # 5 MB
		return await message.reply_text(
			f'⚠️ Превышен размер файла!\n'
			f'_Максимально допустимый размер - 5мб_'
		)


async def send_unknown_question_message(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
		text: str = None
) -> Message:
	message = await message.reply_text(
		text or f'❗️К сожалению, я не смог разобрать запрос.\n'
		        f'Нажмите на интересующий раздел ниже или повторите иначе свой запрос',
		reply_markup=reply_markup
	)
	context.chat_data["warn_message_id"] = message.message_id
	return message


async def place_new_order_message(message: Message, category: dict = None, text: str = None) -> Message:
	""" Инлайн сообщение с размещением нового заказа """
	inline_markup = generate_inline_markup(["➕ Создать"], callback_data="place_order")
	title = f'Разместить новый заказ'
	if category:
		title += f' в категории {category["name"].upper()}'

	return await message.reply_text(
		f'_{text or title}_',
		reply_markup=inline_markup,
	)


async def select_events_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_markup(
		["Местные", "Российские", "Международные"],
		callback_data_prefix="event_type_",
		vertical=True
	)

	return await message.reply_text(
		text or f'Какие мероприятия интересуют?',
		reply_markup=buttons,
	)


async def choose_sandbox_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_markup(
		DESIGNER_SANDBOX_KEYBOARD,
		callback_data_prefix="sandbox_type_",
		vertical=False
	)
	return await message.reply_text(
		text or f'Выберите интересующую группу:',
		reply_markup=buttons,
	)


async def failed_questionnaire_message(message: Message) -> Message:
	return await message.reply_text(
		text='*Анкетирование было остановлено!*\n',
		reply_markup=start_menu
	)


async def empty_questionnaire_list_message(message: Message) -> Message:
	return await message.reply_text(
		text='❗️Вы не выбрали ни одного поставщика\n',
		reply_markup=start_menu
	)


async def offer_for_questionnaire_message(
		message: Message,
		reply_markup: Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]] = None
) -> Message:
	return await message.reply_text(
		"Анкетирование состоит из двух этапов:\n"
		"1. Выбор поставщиков с кем доводилось работать, сгруппированных по видам деятельности.\n"
		"2. Оценка выбранных поставщиков по нескольким критериям.\n\n",
		reply_markup=reply_markup,
	)


async def show_questionnaire_message(message: Message, text: str = None, link_text: str = None) -> Message:
	button = generate_inline_markup(
		[link_text or "Начать анкетирование"],
		callback_data="questionnaire",
	)

	return await message.reply_text(
		text or "Для составления рейтинга поставщиков, предлагаем пройти анкетирование.",
		reply_markup=button,
	)


async def success_questionnaire_message(message: Message) -> Message:
	return await message.reply_text(
		text='*✅ Анкетирование успешно завершено!*\n'
		     f'_Ваши результаты будут учтены в общем рейтинге поставщиков._\n'
		     f'_Спасибо за уделенное время_',
		reply_markup=start_menu
	)


async def send_notify_message(
		context: ContextTypes.DEFAULT_TYPE,
		user_id: Union[int, list],
		text: str,
		from_name: str = None,
) -> None:
	"""
    Функция для отправки уведомлений пользователям.
    :param context: Контекст выполнения функции.
    :param user_id: Идентификатор или список идентификаторов пользователей.
    :param text: Текст уведомления.
    :param from_name: Имя отправителя уведомления (необязательный параметр).
    :return: None
    """
	if not user_id and not text:
		return

	if isinstance(user_id, int):
		user_id = [user_id]

	for _id in user_id:
		res = await fetch_user_data(_id)
		data = res["data"]
		if data and data["user_id"]:
			await context.bot.send_message(
				chat_id=data["user_id"],
				text=f'*❗️Уведомление {"от " + from_name if from_name else ""}*\n\n{text}'
			)

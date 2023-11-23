from asyncio import sleep
from typing import Optional, Union, Literal

from telegram import (
	Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	CONFIRM_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SUBMIT_REG_KEYBOARD, CANCEL_REG_KEYBOARD, START_REG_KEYBOARD,
	SEGMENT_KEYBOARD, REPEAT_KEYBOARD, SEARCH_OPTIONS_KEYBOARD, CONTINUE_KEYBOARD
)
from bot.constants.menus import continue_reg_menu, cancel_reg_menu, start_menu
from bot.constants.static import CAT_GROUP_DATA, MAX_RATE, RATE_BUTTONS
from bot.utils import (
	generate_inline_markup, generate_reply_markup, fetch_user_data, update_inline_markup
)


async def offer_for_registration_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "ℹ️ Чтобы начать пользоваться Консьерж Сервис, необходимо пройти регистрацию!",
		reply_markup=generate_reply_markup([START_REG_KEYBOARD])
	)


async def denied_access_message(message: Message) -> None:
	inline_markup = generate_inline_markup(
		["Написать администратору"],
		callback_data="message_for_admin",
	)
	await message.reply_text(
		f'*Доступ в Консьерж для Дизайнера закрыт!*',
		reply_markup=inline_markup
	)


async def submit_reg_data_message(message: Message) -> Message:
	inline_markup = generate_inline_markup(
		[SUBMIT_REG_KEYBOARD + CANCEL_REG_KEYBOARD],
		callback_data=["approve", "cancel"],
		vertical=True
	)

	return await message.reply_text(
		f'❗ В случае отмены Вам придется заново пройти регистрацию.\n'
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
		f'*Спасибо за регистрацию! 🤝*\n'
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
		'*❕Вы уже зарегистрированы!*\n'
		'Можете начать пользоваться Консьерж Сервис\n',
		reply_markup=start_menu
	)


async def interrupt_reg_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(text or "*🚫 Регистрация отменена!*\n", reply_markup=ReplyKeyboardRemove())


async def share_link_message(message: Message, link: str, link_text: str, text: str) -> None:
	inline_markup = InlineKeyboardMarkup([[InlineKeyboardButton(link_text, url=link, callback_data="share_link")]])
	await message.reply_text(text, reply_markup=inline_markup)


async def input_regions_message(
		message: Message,
		status: Literal["main", "additional"] = "additional",
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
) -> int:
	if not reply_markup:
		reply_markup = generate_reply_markup([CONTINUE_KEYBOARD], one_time_keyboard=False, share_location=True)

	if status == "main":
		text = "Введите свой основной рабочий регион или воспользуйтесь автоопределением."
	else:
		text = "Если есть другие регионы где вы представлены, то введите их и/или нажмите *Продолжить*"

	message = await message.reply_text(text, reply_markup=reply_markup)
	return message.message_id


async def confirm_region_message(message: Message, text: str = None) -> int:
	inline_markup = generate_inline_markup(
		[CONFIRM_KEYBOARD],
		callback_data=["yes", "no"],
		callback_data_prefix="choose_region_"
	)
	message = await message.reply_text(text, reply_markup=inline_markup)
	return message.message_id


async def add_region_warn_message(message: Message, text: str = None) -> int:
	message = await message.reply_text(f'⚠️ Регион *{text}* уже был добавлен!', reply_markup=continue_reg_menu)
	return message.message_id


async def not_found_region_message(message: Message, text: str = None) -> int:
	message = await message.reply_text(
		f"⚠️ Регион с названием *{text}* не найден!\n"
		f"Введите корректное название региона.\n",
		reply_markup=continue_reg_menu,
	)
	return message.message_id


async def incorrect_socials_warn_message(message: Message) -> None:
	await message.reply_text(
		'⚠️ Адрес должен начинаться с "http://"',
		reply_markup=continue_reg_menu,
	)


async def offer_to_select_segment_message(message: Message, title: str = None) -> Message:
	buttons = generate_inline_markup(SEGMENT_KEYBOARD, callback_data_prefix="segment_", vertical=True)
	return await message.reply_text(
		f'🎯 {title or "Выберите сегмент, в котором Вы работаете"}:',
		reply_markup=buttons
	)


async def offer_to_select_rating_message(message: Message, title: str = None, active_value: int = None) -> Message:
	buttons = [[RATE_BUTTONS[3]] * MAX_RATE]
	callback_data = list(range(1, MAX_RATE + 1))
	rate_markup = generate_inline_markup(buttons, callback_data=callback_data, callback_data_prefix="rating_")
	if active_value:
		rate_markup = update_inline_markup(
			inline_keyboard=rate_markup.inline_keyboard,
			active_value=str(active_value),
			button_type='rate'
		)
	title = f'⭐️ {title or "Выберите рейтинг"}:'
	return await message.reply_text(title, reply_markup=rate_markup)


async def offer_to_input_address_message(message: Message) -> Message:
	return await message.reply_text(
		"*🏠 Укажите свой рабочий адрес*",
		reply_markup=continue_reg_menu,
	)


async def success_save_rating_message(message: Message, user_data: dict) -> Message:
	return await message.reply_text(
		f'*✅ Рейтинг успешно сохранен!*\n'
		f'_Личный рейтинг: ⭐{user_data["related_total_rating"]}_\n️'
		f'_Общий рейтинг: ⭐{user_data["total_rating"]}️_\n'
	)


async def yourself_rate_warning_message(message: Message) -> Message:
	return await message.reply_text(
		f'*❗️Нельзя выставлять оценки самому себе!*',
	)


async def add_new_user_message(message: Message, category: dict) -> Message:
	inline_markup = generate_inline_markup(
		["➕ Добавить"],
		callback_data=str(category["group"]),
		callback_data_prefix="add_new_user_",
	)

	group_data = CAT_GROUP_DATA[category["group"]]
	group_title = group_data["title"][:-1] + "а"
	return await message.reply_text(
		f'_🗣 Порекомендовать нового {group_title.lower()} в категории_ '
		f'*{category["name"].upper()}*',
		reply_markup=inline_markup
	)


async def repeat_input_phone_message(message: Message) -> Message:
	inline_markup = generate_inline_markup([REPEAT_KEYBOARD], callback_data="input_phone")

	return await message.reply_text(
		f'❕Если смс код не пришел или ошиблись в наборе номера, то повторите операцию',
		reply_markup=inline_markup
	)


async def continue_reg_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "Нажмите ➡️ для завершения регистрации",
		reply_markup=continue_reg_menu
	)


async def offer_to_cancel_action_message(message: Message, text: str = None) -> Message:
	inline_markup = generate_inline_markup([CONFIRM_KEYBOARD], callback_data=["yes", "no"])
	return await message.reply_text(
		text or '*⁉️ Несохраненные данные будут утеряны*\nВсе равно продолжить?',
		reply_markup=inline_markup
	)


async def share_files_message(message: Message, text: str) -> Message:
	inline_markup = generate_inline_markup(
		["📎 Прикрепить файлы"],
		callback_data="share_files",
	)
	return await message.reply_text(text, reply_markup=inline_markup)


async def check_file_size_message(message: Message, limit: int = 5) -> Message:
	file = message.document or message.photo[-1]
	if file and file.file_size > limit * 1024 * 1024:
		return await message.reply_text(
			f'⚠️ Превышен допустимый размер файла!\n_Максимальный размер:_ *{limit}МБ*'
		)


async def send_unknown_question_message(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
		text: str = None
) -> Message:
	message = await message.reply_text(
		text or f'⁉️ К сожалению, я не смог разобрать вопрос\n'
		        f'Выберите раздел в меню или повторите иначе свой запрос',
		reply_markup=reply_markup
	)
	context.chat_data["warn_message_id"] = message.message_id
	return message


async def place_new_order_message(message: Message, category: dict = None, text: str = None) -> Message:
	""" Инлайн сообщение с размещением нового заказа """
	inline_markup = generate_inline_markup(["➕ Создать"], callback_data="place_order")
	title = f'_Разместить новый заказ_'
	if category:
		title += f'_ на бирже в категории_\n*{category["name"].upper()}*'

	return await message.reply_text(
		f'{text or title}',
		reply_markup=inline_markup,
	)


async def select_search_options_message(message: Message, cat_group: int) -> Message:
	keyboard = SEARCH_OPTIONS_KEYBOARD
	if cat_group != 2:
		keyboard = SEARCH_OPTIONS_KEYBOARD.copy()[:-1]

	inline_markup = generate_inline_markup(keyboard, vertical=True)
	return await message.reply_text(
		"🖍 Введите поисковые слова и/или выберите опции из списка:",
		reply_markup=inline_markup
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
		text='*🛑 Анкетирование было остановлено!*\n',
		reply_markup=start_menu
	)


async def empty_questionnaire_list_message(message: Message) -> Message:
	return await message.reply_text(
		text='⚠️ Вы не выбрали ни одного поставщика!',
		reply_markup=start_menu
	)


async def offer_for_questionnaire_message(
		message: Message,
		reply_markup: Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup]] = None
) -> Message:
	return await message.reply_text(
		"Анкетирование состоит из двух этапов:\n"
		"1. _Выбор поставщиков с кем доводилось работать, сгруппированных по видам деятельности._\n"
		"2. _Оценка выбранных поставщиков по нескольким критериям._\n\n",
		reply_markup=reply_markup,
	)


async def show_questionnaire_message(message: Message, text: str = None, link_text: str = None) -> Message:
	button = generate_inline_markup(
		[link_text or "Начать анкетирование"],
		callback_data="questionnaire",
	)

	return await message.reply_text(
		text or "❕Для составления рейтинга поставщиков, предлагаем пройти анкетирование.",
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
				text=f'*🛎 Уведомление {"от " + from_name if from_name else ""}*\n\n{text}'
			)

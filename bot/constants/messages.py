from typing import Optional, Union, Literal

from telegram import (
	Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	CONFIRM_KEYBOARD, SUBMIT_REG_KEYBOARD, CANCEL_KEYBOARD, START_REG_KEYBOARD,
	SEGMENT_KEYBOARD, REPEAT_KEYBOARD, SEARCH_OPTIONS_KEYBOARD, CONTINUE_KEYBOARD, REG_GROUP_KEYBOARD
)
from bot.constants.menus import continue_menu, start_menu
from bot.constants.static import CAT_GROUP_DATA, MAX_RATE, RATE_BUTTONS
from bot.utils import (
	generate_inline_markup, generate_reply_markup, update_inline_markup
)


async def join_chat_message(
		message: Message,
		link: str,
		text: str = None,
		subtext: str = "",
		chat_name: str = "",
) -> Message:

	join_button = generate_inline_markup([f'Присоединиться к {subtext.split(" ")[-1]}'], url=link)
	return await message.reply_text(
		text=text or f'Присоединяйтесь к{subtext} *Консьерж для Дизайнера {chat_name}*',
		reply_markup=join_button
	)


async def offer_for_registration_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "❕Чтобы начать пользоваться Консьерж Сервис, необходимо пройти регистрацию!",
		reply_markup=generate_reply_markup([START_REG_KEYBOARD])
	)


async def denied_access_message(message: Message) -> Message:
	inline_markup = generate_inline_markup(
		["Написать администратору"],
		callback_data="message_for_admin",
	)
	return await message.reply_text(
		f'‼️ *Консьерж Сервис не доступен!*',
		reply_markup=inline_markup
	)


async def submit_reg_data_message(message: Message) -> Message:
	inline_markup = generate_inline_markup(
		[SUBMIT_REG_KEYBOARD + CANCEL_KEYBOARD],
		callback_data=["approve", "cancel"],
		cols=1
	)

	return await message.reply_text(
		f'❗ В случае отмены Вам придется заново пройти регистрацию.\n'
		f'Если захотите что-то изменить, то в будущем у Вас появится такая возможность.\n',
		reply_markup=inline_markup
	)


async def success_registration_message(message: Message) -> Message:
	return await message.reply_text(
		f'*Спасибо за регистрацию!*\n'
		f'Вам предоставлен доступ в Консьерж Сервис',
		reply_markup=start_menu
	)


async def offer_questionnaire_message(message: Message) -> Message:
	questionnaire_button = generate_inline_markup(
		["Перейти к анкетированию"],
		callback_data="questionnaire"
	)
	return await message.reply_text(
		"Для составления рейтинга поставщиков рекомендуем пройти анкетирование.",
		reply_markup=questionnaire_button
	)


async def restricted_access_message(message: Message, reply_markup: ReplyKeyboardMarkup = None) -> Message:
	return await message.reply_text(
		f'_В настоящий момент доступ в Консьерж Сервис частично ограничен, '
		f'так как Вы не указали при регистрации ссылку на свои ресурсы.\n'
		f'Вы можете в разделе "Мой Профиль" добавить ссылку на сайт или соцсети '
		f'или прикрепить фото документов, подтверждающих что Вы являетесь дизайнером или архитектором_',
		reply_markup=reply_markup
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


async def select_user_group_message(
		message: Message,
		button_type: Literal["checkbox", "radiobutton"] = "checkbox",
		groups_only: list = None,
		text: str = None
) -> int:
	keyboard = REG_GROUP_KEYBOARD.copy()
	if groups_only:
		keyboard[:] = [keyboard[i] for i in range(len(keyboard)) if i in groups_only]

	inline_markup = generate_inline_markup(keyboard, callback_data=groups_only, cols=1)
	inline_markup = update_inline_markup(
		inline_keyboard=inline_markup.inline_keyboard,
		active_value="",
		button_type=button_type
	)
	message = await message.reply_text(text or "Кого Вы представляете?", reply_markup=inline_markup)
	return message.message_id


async def input_regions_message(
		context: ContextTypes.DEFAULT_TYPE,
		status: Literal["main", "additional"] = "additional",
		reply_markup: Optional[ReplyKeyboardMarkup] = None,
) -> Message:
	chat_id = context.chat_data["chat_id"]
	keyboard = [CONTINUE_KEYBOARD] if status == "additional" else [CANCEL_KEYBOARD]
	if not reply_markup:
		reply_markup = generate_reply_markup(keyboard, one_time_keyboard=False, request_location=True)

	if status == "main":
		text = "Введите свой основной рабочий регион или воспользуйтесь автоопределением."
	else:
		text = "Если есть другие регионы где вы представлены, то введите их и/или нажмите *Продолжить*"

	return await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


async def confirm_region_message(context: ContextTypes.DEFAULT_TYPE, text: str) -> Message:
	inline_markup = generate_inline_markup(
		[CONFIRM_KEYBOARD],
		callback_data=["yes", "no"],
		callback_data_prefix="choose_region_"
	)
	chat_id = context.chat_data["chat_id"]
	return await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=inline_markup)


async def incorrect_socials_warn_message(message: Message) -> None:
	await message.reply_text(
		'⚠️ Адрес должен начинаться с *https://*',
		reply_markup=continue_menu,
	)


async def offer_to_select_segment_message(message: Message, title: str = None) -> Message:
	inline_markup = generate_inline_markup(SEGMENT_KEYBOARD, callback_data_prefix="segment_", cols=1)
	inline_markup = update_inline_markup(
		inline_keyboard=inline_markup.inline_keyboard,
		active_value="",
		button_type="radiobutton",
	)
	return await message.reply_text(
		f'🎯 {title or "Выберите сегмент, в котором Вы работаете:"}',
		reply_markup=inline_markup
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
		reply_markup=continue_menu,
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


async def load_more_users_message(message: Message, group: int, cat_id: int, offset: int) -> int:
	inline_markup = generate_inline_markup(
		"➕",
		callback_data=f'group_{group}__category_{cat_id}__offset_{offset}'
	)

	reply_message = await message.reply_text(f'Показать еще', reply_markup=inline_markup)
	return reply_message.message_id


async def recommend_new_user_message(message: Message, category: dict = None) -> Message:
	inline_markup = generate_inline_markup(
		["➕ Добавить"],
		callback_data=str(category["group"] if category else ""),
		callback_data_prefix="recommended_user_",
	)

	if category is None:
		titles = []
		titles += [CAT_GROUP_DATA[group]["title"][:-1] + "а" for group in range(1,len(CAT_GROUP_DATA))]
		group_title = " и ".join(titles)

	else:
		group_data = CAT_GROUP_DATA[category["group"]]
		group_title = group_data["title"][:-1] + "а"

	text = f'🗣 Порекомендовать нового {group_title.lower()}'
	if category:
		text += f'\nв категории: {category["name"].upper()}'

	return await message.reply_text(f'_{text}_', reply_markup=inline_markup)


async def repeat_input_phone_message(message: Message) -> Message:
	inline_markup = generate_inline_markup([REPEAT_KEYBOARD], callback_data="input_phone")

	return await message.reply_text(
		f'❕Если смс код не пришел или ошиблись в наборе номера, то повторите операцию',
		reply_markup=inline_markup
	)


async def continue_reg_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "Нажмите ➡️ для завершения регистрации",
		reply_markup=continue_menu
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
	title = f'🆕 Разместить новый заказ на бирже'
	if category:
		title += f'\nв категории: {category["name"].upper()}'

	return await message.reply_text(
		f'_{text or title}_',
		reply_markup=inline_markup
	)


async def select_search_options_message(message: Message, cat_group: int) -> Message:
	keyboard = SEARCH_OPTIONS_KEYBOARD
	if cat_group != 2:
		keyboard = SEARCH_OPTIONS_KEYBOARD.copy()[:-1]

	inline_markup = generate_inline_markup(keyboard, cols=1)
	return await message.reply_text(
		"🖍 Введите поисковые слова и/или выберите опции из списка:",
		reply_markup=inline_markup
	)


async def select_events_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_markup(
		["Местные", "Российские", "Международные"],
		callback_data_prefix="events_type_",
		cols=1
	)

	return await message.reply_text(
		text or f'Какие мероприятия интересуют?',
		reply_markup=buttons,
	)


async def choose_designer_group_message(message: Message, chat_groups: list = None) -> Optional[Message]:
	if not chat_groups:
		return

	buttons = generate_inline_markup(chat_groups, callback_data_prefix="join_chat_group_")
	return await message.reply_text(
		f'Перейдите в интересующую группу:',
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

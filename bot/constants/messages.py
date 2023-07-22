from typing import List, Optional, Union

from telegram import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, \
	Document, PhotoSize
from telegram.ext import ContextTypes

from bot.constants.keyboards import (
	CONFIRM_KEYBOARD, DESIGNER_SANDBOX_KEYBOARD, SUBMIT_REG_KEYBOARD, CANCEL_REG_KEYBOARD, START_REG_KEYBOARD,
	SEGMENT_KEYBOARD, REG_GROUP_KEYBOARD, REPEAT_KEYBOARD
)
from bot.constants.menus import continue_reg_menu, cancel_reg_menu, start_menu, back_menu, done_menu
from bot.utils import generate_inline_keyboard, generate_reply_keyboard, data_list_to_string, format_output_text


async def offer_for_registration_message(message: Message, text: str = None) -> Message:
	reg_menu = generate_reply_keyboard([START_REG_KEYBOARD])
	return await message.reply_text(
		text or "ℹ️ Чтобы начать пользоваться Консьерж Сервис, необходимо пройти регистрацию!",
		reply_markup=reg_menu,
	)


async def denied_access_message(message: Message) -> None:
	# TODO: Создать логику отправки сообщений администратору
	button = generate_inline_keyboard(
		["Написать администратору"],
		callback_data="message_for_admin",
	)
	await message.reply_text(
		f'*Доступ в Консьерж для Дизайнера закрыт!*',
		reply_markup=done_menu
	)
	await message.reply_text(
		f'Можете задать вопрос администратору сервиса.',
		reply_markup=button
	)


async def submit_reg_data_message(message: Message) -> Message:
	submit_reg_menu = generate_inline_keyboard(
		[SUBMIT_REG_KEYBOARD + CANCEL_REG_KEYBOARD],
		callback_data=["approve", "cancel"],
		vertical=True
	)

	return await message.reply_text(
		f'ℹ️ В случае отмены Вам придется заново пройти регистрацию.\n'
		f'Если захотите что-то изменить, то в будущем у Вас появится такая возможность.\n',
		reply_markup=submit_reg_menu
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
		f'или направить нам фото документов, подтверждающих что Вы являетесь дизайнером или архитектором_',
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
	button = InlineKeyboardMarkup(
		[[
			InlineKeyboardButton(
				link_text,
				url=link,
				callback_data="share_link"
			)
		]]
	)
	await message.reply_text(text, reply_markup=button)


async def introduce_reg_message(message: Message) -> Message:
	await message.reply_text(
		"Для начала давайте познакомимся.",
		reply_markup=cancel_reg_menu,
	)

	return await message.reply_text(
		"Кого Вы представляете?",
		reply_markup=generate_inline_keyboard(REG_GROUP_KEYBOARD),
	)


async def show_categories_message(
		message: Message,
		category_list: List,
		text: str = None,
		message_id: Optional[int] = None
) -> Optional[Message]:

	if message_id is None:
		reply_markup = generate_inline_keyboard(
			category_list,
			item_key="name",
			callback_data="id",
			prefix_callback_name="category_",
			vertical=True
		)
		return await message.reply_text(
			text or 'Список категорий:',
			reply_markup=reply_markup,
		)
	else:
		categories = data_list_to_string(category_list, field_names="name", separator="\n☑️ ")

		await message.get_bot().edit_message_text(
			text or f'*Выбранные категории:*'
			        f'\n☑️ {categories}',
			chat_id=message.chat_id,
			message_id=message_id,
		)


async def required_category_warn_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "⚠️ Необходимо выбрать хотя бы одну категорию!",
	)


async def only_in_list_warn_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or '⚠️ Можно выбрать категорию только из списка!\n',
		reply_markup=continue_reg_menu,
	)


async def not_validated_warn_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "⚠️ Ответ должен обязательно содержать число!\n",
		reply_markup=continue_reg_menu,
	)


async def show_main_region_message(message: Message, text: str = None) -> Message:
	buttons = generate_reply_keyboard(
		[CANCEL_REG_KEYBOARD],
		one_time_keyboard=False,
		share_location=True
	)

	return await message.reply_text(
		text or "Укажите свой основной регион или поделитесь местоположением для автоопределения.",
		reply_markup=buttons,
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

	top_regions_buttons = generate_inline_keyboard(
		top_regions_list,
		item_key="name",
		callback_data="id",
		prefix_callback_name="region_"
	)

	if "last_message_id" not in chat_data:
		message = await context.bot.send_message(
			chat_id=chat_data["chat_id"],
			text=f'Можете выбрать регион из списка ниже или ввести свой:',
			reply_markup=top_regions_buttons,
		)
		chat_data["last_message_id"] = message.message_id  # Сохраним для изменения сообщения

	else:
		await context.bot.edit_message_reply_markup(
			chat_id=chat_data["chat_id"],
			message_id=chat_data["last_message_id"],
			reply_markup=top_regions_buttons
		)


async def confirm_region_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_keyboard(
		[CONFIRM_KEYBOARD],
		callback_data=["yes", "no"],
		prefix_callback_name="choose_region_"
	)
	return await message.reply_text(
		f'{text}, все верно?',
		reply_markup=buttons
	)


async def region_selected_warn_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		f'⚠️ *{text}* был уже выбран!\n',
		reply_markup=continue_reg_menu,
	)


async def not_found_region_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		f"⚠️ Регион с названием '{text or message.text}' не найден!\n"
		f"Введите корректное название региона.\n",
		reply_markup=continue_reg_menu,
	)


async def not_detected_region_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "⚠️ Не удалось определить местоположение.\n"
		        "Введите регион самостоятельно.",
		reply_markup=continue_reg_menu,
	)


async def required_region_warn_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or '⚠️ Необходимо указать хотя бы один регион!',
		reply_markup=cancel_reg_menu,
	)


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
	buttons = generate_inline_keyboard(
		SEGMENT_KEYBOARD,
		prefix_callback_name="segment_",
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


async def offer_to_save_rating_message(message: Message) -> Message:
	button = generate_inline_keyboard(
		["✅ Сохранить"],
		callback_data="save_rating",
	)

	return await message.reply_text(
		"После оценки нажмите кнопку\n"
		"*Сохранить результаты*",
		reply_markup=button,
	)


async def show_rating_title_message(message: Message, text: str = "") -> Message:
	text = "\n" + text if text else ""
	return await message.reply_text(
		f'\n{format_output_text("`Общий рейтинг`", text, default_value=" отсутствует", value_tag="_")}'
	)


async def success_save_rating_message(message: Message, user_data: dict) -> None:
	await message.edit_text(
		f'*Рейтинг для {user_data["username"]} успешно обновлен!*\n'
		f'Спасибо за оценку ♥\n️'
		f'*Ваш рейтинг:* ⭐_{user_data["author_rate"]}_\n️'
		f'*Общий рейтинг:* ⭐_{user_data["total_rate"]}️_\n'
	)


async def yourself_rate_warning_message(message: Message) -> Message:
	return await message.reply_text(
		f'*⚠️ Нельзя выставлять оценки самому себе!*',
	)


async def offer_to_cancel_action_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_keyboard(
		[CONFIRM_KEYBOARD],
		callback_data=["yes", "no"],
		# prefix_callback_name="cancel_"
	)
	return await message.reply_text(
		text or '*⚠️ Все введенные данные будут утеряны!*\n'
		        'Все равно отменить?',
		reply_markup=buttons,
	)


async def offer_to_set_segment_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_keyboard(
		SEGMENT_KEYBOARD,
		prefix_callback_name="segment_",
		vertical=True
	)

	return await message.reply_text(
		text or "🎯 Сегмент еще не установлен.\n"
		        "Если работали с ними, то подскажите",
		reply_markup=buttons
	)


async def show_after_set_segment_message(message: Message, segment: int = None) -> None:
	# segment_text = SEGMENT_KEYBOARD[segment][0]
	await message.edit_text(
		f'Спасибо за Ваш выбор! ❤️',
		reply_markup=None,
	)


async def empty_data_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or "⚠️ Недостаточно данных для завершения действия!",
		reply_markup=start_menu,
	)


async def verify_by_sms_message(message: Message) -> Message:
	await message.reply_text(
		"Введите полученный код из смс:",
		reply_markup=cancel_reg_menu,
	)
	button = generate_inline_keyboard([REPEAT_KEYBOARD], callback_data="input_phone")
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


async def share_files_message(message: Message, text: str) -> Message:
	button = generate_inline_keyboard(
		["Прикрепить файлы"],
		callback_data="share_files",
	)
	return await message.reply_text(text, reply_markup=button)


async def check_file_size_message(message: Message, file: Union[Document, PhotoSize] = None, limit: int = 5) -> Message:
	if file and file.file_size > limit * 1024 * 1024:  # 5 MB
		return await message.reply_text(
			f'⚠️ Превышен размер файла!\n'
			f'_Максимально допустимый размер - 5мб_'
		)


async def send_unknown_question_message(message: Message, text: str = None) -> Message:
	return await message.reply_text(
		text or f'Не вполне понял Вас.\n'
		        f'Выберите нужный раздел или уточните свой вопрос.',
		reply_markup=message.reply_markup or back_menu,
	)


async def show_designer_order_message(message: Message, category: str = None) -> Message:
	button = generate_inline_keyboard(
		["Разместить заказ"],
		callback_data="place_order"
	)
	return await message.reply_text(
		f'Разместите новый заказ на бирже из категории {category.upper()}',
		reply_markup=button,
	)


async def select_events_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_keyboard(
		["Местные", "Российские", "Международные"],
		prefix_callback_name="event_type_",
		vertical=True
	)
	return await message.reply_text(
		text or f'Какие мероприятия интересуют?',
		reply_markup=buttons,
	)


async def choose_sandbox_message(message: Message, text: str = None) -> Message:
	buttons = generate_inline_keyboard(
		DESIGNER_SANDBOX_KEYBOARD,
		prefix_callback_name="sandbox_type_",
		vertical=True
	)
	return await message.reply_text(
		text or f'Выберите необходимую группу ниже:',
		reply_markup=buttons,
	)


async def failed_questionnaire_message(message: Message) -> None:
	await message.reply_text(
		text='*Анкетирование было остановлено!*\n',
		reply_markup=start_menu
	)


async def empty_questionnaire_list_message(message: Message) -> None:
	await message.reply_text(
		text='*Список пустой*\n'
		     'Нечего оценивать, так как не было выбрано ни одного поставщика.\n',
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
	button = generate_inline_keyboard(
		[link_text or "Начать анкетирование"],
		callback_data="questionnaire",
	)

	return await message.reply_text(
		text or "Для составления рейтинга поставщиков, предлагаем пройти анкетирование.",
		reply_markup=button,
	)


async def success_questionnaire_message(message: Message) -> None:
	await message.reply_text(
		text='*Анкетирование успешно завершено!*\n'
		     f'Ваши результаты будут учтены в общем рейтинге поставщиков.\n'
		     f'Спасибо за уделенное время',
		reply_markup=start_menu
	)


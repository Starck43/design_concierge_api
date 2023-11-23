import re
from typing import Optional, List

from telegram import Update, Message
from telegram.ext import ContextTypes

from bot.constants.keyboards import SEARCH_OPTIONS_KEYBOARD, SEGMENT_KEYBOARD
from bot.constants.messages import (
	offer_to_select_segment_message, offer_to_select_rating_message
)
from bot.constants.patterns import FILTER_PATTERN, CLEAR_FILTER_PATTERN
from bot.constants.static import SEARCH_FIELD_LIST, MAX_RATE
from bot.handlers.common import (
	get_section, edit_or_reply_message, delete_messages_by_key, send_error_to_admin, generate_users_list,
	generate_categories_list, load_categories, regenerate_inline_keyboard
)
from bot.utils import match_query, fetch_data, data_to_string, clean_string, get_plural_word, filter_strings


async def input_search_data_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
	""" Функция ввода данных полей для поиска поставщика """

	chat_data = context.chat_data
	last_message_ids = chat_data.setdefault("last_message_ids", {})
	local_data = chat_data.setdefault("local_data", {})
	search_data = local_data.setdefault("search_data", {"fields": {}})

	section = get_section(context)
	query_message = update.message.text
	state = section["state"]
	await update.message.delete()

	# если нажата кнопка Очистить результаты поиска
	if match_query(CLEAR_FILTER_PATTERN, query_message):
		if not search_data["fields"]:
			return state

		await delete_messages_by_key(context, "last_message_ids")
		chat_data["last_message_id"] = await edit_or_reply_message(
			context,
			"❎ _Поисковый запрос удален!_",
			message=chat_data.get("last_message_id", None),
			reply_markup=section["reply_markup"]
		)

		search_data["last_option"] = None
		search_data["fields"].clear()
		search_data.pop("selected_categories", {})

	# если введен текст для поиска или нажата кнопка Показать результаты поиска
	else:
		if match_query(FILTER_PATTERN, query_message) and not search_data.get("fields"):
			text = "_Ничего не выбрано для поиска!_"
			await edit_or_reply_message(
				context,
				text=text,
				message_type="warn",
				lifetime=2
			)
			return state

		# если введены ключевые слова в строке
		elif not match_query(FILTER_PATTERN, query_message):
			min_word_length = 3
			matched_list, non_matched_list = filter_strings(query_message, length=min_word_length)
			if not matched_list:
				text = f"_Поисковые слова оказались короткими!\nДопустимая длина не менее {min_word_length} символов_"
				chat_data["last_message_id"] = await edit_or_reply_message(
					context,
					text=text,
					message_type="warn",
					message=chat_data.get("last_message_id", None),
					reply_markup=section["reply_markup"]
				)
				return state

			selected_option = 3
			search_data["last_option"] = selected_option
			field_name = SEARCH_FIELD_LIST[selected_option]

			# очистим строку запроса от спецсимволов и соберем их через запятую для передачи в поисковом запросе
			query_string = ",".join(matched_list)
			search_data["fields"].update({field_name: query_string})
			non_matched_string = ", ".join(non_matched_list)

			is_multi_words = len(matched_list) > 1  # установим, что введено сочетание слов
			if is_multi_words:
				query_message = "_ —  " + clean_string(query_string, "_\n_ —  ") + "_"
				text = f'⌨️ *Поисковые сочетания*: ☑️\n{query_message}'
			else:
				text = f'⌨️️ _{query_string}_ ☑️'

			if non_matched_string:
				text += f'\n🆎 не попали в запрос: _{non_matched_string}_\n'
				text += f'_Допускается не менее {min_word_length} символов!_'

			message_id = await edit_or_reply_message(
				context,
				text=text,
				message=last_message_ids.get(f"search_option_{selected_option}"),
				delete_before_reply=chat_data.get("last_message_id", None),
				reply_markup=section["reply_markup"]
			)
			last_message_ids[f"search_option_{selected_option}"] = message_id

		users = await load_filtered_users(update.message, context, queryset=search_data["fields"])
		if users:
			await delete_messages_by_key(context, last_message_ids.get("found_users"))
			inline_markup = generate_users_list(users)
			user_count = len(users)
			if section["cat_group"] == 2:
				plural_words = ['поставщик', 'поставщика', 'поставщиков']
			else:
				plural_words = ['исполнитель', 'исполнителя', 'исполнителей']

			plural_word = get_plural_word(user_count, *plural_words)
			title = f'🔦 *Результаты поиска*:\n(найдено: _{user_count} {plural_word}_)'
			inline_message = await update.message.reply_text(title, reply_markup=inline_markup)
			last_message_ids["found_users"] = inline_message.message_id

		else:
			title = "_❕Ничего не найдено по запросу!_"
			chat_data["last_message_id"] = await edit_or_reply_message(
				context,
				text=title,
				message=chat_data.get("last_message_id", None),
				reply_markup=section["reply_markup"]
			)

	return state


async def select_search_option_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
	""" Колбэк выобра опций для поиска поставщика """

	query = update.callback_query
	await query.answer()

	selected_option = int(query.data.lstrip("search_option_"))
	if selected_option >= len(SEARCH_FIELD_LIST):
		return

	chat_data = context.chat_data
	last_message_ids = chat_data.setdefault("last_message_ids", {})

	local_data = chat_data.setdefault("local_data", {})
	selected_callback_data = local_data.setdefault("selected_callback_data", {})  # выбранные колбэки списка кнопок
	search_data = local_data.setdefault("search_data", {"fields": {}})
	search_option_message = last_message_ids.get(f"search_option_{selected_option}")
	section = get_section(context)

	await delete_messages_by_key(context, search_option_message)
	await delete_messages_by_key(context, last_message_ids.get("found_users"))

	caption = SEARCH_OPTIONS_KEYBOARD[selected_option]
	title = f'*Выберите {caption[2:].lower()}*'
	if selected_option == 0:  # категории
		inline_markup = await generate_categories_list(
			query.message,
			context,
			groups=section["cat_group"],
			checked_callback_data=list(selected_callback_data.values()),
			button_type="checkbox"
		)
		message = await query.message.reply_text(text=f'{caption[0]} {title}:', reply_markup=inline_markup)

	elif selected_option == 1:  # рейтинг
		title = f'{title} от 1 до {MAX_RATE}'
		current_rating = search_data["fields"].get("rating")
		message = await offer_to_select_rating_message(query.message, title=title, active_value=current_rating)

	elif selected_option == 2:  # сегмент
		message = await offer_to_select_segment_message(query.message, title=title)

	else:
		return

	last_message_ids[f"search_option_{selected_option}"] = message.message_id
	search_data["last_option"] = selected_option


async def select_search_categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк выбора категорий для фильтра поставщиков """

	query = update.callback_query
	await query.answer()

	query_data = query.data.split("__")
	cat_id = int(query_data[-1].lstrip("category_"))
	group = int(query_data[0].lstrip("group_")) if len(query_data) > 1 else None

	last_message_ids = context.chat_data.setdefault("last_message_ids", {})
	local_data = context.chat_data.setdefault("local_data", {})
	selected_callback_data = local_data.setdefault("selected_callback_data", {})  # выбранные колбэки списка кнопок
	search_data = local_data.setdefault("search_data", {})
	selected_option = 0
	search_data.setdefault("last_option", selected_option)
	field_name = SEARCH_FIELD_LIST[selected_option]
	selected_categories = search_data.setdefault("selected_categories", {})
	section = get_section(context)

	current_cat = await load_categories(query.message, context, cat_id=cat_id)
	if not current_cat:
		return

	# await regenerate_inline_keyboard(query.message, active_value=query.data, button_type="checkbox")
	if selected_callback_data.get(cat_id):
		# удалим отмеченную категорию
		del selected_callback_data[cat_id]
		del selected_categories[cat_id]
	else:
		# Добавим отмеченную категорию
		selected_callback_data[cat_id] = query.data
		selected_categories[cat_id] = current_cat

	cat_ids = list(selected_categories.keys())
	message_id = last_message_ids.get(f"search_option_{selected_option}")
	if cat_ids:
		selected_cat_names = data_to_string(selected_categories, field_names=["name"], prefix=" —  ", tag="_")
		title = f'*{SEARCH_OPTIONS_KEYBOARD[selected_option]}*: ☑️\n{selected_cat_names}'
		last_message_id = context.chat_data.get("last_message_id", None)
		message_id = await edit_or_reply_message(
			context,
			message=message_id,
			text=title,
			delete_before_reply=last_message_id,
			reply_markup=section["reply_markup"] if last_message_id else None
		)
		last_message_ids[f"search_option_{selected_option}"] = message_id

	elif message_id:
		await context.bot.delete_message(chat_id=query.message.chat_id, message_id=message_id)

	search_data["fields"].update({field_name: cat_ids})


async def select_search_rating_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк выбора рейтинга поставщика """

	query = update.callback_query
	await query.answer()

	rate = int(query.data.lstrip("rating_"))
	last_message_ids = context.chat_data.setdefault("last_message_ids", {})
	local_data = context.chat_data.setdefault("local_data", {})
	search_data = local_data.setdefault("search_data", {})
	selected_option = 1
	search_data.setdefault("last_option", selected_option)
	field_name = SEARCH_FIELD_LIST[selected_option]
	section = get_section(context)

	if search_data["fields"].get(field_name, 0) == rate:
		return

	await regenerate_inline_keyboard(query.message, active_value=str(rate), button_type='rate')

	title = f'⭐️ _{rate}{" и выше" if rate < 8 else ""}_ ☑️'
	last_message_id = context.chat_data.get("last_message_id", None)
	message_id = await edit_or_reply_message(
		context,
		message=last_message_ids.get(f"search_option_{selected_option}"),
		text=title,
		delete_before_reply=last_message_id,
		reply_markup=section["reply_markup"] if last_message_id else None
	)
	last_message_ids[f"search_option_{selected_option}"] = message_id
	search_data["fields"].update({field_name: rate})


async def select_search_segment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	""" Колбэк выбора сегмента поиска поставщика """

	query = update.callback_query
	await query.answer()

	segment_index = int(query.data.lstrip("segment_"))
	last_message_ids = context.chat_data.setdefault("last_message_ids", {})
	local_data = context.chat_data.setdefault("local_data", {})
	search_data = local_data.setdefault("search_data", {})
	selected_option = 2
	search_data.setdefault("last_option", selected_option)
	field_name = SEARCH_FIELD_LIST[selected_option]
	section = get_section(context)

	title = f'🎯 _{SEGMENT_KEYBOARD[segment_index]}_ ☑️'
	last_message_id = context.chat_data.get("last_message_id", None)
	message_id = await edit_or_reply_message(
		context,
		message=last_message_ids.get(f"search_option_{selected_option}"),
		text=title,
		delete_before_reply=last_message_id,
		reply_markup=section["reply_markup"] if last_message_id else None
	)
	last_message_ids[f"search_option_{selected_option}"] = message_id
	search_data["fields"].update({field_name: segment_index})


async def load_filtered_users(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		queryset: dict
) -> Optional[List[dict]]:
	"""  Функция API: Поиск пользователей на сервере """

	if not queryset:
		return None

	res = await fetch_data("search/", params=queryset)
	if res["error"]:
		text = f'Ошибка поиска поставщиков!'
		await send_error_to_admin(message, context, error=res, text=text)
		return None

	return res["data"]

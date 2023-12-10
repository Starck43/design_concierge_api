import difflib
import json
import re
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Optional, Dict, Union, List, Any, Tuple, Literal
from urllib.parse import urlencode

import aiohttp
import unicodedata
from django.core.cache import cache
from slugify import slugify
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ChatMember
from telegram.ext import CommandHandler, filters, CallbackContext

from bot.bot_settings import SERVER_URL
from bot.constants.api import OPENSTREETMAP_GEOCODE_URL
from bot.constants.static import RATE_BUTTONS
from bot.logger import log


def command_handler(app, command, handler_filters=filters.COMMAND):
	def decorator(func):
		if app:
			handler = CommandHandler(command, func, filters=handler_filters)
			app.add_handler(handler)
		return func

	return decorator


def send_action(action):
	"""
	Запускает "action" во время обработки команды.

	Example usage:
		@send_action(ChatAction.TYPING) \n
		def my_handler(update, context):
			pass
	"""

	def decorator(func):
		@wraps(func)
		async def wrapped(update, context, *args, **kwargs):
			chat_id = update.effective_message.chat_id
			await context.bot.send_chat_action(chat_id=chat_id, action=action)
			return await func(update, context, *args, **kwargs)

		return wrapped

	return decorator


def allowed_roles(roles: Union[ChatMember, List[str]] = None, channel_id=None):
	def decorator(func):
		@wraps(func)
		async def wrapped(update: Update, context: CallbackContext):
			user = update.effective_user
			chat_id = channel_id or update.effective_chat.id
			if not roles:
				return await func(update, context)
			if isinstance(roles, ChatMember):
				member = await context.bot.get_chat_member(chat_id, user.id)
				if member.status in roles:
					return await func(update, context)
			elif isinstance(roles, list) and user.id in roles:
				return await func(update, context)
			await update.message.reply_text("У вас нет прав для выполнения этой команды.")

		return wrapped

	return decorator


# def get_conv_state(state: Type[Enum], value: any) -> Optional[Enum]:
# 	for item_name, item_value in state.__members__.items():
# 		if item_value.value == value:
# 			return item_value
# 	return None


def build_keyboard(
		buttons: list,
		cols: int,
		header: Optional[List[KeyboardButton]] = None,
		footer: Optional[List[KeyboardButton]] = None,
		as_markup: bool = False,
		**kwargs
) -> Union[ReplyKeyboardMarkup, List[List[KeyboardButton]]]:
	"""
	Creates a keyboard with buttons for Telegram.

	:param buttons: a list of text buttons
	:param cols: the number of columns in the keyboard
	:param header: a list of Keyboard buttons for the header
	:param footer: a list of Keyboard buttons for the footer
	:param as_markup: if keyboard need to be returned as ReplyKeyboardMarkup
	:param kwargs: additional parameters for the buttons
	:return: a list of lists of KeyboardButton
	"""

	buttons = [
		[KeyboardButton(text=btn, **kwargs) for btn in buttons[i:i + cols]] for i in range(0, len(buttons), cols)
	] if buttons else []

	if header:
		buttons.insert(0, [btn for btn in header])

	if footer:
		buttons.append([btn for btn in footer])

	return ReplyKeyboardMarkup(buttons, resize_keyboard=True) if as_markup else buttons


def generate_reply_markup(
		data: Union[List[str], List[List[str]], List[Dict[str, Any]], None],
		columns: int = 2,
		resize_keyboard: bool = True,
		one_time_keyboard: bool = True,
		is_persistent: bool = True,
		**kwargs
) -> Optional[ReplyKeyboardMarkup]:
	"""
	Generates a reply keyboard markup for Telegram bot API.

	Args:
		data: The data to be displayed on the keyboard. Can be a list of strings,
		a list of lists of strings, or a list of dictionaries.
		columns: the number of columns in the keyboard
		resize_keyboard: Whether the keyboard should be resized to fit the number of buttons.
		one_time_keyboard: Whether the keyboard should be hidden after use.
		is_persistent: Whether the keyboard should be always shown when the regular keyboard is hidden.
		**kwargs: Additional keyword arguments to be passed to the KeyboardButton constructor.

	Returns:
		An instance of ReplyKeyboardMarkup containing the generated keyboard buttons.
		Returns None if the data is empty or invalid.
	"""

	if not data:
		return None
	buttons = []
	request_location = kwargs.pop("request_location", None)
	if request_location:
		buttons.append([KeyboardButton("📍 Определить регион", request_location=True, **kwargs)])

	request_contact = kwargs.pop("request_contact", None)
	if request_contact:
		buttons.append([KeyboardButton("👤 Поделиться контактом", request_contact=True, **kwargs)])

	for row in data:
		text = None
		if isinstance(row, list):
			buttons.extend(build_keyboard(row, cols=columns, **kwargs))
		elif isinstance(row, dict):
			text = row.get("text")
		else:
			text = row

		if text:
			row = [KeyboardButton(text, **kwargs)]
			buttons.append(row)

	return ReplyKeyboardMarkup(
		buttons, resize_keyboard=resize_keyboard, one_time_keyboard=one_time_keyboard, is_persistent=is_persistent
	)


# TODO: Обработать исключение для callback_data = [], когда его длина не совпадает с общим количеством строк в data
def generate_inline_markup(
		data: Union[List[str], List[List[str]], List[Dict[str, Any]], str],
		item_key: Optional[str] = None,
		item_prefix: Optional[Union[str, List[str]]] = "",
		callback_data: Optional[Union[str, List[str], List[List[str]]]] = None,
		callback_data_prefix: Optional[str] = "",
		second_button_label: Optional[str] = "",
		vertical: bool = False,
		**kwargs,
) -> Optional[InlineKeyboardMarkup]:
	"""
	Generates an inline keyboard markup for Telegram bot API.

	Args:
		data: The data to be displayed on the keyboard. Can be a list of strings,
		a list of lists of strings, or a list of dictionaries.
		callback_data: The callback data to be sent when a button is pressed. Can be a string,
		a list of strings, or a list of lists of strings.
		item_key: The key in the dictionary to be used as the button label.
		item_prefix: A string or list of strings to be added as a prefix to the button label.
		callback_data_prefix: The string to be added as a prefix to the callback data string.
		second_button_label: The text to be displayed in the second column.
		vertical: Whether the buttons should be displayed vertically or horizontally.
		**kwargs: Additional keyword arguments to be passed to the InlineKeyboardButton constructor.

	Returns:
		An instance of InlineKeyboardMarkup containing the generated keyboard buttons.
		Returns None if the data is empty or invalid.
	"""

	if not data:
		return None

	if isinstance(data, str):
		data = [data]

	if isinstance(callback_data, str) and callback_data:
		callback_data = [callback_data]
		flatten_data = flatten_list(data)
		if len(flatten_data) != len(callback_data):
			callback_data = callback_data * len(flatten_data if isinstance(data[0], list) else data)
	elif isinstance(callback_data, list) and callback_data:
		callback_data = flatten_list(callback_data)
	else:
		callback_data = [str(i) for i in range(len(flatten_list(data)))]

	buttons = []

	for i, row in enumerate(data):
		callback_data_str = callback_data_prefix

		if isinstance(row, str):
			text = item_prefix + row
			callback_data_str += str(callback_data.pop(0)) if callback_data else slugify(row, separator="_")
			row = [InlineKeyboardButton(text, callback_data=callback_data_str, **kwargs)]

		elif isinstance(row, dict):
			key = row.get(callback_data[i], slugify(row.get(item_key, callback_data[i]), separator="_"))
			text = row.get(item_key, key)

			if item_prefix:
				if isinstance(item_prefix, list):
					prefix = "".join([str(row.get(post_key, post_key)) for post_key in item_prefix])
				else:
					prefix = str(row.get(item_prefix, item_prefix if item_prefix else ""))

				if "None" not in prefix:
					text = f"{text} {prefix}"

			callback_data_str += str(key)
			row = [InlineKeyboardButton(text, callback_data=callback_data_str, **kwargs)]

		elif isinstance(row, list):
			prefix = "".join(item_prefix) if isinstance(item_prefix, list) else item_prefix
			left_part, right_part = "", ""
			if prefix:
				if prefix[-1] == " ":
					left_part = prefix
				else:
					right_part = prefix

			_row = []
			for item in row:
				callback_data_str = callback_data_prefix
				callback_data_str += str(callback_data.pop(0)) if callback_data else slugify(item, separator="_")
				text = left_part + item + right_part
				_row.append(InlineKeyboardButton(text, callback_data=callback_data_str, **kwargs))
			row = _row

		else:
			row = None

		if row and second_button_label:
			row.append(
				InlineKeyboardButton(
					text=second_button_label,
					callback_data=f"extra__{callback_data_str}",
					**kwargs,
				)
			)
		buttons.append(row)

	if vertical:
		buttons = [[btn] for row in buttons for btn in row]
	else:
		buttons = [row for row in buttons]

	return InlineKeyboardMarkup(buttons)


def update_inline_markup(
		inline_keyboard: Union[List[List[InlineKeyboardButton]], Tuple[Tuple[InlineKeyboardButton]]],
		active_value: Union[str, list] = None,
		button_type: Literal["checkbox", "radiobutton", "rate"] = "radiobutton",
) -> InlineKeyboardMarkup:
	"""
	Update an inline keyboard, checking an active button in button list.
	Button types: radiobutton, checkbox, rate
	"""

	new_inline_keyboard = []
	if isinstance(active_value, int):
		active_value = [active_value]
	elif active_value is None:
		active_value = []

	for row in inline_keyboard:
		new_row = []
		rate_value = len(row)
		for button in row:
			if button_type == 'rate':
				rate = int(active_value[0] if active_value else "0")
				level = rate / rate_value
				try:
					symbol = RATE_BUTTONS[3]
					if int(button.callback_data[-1]) <= rate:
						if level > RATE_BUTTONS[0][1]:
							symbol = RATE_BUTTONS[0][0]
						elif level > RATE_BUTTONS[1][1]:
							symbol = RATE_BUTTONS[1][0]
						else:
							symbol = RATE_BUTTONS[2]

				except ValueError:
					symbol = button.text

				new_button = InlineKeyboardButton(symbol, callback_data=button.callback_data)

			elif button.callback_data in active_value:
				if button_type == 'checkbox':
					new_symbol = "✓  "
					old_symbol = "▢  "
					if button.text.startswith(new_symbol):
						text = old_symbol + button.text[3:]
					elif button.text.startswith(old_symbol):
						text = new_symbol + button.text[3:]
					else:
						text = f'{new_symbol}{button.text}'
					new_button = InlineKeyboardButton(text, callback_data=button.callback_data)
				else:
					new_symbol = "◉ "
					old_symbol = "◌ "
					text = f'{new_symbol}{button.text.lstrip(old_symbol)}'
					new_button = InlineKeyboardButton(text, callback_data=button.callback_data)

			else:
				if button_type == 'checkbox':
					selected_symbol = "✓  "
					symbol = "▢  "
					text = button.text
					if not button.text.startswith(symbol) and not button.text.startswith(selected_symbol):
						text = f'{symbol}{button.text}'
					new_button = InlineKeyboardButton(text, callback_data=button.callback_data)
				else:
					new_symbol = "◌ "
					old_symbol = "◉ "
					text = f'{new_symbol}{button.text.lstrip(new_symbol).lstrip(old_symbol)}'
					new_button = InlineKeyboardButton(text, callback_data=button.callback_data)
			new_row.append(new_button)
		new_inline_keyboard.append(new_row)

	return InlineKeyboardMarkup(new_inline_keyboard)


def remove_button_from_keyboard(keyboard: InlineKeyboardMarkup, callback_data: str) -> Optional[InlineKeyboardMarkup]:
	"""
	Removes an inline markup button by its callback_data.

	:param keyboard: The keyboard from which the button needs to be removed.
	:param callback_data: The callback_data of the button that needs to be removed.
	:return: The updated keyboard without the removed button.
	"""

	if not keyboard:
		return None

	updated_inline_markup = []
	for row in keyboard.inline_keyboard:
		updated_row = []
		for button in row:
			if button.callback_data != callback_data:
				updated_row.append(button)
		updated_inline_markup.append(updated_row)
	return InlineKeyboardMarkup(updated_inline_markup)


def add_button_to_keyboard(inline_markup: InlineKeyboardMarkup, text: str, callback_data: str) -> InlineKeyboardMarkup:
	"""
	Adds a button to the keyboard with the specified text and callback_data.

	:param inline_markup: The keyboard to which the button needs to be added.
	:param text: The text of the button.
	:param callback_data: The callback_data of the button.
	:return: The updated keyboard with the added button.
	"""
	updated_inline_markup = []
	if inline_markup:
		[updated_inline_markup.append(row) for row in inline_markup.inline_keyboard]
	new_button = InlineKeyboardButton(text=text, callback_data=callback_data)
	updated_inline_markup.append([new_button])
	return InlineKeyboardMarkup(updated_inline_markup)


def sub_years(years: int = 0) -> int:
	"""
	Returns the date that is obtained by subtracting the given number of years
	from the current date.
	:param years: The number of years to subtract.
	:return: The resulting date in "YYYY" format or empty string.
	"""

	today = datetime.today()
	result = today - timedelta(days=years * 365)
	return int(result.strftime("%Y"))


def calculate_years_of_work(start_year: int, absolute_value: bool = False) -> Optional[str]:
	"""
	Calculate the number of years of work based on the start year.

	:param start_year: The year the work started.
	:param absolute_value: The flag to determine if the start year is the years of the work
	:return: A string indicating the number of years of work.
	"""

	if not start_year:
		return None

	years_of_work = int(start_year)
	if not absolute_value:
		current_year = datetime.now().year
		years_of_work = current_year - years_of_work

	if years_of_work == 0:
		return "меньше года"
	elif years_of_work == 1:
		return "1 год"
	elif 2 <= years_of_work <= 4:
		return f"{years_of_work} года"
	else:
		return f"{years_of_work} лет"


def replace_double_slashes(url: str):
	return re.sub(r'(?<!:)//+', '/', url)


def clean_string(text: str, delimiter: str = " ") -> str:
	"""
	Cleans a string by replacing spaces, underscores, hyphens, and special characters with a given delimiter.
	:param text: The input string to be cleaned.
	:param delimiter: The delimiter to be used for replacing special characters and spaces. Default is a space.
	:return: The cleaned string with the specified delimiter.
	"""
	pattern = r"[\s\W_-]+"
	return re.sub(pattern, delimiter, text)


def filter_strings(strings: Union[list, str], length: int) -> Tuple[list, list]:
	"""
	Filters a list of strings based on a given length and returns a tuple containing the new list and
	the list of removed elements.
	If a string is passed instead of a list, it is first converted to a list of strings using the regex pattern.
	Args:
		strings (List[str]): The list of strings to be filtered.
		length (int): The length to filter the strings by.
	Returns:
		Tuple[list, list]: A tuple containing the new list of filtered strings and the list of removed elements.
	"""
	removed_elements = []
	filtered_elements = []

	if strings:
		if isinstance(strings, str):
			strings = re.split(r'[\s\W_-]+', strings)

		for s in strings:
			if len(s) < length:
				removed_elements.append(s)
			else:
				filtered_elements.append(s)

	return filtered_elements, removed_elements


def get_formatted_date(date: str, format_pattern: str = "%d.%m.%Y") -> tuple:
	current_date = datetime.now()

	if not date:
		return "бессрочно", None, current_date

	date_object = datetime.fromisoformat(date)
	date_string = date_object.strftime(format_pattern) if current_date <= date_object else ""
	return date_string, date_object, current_date


def validate_date(date_text: str, format_pattern: str = "%d.%m.%Y") -> Optional[tuple]:
	try:
		# Замена символов "/" и "-" на точку
		date_text = re.sub(r'[\s/-]+', '.', date_text.strip())

		# Проверка формата даты и преобразование в объект datetime
		date_obj = datetime.strptime(date_text, format_pattern)

		formatted_date = date_obj.strftime("%Y-%m-%d")  # Формат даты для сохранения в таблице
		return date_text, formatted_date

	except ValueError:
		return None


def validate_number(text: str) -> Optional[int]:
	pattern = r'^\D*?(\d+)\D*?$'  # Регулярное выражение для отсечения нечисловых символов
	match = re.match(pattern, text)
	if match:
		return int(match.group(1))
	else:
		return None


def is_emoji(character: str) -> bool:
	return unicodedata.category(character) == "So"


def extract_numbers(string: str) -> List[any]:
	"""
	Extracts all numbers from a given string.

	:param string: The input string.
	:return: A list of numbers extracted from the string.
	"""

	res_list = re.findall(r'\d+', string)
	if not res_list:
		res_list = [""]
	return res_list


def convert_obj_to_tuple_list(obj_list: dict, *keys) -> List[Optional[Tuple]]:
	tuple_list = []
	for obj in obj_list:
		tuple_list.append(tuple(obj.get(key) for key in keys))
	return tuple_list


def extract_fields(data: List[dict], field_names: Union[str, List[str]]) -> List[any]:
	"""
		Extracts values from a list of dictionaries corresponding to the given field names.

		:param data: A list of dictionaries to extract values from.
		:param field_names: A string or list of strings representing the field names to extract values for.
		:return: A list of values corresponding to the given field names.
			If a single field name is given, a list of values is returned.
			If multiple ones are given, a list of lists is returned, where each inner list corresponds to
			the values for a single dictionary.
	"""

	if not data:
		return []

	if isinstance(field_names, str):
		field_names = [field_names]

	if len(field_names) == 1:
		field_name = field_names[0]
		return [val.get(field_name, field_name) for val in data if field_name not in val or val[field_name] is not None]

	result = []
	for val in data:
		fields = []
		for field_name in field_names:
			if field_name not in val or val[field_name] is not None:
				fields.append(val.get(field_name, field_name))

		if None not in fields:
			result.append(fields)
	return result


def data_to_string(
		data: Union[List[dict], Dict[str, dict]],
		field_names: Union[str, List[str]],
		separator: str = "\n",
		prefix: str = "",
		tag: str = ""
) -> str:
	"""
	Converts a list or dictionary of dictionaries into a string with specific fields formatted as desired.
	:param prefix: any symbols before every string: 
	:param data: A list or dictionary of dictionaries to extract values from.
	:param field_names: A string or list of strings representing the field names to extract values for.
	:param separator: A string used to separate the values in the resulting string. Default is a newline character.
	:return: A string representing the values extracted from the dictionaries.
	"""
	if isinstance(data, dict):
		data = list(data.values())

	if not data:
		return ""

	result_list = extract_fields(data, field_names)

	if not result_list:
		return ""

	if isinstance(result_list[0], str):
		return prefix + tag + f'{separator}{prefix}'.join(result_list) + tag

	result = ""
	for fields in result_list:
		line = prefix + tag + str(fields.pop(0))
		if len(fields) > 0:
			line += f": {' '.join(map(str, fields))}"
		result += line + tag + separator

	return result.rstrip(separator)


def format_output_text(
		caption: str = "",
		data: Union[int, str, dict, list, None] = None,
		default_value: str = "",
		default_sep: str = ":",
		tag: str = ""
) -> str:
	if (data is None or isinstance(data, str) and data.strip() == "") and not default_value:
		return ""

	result = f'{caption}{default_sep} ' if caption else ""
	value = data.values() if isinstance(data, dict) else data.copy() if isinstance(data, list) else data

	if value is None:
		value = ""

	elif isinstance(value, list):
		value = f'\n- {tag}' + f'{tag}\n- {tag}'.join(value) + tag

	else:
		value = f'{tag}{data}{tag}'

	result += value if data is not None else default_value
	return "\n" + result.lstrip()


def format_output_link(src: str, caption: str = '', icon: str = '', link_type: str = "url") -> str:
	"""
	Formats a link with an optional icon and caption.

	Args:
	    src: The URL or phone number or email address to link to.
	    caption: An optional caption to display with the link.
	    icon: An optional icon to display next to the link.
	    link_type: The type of link to create, either "url" or "tel" or "email".

	Returns:
	    A string containing the formatted link.
	"""

	if not src:
		return ""

	if link_type.lower() == "tel":
		url = f'tel:{src}'
	elif link_type.lower() == "email":
		url = f'mailto:{src}'
	else:
		url = src if src.startswith('http://') or src.startswith('https://') else f"http://{src}"

	return f'{icon} [{caption or src}]({url})\n'


def find_obj_in_dict(list_dict: List[dict], params: Dict[str, Any], condition: str = "AND") -> dict:
	"""
	Finds an object within a list of dictionaries based on specified keys and values, using the specified condition.
	Args:
		list_dict: A list of dictionaries to search within.
		params: A dictionary containing keys and values to search for.
		condition: The condition to use for matching. Possible values are "AND" (default) or "OR".

	Returns:
		The first dictionary that matches the specified keys and values using the specified condition.
	"""

	for elem in list_dict:
		if isinstance(elem, dict):  # Check if elem is a dictionary
			if condition == "AND":
				if all(elem.get(key) == value for key, value in params.items() if value is not None):
					return elem
			elif condition == "OR":
				if any(elem.get(key) == value for key, value in params.items() if value is not None):
					return elem
	return {}


# TODO: объединить с find_obj_in_dict
def find_obj_in_list(list_dict: List[dict], search_params: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
	if not search_params:
		return {}, -1

	for i, obj in enumerate(list_dict):
		if all(obj.get(key) == value for key, value in search_params.items()):
			return obj, i

	return {}, -1


def remove_item_from_list(src: List[Dict[str, Any]], params: Dict[str, Any]) -> bool:
	obj, i = find_obj_in_list(src, params)
	if obj:
		src.pop(i)
		return True

	return False


def remove_duplicates(data: List[dict], field: str) -> None:
	"""
	Removes dictionary duplicates in a list based on the specified field.

	Args:
		data: A list of dictionaries to remove duplicates from.
		field: The field to use for removing duplicates.

	Returns:
		None (the function mutates the input list).
	"""

	unique_values = set()  # Set of unique field values

	for item in data:
		value = item.get(field)

		if value not in unique_values:
			unique_values.add(value)
		else:
			data.remove(item)


def get_key_values(arr: list, key: str) -> List[str]:
	return [obj.get(str(key)) for obj in arr]


def list_to_dict(objects: list, key_name: str, *fields) -> dict:
	"""
	This function takes a list of objects and a key name as input, and returns a dictionary
	where the keys are the values of the key name property of the objects,
	and the values are the objects themselves.

	Args:
		objects (list): A list of objects.
		key_name (str): The name of the key property to use as the dictionary keys.
		*fields (str): The names of the properties to include in the dictionary values.

	Returns:
		dict: A dictionary where the keys are the values of the key name property of the objects,
		and the values are dictionaries containing the specified properties of the objects.
	"""
	result = {}
	for obj in objects:
		if obj[key_name]:
			item = {field: obj[field] for field in fields}
			result[obj[key_name]] = item
	return result


def update_text_by_keyword(text: str, keyword: str, replacement: str) -> str:
	""" Substitute some string in the given text with the replacement by the keyword """
	is_replaced = False
	lines = text.split("\n")
	for i in range(len(lines)):
		if keyword in lines[i]:
			lines[i] = replacement
			is_replaced = True

	if is_replaced:
		new_text = "\n".join(lines)
		return new_text

	return text


def dict_to_formatted_text(data: dict, indent: int = 2) -> str:
	"""
	Converts a dictionary to json formatted text.
	:param data: The dictionary to be converted.
	:param indent: The number of spaces for indentation (default is 2).
	:return: The formatted text representation of the dictionary.
	"""

	def parse_value(val):
		"""
		Parses the value based on its type.
		:param val: The value to be parsed.
		:return: The parsed value.
		"""
		if isinstance(val, dict):
			return json.dumps(val, ensure_ascii=False, indent=indent)

		elif isinstance(val, list) and val and isinstance(val[0], dict):
			parsed_list = []
			for item in val:
				parsed_list.append(json.dumps(item, skipkeys=True, ensure_ascii=False, indent=indent))

			return "[\n" + ",\n".join(parsed_list) + "\n]"

		elif isinstance(val, Enum):
			return f'{val.value} ({val.__class__.__name__}.{val.name})'

		else:
			return str(val)

	formatted_text = []
	for key, value in data.items():
		formatted_value = parse_value(value)
		formatted_text.append(f'{key}: {formatted_value}')

	return '\n'.join(formatted_text)


def determine_greeting(hour: int) -> str:
	if 5 < hour < 12:
		greeting = 'Доброе утро'
	elif 12 < hour < 17:
		greeting = 'Добрый день'
	else:
		greeting = 'Добрый вечер'
	return greeting


def is_phone_number(value: str) -> bool:
	pattern = r'^(\+?\d{1,3})?[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}$'
	return bool(re.match(pattern, value))


def format_phone_number(number: str) -> Optional[str]:
	# TODO: В будущем использовать готовую библиотеку для форматирования любого номера телефона
	phone_number = re.sub(r'[^\d]', '', number)  # Удаление всех символов, кроме "+" и цифр
	phone_number = re.sub(r'^(8|007)', '7', phone_number, count=1)  # Replace the first "8" with "+7"
	return phone_number if len(phone_number) == 11 else None


def remove_special_chars(s: str, code_alias: str = "866") -> str:
	"""
	Removes special characters from a string.
	:param s: The string from which to remove special characters.
	:param code_alias: The code alias for encoding. Defaults to "866".
	:return: The string without special characters.
	"""
	if not s:
		return ""

	return str(s).encode(code_alias, 'ignore').decode(code_alias).strip()


def get_plural_word(number: int, nominative_singular: str, genetive_singular: str, nominative_plural: str) -> str:
	"""
	Returns the plural form of a word for a given number.
	:param number: The number for which to determine the plural form of the word.
	:param nominative_singular: The nominative singular form of the word.
	:param genetive_singular: The genetive singular form of the word.
	:param nominative_plural: The nominative plural form of the word.
	:return: The plural form of the word for the given number.
	"""
	last_digit = 0
	word = ((number in range(5, 20)) and nominative_plural or
	        (1 in (number, (last_digit := number % 10))) and nominative_singular or
	        ({number, last_digit} & {2, 3, 4}) and genetive_singular or nominative_plural
	        )
	return word


def match_query(substring: any, text: str) -> bool:
	"""
	Checks if the text contains the given substring.
	:param substring: The substring to find in the text.
	:param text: The text in which to find the substring.
	:return: True if the text contains the substring, False otherwise.
	"""
	pattern = remove_special_chars(substring) if isinstance(substring, str) else str(substring)
	if not substring or not text:
		return False

	return bool(re.search(pattern, text, re.I))


def flatten_list(
		lst: List[Union[str, List[str]]],
		exclude: Optional[Union[str, List[str]]] = None,
		delimiter: str = ""
) -> Union[List[str], str]:
	"""
	Given a list or lists of strings, returns a flattened string with the specified delimiter.
	Args:
		lst: A list of strings and lists of strings to flatten.
		exclude: A string or list of strings to exclude from the flattened string. Defaults to None.
		delimiter: The delimiter to use between flattened strings. If it's empty then result as list. Defaults to ''.
	Returns:
		Union[List[str], str]: The flattened string without special characters.
	"""
	if not lst:
		return ""

	if not exclude:
		exclude = []

	if isinstance(exclude, str):
		exclude = [exclude]

	flattened = []
	stack = lst[::-1]

	while stack:
		item = stack.pop()

		if isinstance(item, list):
			stack.extend(item[::-1])
		elif item not in exclude:
			flattened.append(remove_special_chars(item))

	if delimiter:
		return delimiter.join(flattened)

	return flattened


def filter_list(
		list_: List[Union[dict, Any]],
		filter_key: str = None,
		filter_value: Any = None,
		sort_key: str = None,
		reverse: bool = False
) -> List[Union[dict, Any]]:
	"""
	Filter a list of dictionaries by a specified key and value, and then sort the resulting list based on a specified key and direction.
	Sort a list of any other type of object while preserving unique values.

	Args:
		list_: The list to filter and sort.
		filter_key: The key to filter by for dictionaries.
		filter_value: The value or values to filter by for dictionaries.
		sort_key: The key to sort by for dictionaries and other types of objects.
		reverse: Whether to sort in reverse order.

	Returns:
		A new filtered and sorted list.
	"""

	if isinstance(list_[0], dict) and filter_key is not None:
		if not isinstance(filter_value, list):
			filter_value = [filter_value]
		filtered_list = list(filter(lambda x: x.get(filter_key) in filter_value, list_))
		if sort_key is not None:
			filtered_list.sort(key=lambda x: x[sort_key], reverse=reverse)
		return filtered_list
	else:
		sorted_list = sorted(set(list_), key=lambda x: x if isinstance(x, str) else str(x), reverse=reverse)
		return sorted_list


def fuzzy_compare(
		src: Union[str, dict],
		data: Union[str, List[str], List[Dict[str, Union[str, int]]]],
		item_key: Optional[str] = None,
		cutoff: float = 0.5
) -> Tuple[Union[dict, str], float, Optional[int]]:
	"""
	Find the closest match to a source string in a list of strings or dictionaries using the difflib library.

	Args:
		src: The source string or dictionary to compare against.
		data: The data to compare to (either a string, a list of strings, or a list of dictionaries).
		item_key: The key to use when comparing a list of dictionaries (optional).
		cutoff: The minimum similarity ratio required for a match (default 0.5).

	Returns:
		A tuple containing the closest match object, the similarity ratio, and the index of the match (if applicable).

	Example usage:
		data = ['banana', 'apple', 'cherry'] \n
		fuzzy_compare('aple', data)  # return: ('apple', 0.8, 1)
	"""

	def get_best_match(element):
		# Find the closest match for the current element using recursive approach
		return fuzzy_compare(element, data, item_key, cutoff)

	if not src:
		return "", 0, None

	if isinstance(src, dict):
		# If the source is a dictionary, convert its values to a list of strings
		src = [str(v) for v in src.values()]

	if isinstance(src, list):
		# If the source is a list, find the closest match for each element and select the one with the highest match ratio
		best_match = ('', 0, None)
		for el in src:
			match, match_ratio, match_index = get_best_match(el)
			if match_ratio > best_match[1]:
				best_match = match, match_ratio, match_index
		return best_match

	if isinstance(data, str):
		matcher = difflib.SequenceMatcher(None, src, data)
		return data, matcher.ratio(), 0

	elif isinstance(data, list):
		if isinstance(data[0], str):
			lower_data = [s.lower() for s in data]
			matches = difflib.get_close_matches(src.lower(), lower_data, cutoff=cutoff)
			if matches:
				match = matches[0]
				match_ratio = difflib.SequenceMatcher(None, src, match).ratio()
				match_index = lower_data.index(match)
				return data[match_index], match_ratio, match_index

			else:
				# If no close match was found, do a case-insensitive substring search
				for i, s in enumerate(data):
					if src.lower() in s.lower():
						return s, 0, i

		elif isinstance(data[0], dict) and data[0].get(item_key):
			result = {}, 0, None
			matcher = difflib.SequenceMatcher(None)
			matcher.set_seq2(src.lower())
			for i, obj in enumerate(data):
				string = obj[item_key].lower()
				matcher.set_seq1(string)
				ratio = matcher.ratio()
				if result[1] < ratio > cutoff:
					result = data[i].copy(), ratio, i
					if ratio == 1:
						break
			return result

	return "", 0, None


async def fetch_location(latitude: float, longitude: float) -> Optional[Dict[str, any]]:
	if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
		return None

	cache_key = f"{latitude},{longitude}"
	try:
		cached_result = cache.get(cache_key)
	except Exception as error:
		log.info(f"Cache error occurred on getting location: {error}")
		cached_result = None

	if cached_result is not None:
		return cached_result

	params = {
		"format": "jsonv2",
		"lon": longitude,
		"lat": latitude,
	}

	res = await fetch(OPENSTREETMAP_GEOCODE_URL, params=params)
	data = res[0]

	if data and "address" in data:
		address = data["address"]
		state = address.get("state", None)
		city = address.get("city", None)
		result = {
			"region": state,
			"city": city,
			"latitude": longitude,
			"longitude": longitude,
		}
		try:
			cache.set(cache_key, result)
		except Exception as error:
			log.info(f"Cache error occurred on saving location: {error}")
		return result
	else:
		return {}


def detect_social(url: str) -> dict:
	"""
	Detects the social media platform and username associated with a given URL.

	Args:
	    url: The URL to detect the social media platform and username for.

	Returns:
	    A dictionary containing the name of the social media platform, the url and icon.
	"""
	if not url:
		return {"src": "", "icon": "", "caption": ""}

	icon = "📱"
	username = ""
	if 'telegram.me' in url or 't.me' in url:
		messenger_name = 'Telegram'
		username = '@'
	elif 'instagram.com' in url:
		messenger_name = 'Instagram'
		username = '@'
	elif 'whatsapp.com' in url or 'wa.me/' in url:
		messenger_name = 'WhatsApp'
	elif 'vk.com' in url:
		messenger_name = 'Вконтакте'
		username = '@' if not url.split('/')[-1].startswith("id") else ""
	else:
		messenger_name = ""
		username = url

	if username != url:
		username += url.split('/')[-1]
	return {"src": username, "icon": icon, "caption": messenger_name}


################################ API ################################
async def fetch(url, headers=None, params=None, data=None, method='GET', timeout=30) -> Tuple:
	async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout), trust_env=True) as session:
		try:
			async with session.request(method, url, headers=headers, params=params, json=data) as response:
				response.raise_for_status()
				headers = response.headers
				status: int = response.status
				if response.content_type == "application/json":
					json = await response.json()
				else:
					json = await response.text()

				return json, status, None, headers

		except aiohttp.ClientConnectionError as error:
			print(f"HTTP error occurred: {error}")
			error_message = f"Client connection error!\n{str(error)}"
			error_code = 503

			return None, error_code, error_message, {}

		except aiohttp.ClientResponseError as error:
			print(f"HTTP error occurred: {error}")
			error_code = error.status
			error_message = f'{error.message} (content type: {response.content_type})'

		except aiohttp.ServerTimeoutError as error:
			print(f"Server timeout error occurred: {error}")
			error_code = error.__class__.__name__
			error_message = error.args[0]

		except Exception as error:
			print(f"Exception occurred: {error}")
			error_code = error.__class__.__name__
			error_message: str = error.args[0]

		return None, error_code, error_message, {}


async def fetch_user_data(
		user_id: int = None,
		endpoint: str = "",
		params: dict = None,
		data: any = None,
		headers: dict = None,
		method: Literal["GET", "POST", "PATCH", "DELETE"] = "GET"
):
	url = SERVER_URL or "http://localhost:8000"
	api_url = replace_double_slashes("{}/api/users/{}/{}/".format(url, str(user_id or ""), endpoint))
	response = await fetch(api_url, params=params, data=data, headers=headers, method=method)
	data, status_code, error, headers = response
	if error or not data:
		return {
			"data": None,
			"status_code": status_code,
			"error": error,
			"url": api_url
		}

	return {
		"data": data,
		"status_code": status_code,
		"error": None,
		"token": headers.get("token", None),
	}


async def fetch_data(endpoint: str, params: dict = None, data: dict = None, method: str = "GET"):
	url = SERVER_URL or "http://localhost:8000"
	api_url = replace_double_slashes(f'{url}/api/{endpoint.replace("None", "")}/')
	response = await fetch(api_url, params=params, data=data, method=method)
	data, status_code, error, _ = response
	if params is not None:
		api_url += "?" + urlencode(params, doseq=True)

	if error or not data:
		return {
			'data': [],
			'status_code': status_code,
			'error': error,
			'url': f'{api_url} ({method})'
		}

	return {
		'data': data,
		"status_code": status_code,
		'error': None
	}


def generate_map_url(address: Optional[str], org_name: str = "") -> str:
	if not address:
		return ""

	url = f'https://yandex.ru/maps/?text={address}'
	if org_name:
		url += f', {org_name}'
	return url

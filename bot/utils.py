import difflib
import re
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Union, List, Any, Tuple
from urllib.parse import urlencode

import aiohttp
import unicodedata
from django.core.cache import cache
from slugify import slugify
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ChatMember
from telegram.ext import CommandHandler, filters, CallbackContext

from bot.bot_settings import SERVER_URL
from bot.constants.api import OPENSTREETMAP_GEOCODE_URL
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
	Example:
		@send_action(ChatAction.TYPING)
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


def build_menu(
		buttons: List, n_cols: int,
		header_buttons: Optional[bool] = None,
		footer_buttons: Optional[bool] = None
):
	menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
	if header_buttons:
		menu.insert(0, [header_buttons])
	if footer_buttons:
		menu.append([footer_buttons])
	return menu


def generate_reply_keyboard(
		data: Union[List[str], List[List[str]], List[Dict[str, Any]], None],
		resize_keyboard: bool = True,
		one_time_keyboard: bool = True,
		is_persistent: bool = False,
		share_location: bool = False,
		share_contact: bool = False,
		**kwargs
) -> Optional[ReplyKeyboardMarkup]:
	"""
	Generates a reply keyboard markup for Telegram bot API.
	Args:
		:param data: The data to be displayed on the keyboard. Can be a list of strings,
		a list of lists of strings, or a list of dictionaries.
		:param resize_keyboard: Whether the keyboard should be resized to fit the number of buttons.
		:param one_time_keyboard: Whether the keyboard should be hidden after use.
		:param is_persistent: Whether the keyboard should be always shown when the regular keyboard is hidden.
		:param share_location: Share current location
		:param share_contact: Share user contact information
		**kwargs: Additional keyword arguments to be passed to the KeyboardButton constructor.
	Returns:
		An instance of ReplyKeyboardMarkup containing the generated keyboard buttons.
		Returns None if the data is empty or invalid.
	"""
	if not data:
		return None
	buttons = []
	for row in data:
		if isinstance(row, str):
			row = [row]
		elif isinstance(row, dict):
			key = row.get("text", "button")
			row = [KeyboardButton(key, **kwargs)]
		buttons.append(row)

	if share_location:
		buttons.insert(0, [KeyboardButton("📍 Определить регион", request_location=True, **kwargs)])
	if share_contact:
		buttons.insert(0, [KeyboardButton("🗂 Поделиться контактом", request_contact=True, **kwargs)])

	return ReplyKeyboardMarkup(
		buttons, resize_keyboard=resize_keyboard, one_time_keyboard=one_time_keyboard, is_persistent=is_persistent
	)


# TODO: Обработать исключение для callback_data = [], когда его длина не совпадает с общим количеством строк в data
def generate_inline_keyboard(
		data: Union[List[str], List[List[str]], List[Dict[str, Any]], None],
		item_key: Optional[str] = None,
		item_prefix: Optional[Union[str, List[str]]] = "",
		callback_data: Optional[Union[str, List[str], List[List[str]]]] = None,
		prefix_callback_name: Optional[str] = None,
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
		vertical: Whether the buttons should be displayed vertically or horizontally.
		prefix_callback_name: The string to be added as a prefix to the callback data string.
		item_prefix: A string or list of strings to be added as a suffix to the button label.
		**kwargs: Additional keyword arguments to be passed to the InlineKeyboardButton constructor.
	Returns:
		An instance of InlineKeyboardMarkup containing the generated keyboard buttons.
		Returns None if the data is empty or invalid.
	"""
	if not data:
		return None

	if not callback_data:
		callback_data = [str(i) for i in range(len(data))]
	elif isinstance(callback_data, str):
		callback_data = [callback_data] * len(data)
	elif isinstance(callback_data, list) and isinstance(callback_data[0], list):
		callback_data = [item for sublist in callback_data for item in sublist]
	buttons = []

	for i, row in enumerate(data):

		if isinstance(row, str):
			row = [InlineKeyboardButton(
				row,
				callback_data=(prefix_callback_name + str(callback_data.pop(0)))
				if prefix_callback_name else str(callback_data.pop(0)) if callback_data else str(i),
				**kwargs
			)]

		elif isinstance(row, dict):
			key = row.get(callback_data[i], slugify(row.get(item_key, callback_data[i]), separator="_"))
			item = row.get(item_key, key)

			if item_prefix:
				if isinstance(item_prefix, list):
					item_postfix = "".join(
						[str(row.get(post_key, post_key)) for post_key in item_prefix]
					)
				else:
					item_postfix = str(row.get(item_prefix, item_prefix if item_prefix else ""))

				if "None" not in item_postfix:
					item = f"{item} {item_postfix}"

			callback_data_str = str(key)
			if prefix_callback_name:
				callback_data_str = prefix_callback_name + callback_data_str
			row = [InlineKeyboardButton(item, callback_data=callback_data_str, **kwargs)]

		elif isinstance(row, list):
			item_postfix = "".join(item_prefix) if isinstance(item_prefix, list) else item_prefix
			left_part = ""
			right_part = ""
			if item_postfix:
				if item_postfix[-1] == " ":
					left_part = item_postfix
				else:
					right_part = item_postfix

			row = [
				InlineKeyboardButton(
					text=left_part + item + right_part,
					callback_data=(prefix_callback_name + str(callback_data.pop(0)))
					if prefix_callback_name else str(callback_data.pop(0))
					if callback_data else slugify(item, separator="_"),
					**kwargs,
				)
				for item in row
			]
		buttons.append(row)

	if vertical:
		buttons = [[btn] for row in buttons for btn in row]
	else:
		buttons = [row for row in buttons]

	return InlineKeyboardMarkup(buttons)


def update_inline_keyboard(
		inline_keyboard: Union[List[List[InlineKeyboardButton]], Tuple[Tuple[InlineKeyboardButton]]],
		active_value: str,
		button_type: str = "radiobutton",
) -> InlineKeyboardMarkup:
	new_inline_keyboard = []

	for row in inline_keyboard:
		new_row = []
		buttons_count = len(row)
		for button in row:
			if button_type == 'rate':
				rate = int(active_value)
				level = rate / buttons_count
				if int(button.callback_data[-1]) <= rate:
					if level > 0.7:
						symbol = "🟩"
					elif level >= 0.5:
						symbol = "🟨"
					else:
						symbol = "🟧️"
					new_button = InlineKeyboardButton(symbol, callback_data=button.callback_data)
				else:
					symbol = "⬜️️️"
					new_button = InlineKeyboardButton(symbol, callback_data=button.callback_data)
			else:
				if button.callback_data == active_value:
					if button_type == 'checkbox':
						symbol = "☑️"
						text = f"{button.text} {symbol}" if not button.text.endswith(symbol) else button.text[:-2]
						new_button = InlineKeyboardButton(text, callback_data=button.callback_data)
					else:
						symbol = "🔹"
						text = f"{symbol}{button.text.strip(symbol)}{symbol}"
						new_button = InlineKeyboardButton(text, callback_data=button.callback_data)
				else:
					if button_type == 'checkbox':
						new_button = InlineKeyboardButton(button.text, callback_data=button.callback_data)
					else:
						symbol = "🔹"
						new_button = InlineKeyboardButton(button.text.strip(symbol), callback_data=button.callback_data)

			new_row.append(new_button)
		new_inline_keyboard.append(new_row)

	return InlineKeyboardMarkup(new_inline_keyboard)


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

	if absolute_value:
		years_of_work = start_year
	else:
		current_year = datetime.now().year
		years_of_work = current_year - start_year

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


def data_list_to_string(data: List[dict], field_names: Union[str, List[str]], separator: str = "\n") -> str:
	"""
		Converts a list of dictionaries into a string with specific fields formatted as desired.
		:param data: A list of dictionaries to extract values from.
		:param field_names: A string or list of strings representing the field names to extract values for.
		:param separator: A string used to separate the values in the resulting string. Default is a newline character.
		:return: A string representing the values extracted from the dictionaries.
	"""
	if not data:
		return ""

	result_list = extract_fields(data, field_names)

	if not result_list:
		return ""

	if isinstance(result_list[0], str):
		return separator.join(result_list)

	result = ""
	for fields in result_list:
		line = str(fields[0])
		if len(fields) > 1:
			line += f": {' '.join(map(str, fields[1:]))}"
		result += line + separator

	return result.rstrip(separator)


def format_output_text(
		caption: str = "",
		value: Union[str, list] = None,
		default_value: str = "",
		default_sep: str = ":",
		value_tag: str = ""
) -> str:
	if (not value or isinstance(value, str) and str(value).strip('\n') == "") and not default_value:
		return ""

	if isinstance(value, list):
		value = value[0] if len(value) == 1 else "\n- " + "\n- ".join(value)

	result = f'{caption}{default_sep} ' if caption else ""
	result += f'{value_tag}{value or default_value}{value_tag}'
	return "\n" + result.lstrip()


def format_output_link(caption: str = '', link_text: str = '', src: str = '', link_type: str = "https") -> str:
	if not src:
		return ""

	if link_type.lower() == "tel":
		url = f'tel:{src}'
	elif link_type.lower() == "email":
		url = f'mailto:{src}'
	elif src.startswith('http://') or src.startswith('https://'):
		url = src
	else:
		url = f"{link_type}://{src}"

	url = f'[{link_text or src}]({url})'

	return format_output_text(caption, url, default_sep=" ")


def rating_to_string(rates: dict, questions: dict, rate_value: int = 8) -> str:
	if not rates or not questions:
		return ""

	result = ""
	for key, val in rates.items():
		if val is None:
			continue

		name = questions.get(key)
		if not name:
			continue

		rate = min(round(val), rate_value)
		level = rate / rate_value

		if level > 0.7:
			symbol = "🟩"
		elif level >= 0.5:
			symbol = "🟨"
		else:
			symbol = "🟧️"

		empty_rate = "⬜" * (rate_value - rate)
		result += f"{name}:\n{symbol * rate}{empty_rate}\n"

	return result


def find_obj_in_dict(list_dict: list, params: Dict[str, Any], condition: str = "AND"):
	"""
	Finds an object within a list of dictionaries based on specified keys and values, using the specified condition.
	:param list_dict: A list of dictionaries to search within.
	:param params: A dictionary containing keys and values to search for.
	:param condition: The condition to use for matching. Possible values are "AND" (default) or "OR".
	:return: The first dictionary that matches the specified keys and values using the specified condition, or None if no match is found.
	"""
	for elem in list_dict:
		if isinstance(elem, dict):  # Check if elem is a dictionary
			if condition == "AND":
				if all(elem.get(key) == value for key, value in params.items() if value is not None):
					return elem
			elif condition == "OR":
				if any(elem.get(key) == value for key, value in params.items() if value is not None):
					return elem
	return None


def find_obj_in_list(arr: List[Dict[str, Any]], search_params: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
	if search_params is None:
		return {}, -1
	for i, obj in enumerate(arr):
		if all(obj.get(key) == value for key, value in search_params.items()):
			return obj, i

	return {}, -1


def remove_item_from_list(src: List[Dict[str, Any]], key: str, value: Any) -> bool:
	obj, i = find_obj_in_list(src, {key: value})
	if obj:
		src.pop(i)
		return True

	return False


def remove_duplicates(data: List[dict], field: str) -> None:
	"""
	Removes dictionary duplicates in a list based on the specified field.

	Arguments:
	- data: A list of dictionaries to remove duplicates from.
	- field: The field to use for removing duplicates.

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


def replace_or_add_string(text, keyword, replacement):
	lines = text.split("\n")
	for i in range(len(lines)):
		if keyword in lines[i]:
			lines[i] = replacement
	new_text = "\n".join(lines)
	return new_text


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
	return s.encode(code_alias, 'ignore').decode(code_alias).strip()


def flatten_list(
		lst: List[Union[str, List[str]]],
		exclude: Optional[Union[str, List[str]]] = None,
		delimiter: str = ''
) -> str:
	"""
	Given a list of strings and lists of strings, returns a flattened string with the specified delimiter.
	Args:
		lst (List[Union[str, List[str]]]): A list of strings and lists of strings to flatten.
		exclude (Optional[Union[str, List[str]]]): A string or list of strings to exclude from the flattened string.
			Defaults to None.
		delimiter (str): The delimiter to use between flattened strings. Defaults to ''.
	Returns:
		str: The flattened string without special characters.
	"""
	if not lst:
		return ''
	if not exclude:
		exclude = []
	if isinstance(exclude, str):
		exclude = [exclude]

	stack = lst.copy()
	flattened = []
	while stack:
		item = stack.pop()
		if isinstance(item, list):
			stack.extend(item[::-1])
		elif item not in exclude:
			flattened.append(remove_special_chars(item))

	return delimiter.join(flattened)


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

	Arguments:
		src -- The source string or dictionary to compare against.
		data -- The data to compare to (either a string, a list of strings, or a list of dictionaries).
		item_key -- The key to use when comparing a list of dictionaries (optional).
		cutoff -- The minimum similarity ratio required for a match (default 0.5).

	Returns:
		A tuple containing the closest match object, the similarity ratio, and the index of the match (if applicable).

	Example usage:
		>>> data = ['banana', 'apple', 'cherry']
		>>> fuzzy_compare('aple', data)
		('apple', 0.8, 1)
	"""

	def get_best_match(element):
		# Find the closest match for the current element using recursive approach
		match, match_ratio, match_index = fuzzy_compare(element, data, item_key, cutoff)
		return match, match_ratio, match_index

	if not src:
		return "", 0, None

	if isinstance(src, dict):
		# If the source is a dictionary, convert its values to a list of strings
		src = [str(v) for v in src.values()]

	if isinstance(src, list):
		# If the source is a list, find the closest match for each element and select the one with the highest match ratio
		best_match = ('', 0, None)
		for element in src:
			match, match_ratio, match_index = get_best_match(element)
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

		elif isinstance(data[0], dict) and item_key in data[0]:
			lower_data = [d[item_key].lower() for d in data]
			matches = difflib.get_close_matches(src.lower(), lower_data, cutoff=cutoff)
			if matches:
				match = matches[0]
				match_ratio = difflib.SequenceMatcher(None, src, match).ratio()
				match_index = next((i for i, d in enumerate(data) if d[item_key].lower() == match), None)
				return data[match_index], match_ratio, match_index

			else:
				# If no close match was found, do a case-insensitive substring search
				for i, s in enumerate(data):
					if src.lower() in s[item_key].lower():
						return s, 0, i

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


def detect_social(url: str = None) -> Tuple[str, str, str]:
	if not url:
		return "", "", ""

	username = ''
	if 'telegram.me/' in url or 't.me/' in url:
		messenger_name = 'Telegram'
		username = '@'
	elif 'instagram.com/' in url:
		messenger_name = 'Instagram'
		username = '@'
	elif 'whatsapp.com/' in url or 'wa.me/' in url:
		messenger_name = 'WhatsApp'
	elif 'vk.com/' in url:
		messenger_name = 'Вконтакте'
		username = '@' if not url.split('/')[-1].startswith("id") else ""
	else:
		return "", "", ""
	username += url.split('/')[-1]
	return messenger_name, username, url


################################ API ################################
async def fetch(url, headers=None, params=None, data=None, method='GET', timeout=30) -> Tuple:
	async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout), trust_env=True) as session:
		try:
			async with session.request(method, url, headers=headers, params=params, json=data) as response:
				response.raise_for_status()
				json = await response.json()
				headers = response.headers
				status: int = response.status

				return json, status, None, headers

		except aiohttp.ClientConnectionError as error:
			print(f"HTTP error occurred: {error}")
			error_message = f"Client connection error!\n{str(error)}"
			error_code = 503

			return None, error_code, error_message, {}

		except aiohttp.ClientResponseError as error:
			print(f"HTTP error occurred: {error}")
			error_code = error.status
			error_message = error.message

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
		user_id: Union[str, int] = "",
		endpoint: str = "",
		params=None,
		method: str = "GET",
		headers: Optional[Dict] = None,
		data: Optional[Dict] = None
):
	url = SERVER_URL or "http://localhost:8000"
	api_url = replace_double_slashes("{}/api/users/{}/{}/".format(url, str(user_id), endpoint))
	response = await fetch(api_url, params=params, method=method, headers=headers, data=data)
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
		"token": headers.get("token", None),
	}


async def fetch_data(
		endpoint: str,
		params=None,
		method: str = "GET",
):
	url = SERVER_URL or "http://localhost:8000"
	api_url = replace_double_slashes(f"{url}/api/{endpoint}/")
	response = await fetch(api_url, params=params, method=method)
	data, status_code, error, _ = response
	if params is not None:
		api_url += "?" + urlencode(params, doseq=True)

	if error or not data:
		return {
			'data': [],
			'status_code': status_code,
			'error': error,
			'url': api_url
		}

	return {
		'data': data,
		"status_code": status_code
	}


def generate_map_url(address: str, org_name: str = "") -> str:
	if not address:
		return ""

	url = f'https://yandex.ru/maps/?text={address}'
	if org_name:
		url += f', {org_name}'
	return url

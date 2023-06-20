import difflib
import re
from functools import wraps
from typing import Optional, Dict, Union, List, Any, Tuple

import aiohttp
from django.core.cache import cache
from slugify import slugify
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import CommandHandler, filters, CallbackContext

from bot.bot_settings import SERVER_URL
from bot.constants.api import OPENSTREETMAP_GEOCODE_URL


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


def allowed_roles(roles, channel_id=None):
	def decorator(func):
		@wraps(func)
		async def wrapped(update: Update, context: CallbackContext):
			user = update.effective_user
			if not channel_id:
				chat_id = update.effective_chat.id
			else:
				chat_id = channel_id

			# Получаем информацию о пользователе
			member = await context.bot.get_chat_member(chat_id, user.id)

			# Проверяем, имеет ли пользователь одну из разрешенных ролей
			if member.status in roles:
				return await func(update, context)
			else:
				await update.message.reply_text("У вас нет прав для выполнения этой команды.")

		return wrapped

	return decorator


# def get_conv_state(state: Type[Enum], value: any) -> Optional[Enum]:
# 	for item_name, item_value in state.__members__.items():
# 		if item_value.value == value:
# 			return item_value
# 	return None


def build_menu(buttons: List, n_cols: int, header_buttons: Optional[bool] = None,
               footer_buttons: Optional[bool] = None):
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
		selective: Optional[bool] = None,
		**kwargs
) -> Optional[ReplyKeyboardMarkup]:
	"""
	Generates a reply keyboard markup for Telegram bot API.
	Args:
		data: The data to be displayed on the keyboard. Can be a list of strings,
		a list of lists of strings, or a list of dictionaries.
		resize_keyboard: Whether the keyboard should be resized to fit the number of buttons.
		one_time_keyboard: Whether the keyboard should be hidden after use.
		selective: Whether the keyboard should be shown only to specific users.
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

	return ReplyKeyboardMarkup(
		buttons, resize_keyboard=resize_keyboard, one_time_keyboard=one_time_keyboard, selective=selective
	)


# TODO: Обработать исключение для callback_data = [], когда его длина не совпадает с общим количеством строк в data
def generate_inline_keyboard(
		data: Union[List[str], List[List[str]], List[Dict[str, Any]], None],
		item_key: Optional[str] = None,
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
			callback_data_str = str(key)
			if prefix_callback_name:
				callback_data_str = prefix_callback_name + callback_data_str
			row = [InlineKeyboardButton(item, callback_data=callback_data_str, **kwargs)]
		elif isinstance(row, list):
			row = [
				InlineKeyboardButton(
					item,
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
		button_type: str = "bold",
) -> InlineKeyboardMarkup:
	new_inline_keyboard = []
	for row in inline_keyboard:
		new_row = []
		for button in row:
			if button_type == 'rate':
				if int(button.callback_data[-1]) <= int(active_value[-1]):
					new_button = InlineKeyboardButton('🌟', callback_data=button.callback_data)
				else:
					new_button = InlineKeyboardButton('⭐️', callback_data=button.callback_data)
			else:
				if button.callback_data == active_value:
					if button_type == 'checkbox':
						icon = "☑️"
						button_text = f"{button.text} {icon}" if not button.text.endswith(icon) else button.text[:-2]
						new_button = InlineKeyboardButton(button_text, callback_data=button.callback_data)
					elif button_type == 'radiobutton':
						new_button = InlineKeyboardButton(f"🔘 {button.text}", callback_data=button.callback_data)
					else:
						new_button = InlineKeyboardButton(f"<b>{button.text}</b>", callback_data=button.callback_data)
				else:
					if button_type == 'radiobutton':
						new_button = InlineKeyboardButton(f"⚪️ {button.text}", callback_data=button.callback_data)
					else:
						new_button = InlineKeyboardButton(button.text, callback_data=button.callback_data)
			new_row.append(new_button)
		new_inline_keyboard.append(new_row)
	return InlineKeyboardMarkup(new_inline_keyboard)


def convert_obj_to_tuple_list(obj_list, *keys) -> List[Optional[Tuple]]:
	tuple_list = []
	for obj in obj_list:
		tuple_list.append(tuple(obj.get(key) for key in keys))
	return tuple_list


def find_obj_in_list(arr: List[Dict[str, Any]], key: str, value: Any) -> Tuple[Dict[str, Any], int]:
	if value is None:
		return {}, -1
	for i, obj in enumerate(arr):
		if obj[key] == value:
			return obj, i
	return {}, -1


def get_key_values(arr: list, key: str) -> List[str]:
	return [obj.get(str(key)) for obj in arr]


def determine_greeting(hour: int) -> str:
	if 5 < hour < 12:
		greeting = 'Доброе утро'
	elif 12 < hour < 17:
		greeting = 'Добрый день'
	else:
		greeting = 'Добрый вечер'
	return greeting


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
		str: The flattened string.
	"""
	if not lst:
		return ''
	if not exclude:
		exclude = []
	if isinstance(exclude, str):
		exclude = [exclude]
	flattened = []
	for item in lst:
		if isinstance(item, list):
			flattened.extend(flatten_list(item, exclude))
		elif item not in exclude:
			flattened.append(item)
	return delimiter.join(flattened)


def filter_list(
		list_: List[Union[Dict, Any]],
		filter_key: str = None,
		filter_value: Any = None,
		sort_key: str = None,
		reverse: bool = False
) -> List[Union[Dict, Any]]:
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
		src: str,
		data: Union[str, List[str], List[Dict[str, Union[str, int]]]],
		item_key: Optional[str] = None,
		cutoff: float = 0.5
) -> Tuple[Union[Dict, str], float, Optional[int]]:
	"""
	Find the closest match to a source string in a list of strings or dictionaries using the difflib library.

	Arguments:
		src -- The source string to compare against.
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

	if isinstance(data, str):
		matcher = difflib.SequenceMatcher(None, src, data)
		return data, matcher.ratio(), -1

	elif isinstance(data, list):
		if isinstance(data[0], str):
			list2 = [s.lower() for s in data]
			matches = difflib.get_close_matches(src.lower(), list2, cutoff=cutoff)
			if matches:
				match = matches[0]
				match_ratio = difflib.SequenceMatcher(None, src, match).ratio()
				match_index = list2.index(match)
				return data[match_index], match_ratio, match_index

			else:
				# If no close match was found, do a case-insensitive substring search
				for i, s in enumerate(data):
					if src.lower() in s.lower():
						return s, 0, i

		elif isinstance(data[0], dict) and item_key in data[0]:
			list2 = [d[item_key].lower() for d in data]
			matches = difflib.get_close_matches(src.lower(), list2, cutoff=cutoff)
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


def replace_double_slashes(url: str):
	return re.sub(r'(?<!:)//+', '/', url)


################################ API ################################
async def fetch(url, headers=None, params=None, data=None, method='GET', timeout=10) -> Tuple:
	async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout), trust_env=True) as session:
		try:
			async with session.request(method, url, headers=headers, params=params, json=data) as response:
				response.raise_for_status()
				json = await response.json()
				headers = response.headers
				status: int = response.status

				return json, status, None, headers

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
		params=None,
		method: str = "GET",
		headers: Optional[Dict] = None,
		data: Optional[Dict] = None
):
	url = SERVER_URL or "http://localhost:8000"
	api_url = replace_double_slashes("{}/api/users/{}/".format(url, str(user_id)))
	response = await fetch(api_url, params=params, method=method, headers=headers, data=data)
	data, status_code, error, headers = response

	if error or not data:
		return {
			"data": None,
			'status_code': status_code,
			'error': error,
			'url': api_url
		}

	return {
		"data": data,
		"status_code": status_code,
		"token": headers.get('token', None),
	}


async def fetch_data(
		endpoint: str,
		params=None,
		method: str = "GET",
):
	url = SERVER_URL or "http://localhost:8000"
	api_url = replace_double_slashes(f"{url}/api/{endpoint}/")
	data, status_code, error, _ = await fetch(api_url, params=params, method=method)

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


async def get_region_by_location(latitude: float, longitude: float) -> Optional[str]:
	if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
		return None

	cache_key = f"{latitude},{longitude}"
	try:
		cached_result = cache.get(cache_key)
	except Exception as error:
		print(f"Cache error occurred: {error}")
		cached_result = None

	if cached_result is not None:
		return cached_result

	params = {
		"format": "jsonv2",
		"lon": longitude,
		"lat": latitude,
	}

	res = await fetch(OPENSTREETMAP_GEOCODE_URL, params=params)
	data = res[0]  # возьмем первый элемент кортежа

	if data and "address" in data:
		address = data["address"]
		state = address.get("state")
		result = state if state else None
		try:
			cache.set(cache_key, result)
		except Exception as error:
			print(f"Cache error occurred: {error}")
		return result
	else:
		return None


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
		str: The flattened string.
	"""
	if not lst:
		return ''
	if not exclude:
		exclude = []
	if isinstance(exclude, str):
		exclude = [exclude]
	flattened = []
	for item in lst:
		if isinstance(item, list):
			flattened.extend(flatten_list(item, exclude))
		elif item not in exclude:
			flattened.append(item)
	return delimiter.join(flattened)


def filter_list(
		list_: List[Union[Dict, Any]],
		filter_key: str = None,
		filter_value: Any = None,
		sort_key: str = None,
		reverse: bool = False
) -> List[Union[Dict, Any]]:
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


def get_org(dic: dict, val: int):
    for elem in dic:
        if elem['id'] == val:
            return elem
    return None


def clear_results(results: list, new_dict: dict):
    new_results = []
    for elem in results:
        if not (new_dict['id'] == elem['id'] and new_dict['questions_key1'] == elem['questions_key1']):
            new_results.append(elem)

    return new_results


def get_dict(list_dict: list, user_id: int):
    for elem in list_dict:
        if elem['id'] == user_id:
            return elem
    return None

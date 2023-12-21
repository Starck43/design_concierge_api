from os import path
from typing import List, Union, Optional

import re
import yaml
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date

from api.models import Event, UserGroup

from bot.logger import log


def load_config(filename: str):
	current_file_path = path.abspath(__file__)

	# Получить путь к директории, содержащей текущий файл
	current_directory = path.dirname(current_file_path)

	# Сконструировать путь к файлу конфигурации относительно текущей директории
	config_file_path = path.join(current_directory, filename)

	with open(config_file_path, "r") as file:
		config = yaml.safe_load(file)
	return config


def get_params_for_group(config: List[dict], group: int, date_from: str = None, date_to: str = None):
	params = []

	for resource in config:
		for group_params in resource.get("params", []):
			if group_params.get("group") == group:
				param_copy = group_params.copy()
				date_to_format = param_copy.get("date_to", {}).get("value")
				date_from_format = param_copy.get("date_from", {}).get("value")
				param_copy["date_to"]["value"] = format_date(date_to, date_to_format)
				if param_copy["date_to"]["value"] and not date_from:
					param_copy["date_from"]["value"] = format_date(datetime.now(), date_to_format)
				elif date_from:
					param_copy["date_from"]["value"] = format_date(date_from, date_from_format)
				params.append(param_copy)

	return params


def format_date(date: Union[str, datetime], date_format: str):
	if not date or not date_format:
		return None

	date_obj = date
	if isinstance(date_obj, str):
		date_obj = datetime.strptime(date_obj, "%d.%m.%Y")
	return date_obj.strftime(date_format).lower()


def build_url(base_url: str, params: dict):
	url = base_url
	query_params = []
	pathname = ""

	for key, value in params.items():
		if isinstance(value, dict):
			if value.get("is_query_param"):
				if value.get("name") and value.get("value"):
					query_params.append(f"{value['name']}={value['value']}")
			else:
				pathname += f"/{value.get('name') or ''}/{value.get('value') or ''}"

	if pathname:
		url += pathname

	elif params.get("query_pathname"):
		url += params["query_pathname"]

	if query_params:
		url += "?" + "&".join(query_params)

	if params.get("search_query"):
		url += ("&" if query_params else "?") + params.get("search_query")

	return re.sub(r'(?<!:)//+', '/', url)


def load_events(events_type: int, group: int, date_from: date = None, date_to: date = None) -> Optional[dict]:
	config = load_config(f'schema-{events_type}.yml')
	if not config:
		return

	params = get_params_for_group(config, group, date_from, date_to)

	for resource in config:
		base_url = resource.get("url", "")
		schema = resource.get("output", {})

		for param in params:
			url = build_url(base_url, param)
			message = f'Sent request on {url}'
			log.info(message)
			response = requests.get(url)

			if response.status_code == 200:
				message = f'Got response [200 OK]'
				log.info(message)
				return parse_events(events_type, group, response.text, base_url, schema)

			else:
				message = f'Error occurred while sending request on {url}'
				log.error(message, extra=response.headers)


def parse_events(events_type: int, group: int, html: str, base_url: str, schema: dict) -> Optional[List[Event]]:
	soup = BeautifulSoup(html, 'html.parser')
	events = []
	root_container = schema.get("root")
	if not root_container:
		log.warning("Root container not found in schema")
		return

	event_elements = soup.select(root_container + " " + (schema.get("children") or ""))
	for event_element in event_elements:
		event_data = {"type": events_type}
		for field in schema.get("fields"):
			field_name = field.get("field")
			selector = field.get("selector")
			attribute = field.get("attribute")

			if not selector:
				continue

			element = event_element.select_one(selector)
			if not element:
				continue

			if attribute:
				value = element.get(attribute)
				if attribute in ["href", "src"] and (not value.startswith("http") or value.startswith("/")):
					value = base_url + value
			else:
				value = element.get_text(strip=True)

			event_data[field_name] = value

			if field_name == "start_date":
				date_values = value.split("-")
				if len(date_values) == 2:
					event_data["start_date"] = datetime.strptime(date_values[0].strip(), "%d.%m.%Y")
					event_data["end_date"] = datetime.strptime(date_values[1].strip(), "%d.%m.%Y")
				else:
					event_data["start_date"] = datetime.strptime(value, "%d.%m.%Y")

		try:
			Event.objects.get(source_link=event_data["source_link"])
		except Event.DoesNotExist:
			event = Event(**event_data)
			events.append(event)

	Event.objects.bulk_create(events)
	try:
		user_group = UserGroup.objects.get(code=group)
		for event in events:
			event.group.set([user_group])  # присвоим после создания событий номер группы для связанной таблицы many2many

	except UserGroup.DoesNotExist:
		log.warning(f"UserGroup with code {group} does not exist")
		return None

	return events

from datetime import date, timedelta
from typing import Tuple

from django.core.files.storage import FileSystemStorage


class MediaFileStorage(FileSystemStorage):
	def save(self, name, content, max_length=None):
		if not self.exists(name):
			return super().save(name, content, max_length)
		else:
			# Prevent saving file on disk
			return name


def user_directory_path(instance, filename):
	directory_path = f'uploads/{instance.user.user_id}'
	return f'{directory_path}/{filename}'


def get_date_range(date_object: date = None) -> Tuple[date, date]:
	"""
	Возвращает диапазон дат в зависимости от указанного месяца.

	Аргументы:
	- date_object (str): Дата в формате datetime (по умолчанию None).

	Возвращает:
	Кортеж из двух дат: начальная и конечная дата указанного в аргументах месяца.
	"""

	today = date.today()

	if date_object:
		# Начальная дата - первое число указанного месяца и года
		start_date = date_object.replace(day=1)
		# Дата окончания - последнее число указанного месяца
		end_of_month = date_object.replace(day=1) + timedelta(days=32)
		end_date = end_of_month.replace(day=1) - timedelta(days=1)
	else:
		# Начальная дата - первое число текущего месяца
		start_date = date(today.year, today.month, 1)
		# Дата окончания - последнее число текущего месяца плюс 12 месяцев
		end_date = date(today.year, today.month, 1) + timedelta(days=31) + timedelta(days=365)

	return start_date, end_date

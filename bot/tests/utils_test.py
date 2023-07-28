import unittest
from bot.utils import extract_fields, data_list_to_string, rates_to_string


class TestListForField(unittest.TestCase):
	def setUp(self):
		self.arr = [
			{"name": "John", "age": 25, "city": "New York"},
			{"name": "Jane", "age": 30, "country": "Canada"},
			{"name": "Bob", "age": 22, "city": "Los Angeles"}
		]

	def test_empty_extract_fields(self):
		self.assertEqual(extract_fields([], "name"), [])

	def test_non_exist_key_for_field(self):
		self.assertEqual(extract_fields(self.arr, ["surname"]), ["surname", "surname", "surname"])

	def test_single_key_for_field(self):
		self.assertEqual(extract_fields(self.arr, ["name"]), ["John", "Jane", "Bob"])

	def test_single_not_key_for_field(self):
		self.assertEqual(extract_fields(self.arr, "name"), ["John", "Jane", "Bob"])

	def test_list_of_keys_for_field(self):
		self.assertEqual(
			extract_fields(self.arr, ["name", "city"]),
			[["John", "New York"], ['Jane', 'city'], ["Bob", "Los Angeles"]]
		)


class TestDataListToStr(unittest.TestCase):
	def setUp(self):
		self.arr = [
			{"name": "Продукт 1", "price": 100, "rate": 4.5},
			{"name": "Продукт 2", "price": 200, "rate": 5.0},
			{"name": "Продукт 3", "price": 150, "rate": 4.0},
		]

	def test_empty_list(self):
		self.assertEqual(data_list_to_string([], "name"), "")

	def test_single_key(self):
		result = "Продукт 1, Продукт 2, Продукт 3"
		self.assertEqual(data_list_to_string(self.arr, "name", separator=", "), result)

	def test_list_of_keys(self):
		result = "Продукт 1: 100\nПродукт 2: 200\nПродукт 3: 150"
		self.assertEqual(data_list_to_string(self.arr, ["name", "price"]), result)

	def test_list_of_not_only_keys(self):
		result = "Продукт 1: 4.5 ⭐\nПродукт 2: 5.0 ⭐\nПродукт 3: 4.0 ⭐"
		self.assertEqual(data_list_to_string(self.arr, ["name", "rate", "⭐"]), result)

	def test_single_not_key(self):
		result = "⭐, ⭐, ⭐"
		self.assertEqual(data_list_to_string(self.arr, ["⭐"], separator=", "), result)


if __name__ == '__main__':
	unittest.main()

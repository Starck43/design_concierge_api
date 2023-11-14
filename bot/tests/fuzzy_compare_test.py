import unittest

from bot.utils import fuzzy_compare


class TestFuzzyCompare(unittest.TestCase):
	def test_string_input(self):
		src = "apple"
		data = "apples"
		expected_output = ("apples", 0.9090909090909091, 0)
		self.assertEqual(fuzzy_compare(src, data), expected_output)

	def test_dict_and_list_of_strings_input(self):
		src = {"1": "apple", "2": "aple", "3": "aplle"}
		data = ["oranges", "bananas", "apples"]
		expected_output = ("apples", 0.9090909090909091, 2)
		self.assertEqual(fuzzy_compare(src, data), expected_output)

	def test_list_of_strings_input(self):
		src = "apple"
		data = ["oranges", "bananas", "apples"]
		expected_output = ("apples", 0.9090909090909091, 2)
		self.assertEqual(fuzzy_compare(src, data), expected_output)

	def test_list_of_dicts_input(self):
		src = "apple"
		data = [
			{"name": "Oranges", "price": 1.50},
			{"name": "Bananas", "price": 0.50},
			{"name": "Apples", "price": 1.00},
		]
		item_key = "name"
		expected_output = ({'name': 'Apples', 'price': 1.0}, 0.9090909090909091, 2)
		self.assertEqual(fuzzy_compare(src, data, item_key), expected_output)

	def test_dict_with_list_of_dicts_input(self):
		src = {"1": "apple", "2": "aple", "3": "aplle"}
		data = [
			{"name": "Oranges", "price": 1.50},
			{"name": "Bananas", "price": 0.50},
			{"name": "Apples", "price": 1.00},
		]
		item_key = "name"
		expected_output = ({'name': 'Apples', 'price': 1.0}, 0.9090909090909091, 2)
		self.assertEqual(fuzzy_compare(src, data, item_key), expected_output)

	def test_no_match(self):
		src = "apple"
		data = ["oranges", "bananas"]
		expected_output = ("", 0, None)
		self.assertEqual(fuzzy_compare(src, data), expected_output)

	def test_empty_input(self):
		src = ""
		data = ["oranges", "bananas"]
		expected_output = ("", 0, None)
		self.assertEqual(fuzzy_compare(src, data), expected_output)

	def test_cutoff(self):
		src = "apple"
		data = ["oranges", "bananas", "applesauce"]
		cutoff = 0.8
		expected_output = ("applesauce", 0, 2)
		self.assertEqual(fuzzy_compare(src, data, None, cutoff), expected_output)


if __name__ == '__main__':
	unittest.main()

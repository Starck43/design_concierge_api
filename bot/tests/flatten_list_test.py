import unittest

from bot.utils import flatten_list


class TestFlattenList(unittest.TestCase):
	def test_flatten_list_positive(self):
		lst = ['a', 'b', 'c', ['d', 'e'], 'f']
		self.assertEqual(flatten_list(lst, exclude='e', delimiter='|'), 'a|b|c|d|f')

	def test_flatten_list_negative(self):
		lst = ['a', 'b', 'c', ['d', 'e'], 'f']
		self.assertEqual(flatten_list(lst, exclude=['e', 'f'], delimiter='|'), 'a|b|c|d')

	def test_flatten_list_empty_list(self):
		lst = []
		self.assertEqual(flatten_list(lst, exclude='e', delimiter='|'), '')

	def test_flatten_list_nested_list(self):
		lst = ['a', 'b', ['c', 'd', ['e', 'f']], 'g']
		self.assertEqual(flatten_list(lst, exclude=['e', 'f'], delimiter='|'), 'a|b|c|d|g')

	def test_flatten_list_exclude_none(self):
		lst = ['a', 'b', 'c', ['d', 'e'], 'f']
		self.assertEqual(flatten_list(lst, exclude=None, delimiter='|'), 'a|b|c|d|e|f')

	def test_flatten_list_exclude_string(self):
		lst = ['a', 'b', 'c', ['d', 'e'], 'f']
		self.assertEqual(flatten_list(lst, exclude='e', delimiter='|'), 'a|b|c|d|f')

	def test_flatten_list_exclude_list(self):
		lst = ['a', 'b', 'c', ['d', 'e'], 'f']
		self.assertEqual(flatten_list(lst, exclude=['e', 'f'], delimiter='|'), 'a|b|c|d')


if __name__ == '__main__':
	unittest.main()

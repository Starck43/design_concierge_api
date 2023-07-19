from enum import Enum


class Group(Enum):
	DESIGNER: int = 0
	OUTSOURCER: int = 1
	SUPPLIER: int = 2
	UNCATEGORIZED: int = 3

	@staticmethod
	def get_enum(num: int) -> 'Group':
		for group in Group:
			if group.value == num:
				return group
		return Group(3)

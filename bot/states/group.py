from enum import Enum


class Group(Enum):
	DESIGNER: int = 0  # Если пользователь и дизайнер и аутсорсер
	OUTSOURCER: int = 1  # Если пользователь только аутсорсер
	SUPPLIER: int = 2  # Если пользователь только поставщик
	UNCATEGORIZED: int = 3

	@staticmethod
	def get_enum(num: int) -> 'Group':
		for group in Group:
			if group.value == num:
				return group
		return Group(3)

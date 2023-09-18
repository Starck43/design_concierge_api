from enum import Enum
from typing import Union, List


class Group(Enum):
	DESIGNER: int = 0  # Если пользователь дизайнер
	OUTSOURCER: int = 1  # Если пользователь аутсорсер
	SUPPLIER: int = 2  # Если пользователь поставщик
	UNCATEGORIZED: int = 3

	_group_dict = {
		0: DESIGNER,
		1: OUTSOURCER,
		2: SUPPLIER,
		3: UNCATEGORIZED
	}

	@staticmethod
	def get_enum(num: Union[int, List[int]]) -> Union['Group', List['Group']]:
		if isinstance(num, int) and 0 <= num <= 2:
			return Group(num)
		elif isinstance(num, list):
			return [Group(n) for n in num if 0 <= n <= 2]
		else:
			return Group(3)

	@staticmethod
	def get_groups_code(groups: list):
		if not groups:
			return "U"

		group_value = groups[0] + groups[-1]
		if group_value > 1 and len(groups) > 2:
			group_value = min(groups) * 2

		group_roles = {0: "D", 1: "DO", 2: "O", 4: "S", 6: "U"}

		return group_roles.get(group_value, "U")

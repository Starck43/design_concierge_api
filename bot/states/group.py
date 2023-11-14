from enum import Enum
from typing import Union, List

from telegram.ext import ContextTypes


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

	@classmethod
	def has_role(cls, user_details: dict, role: int):
		"""
		    Check if the user has a specific role.

		    Args:
		        user_details : Detail user data.
		        role (Group): The role to check.

		    Returns:
		        bool: True if the user has the specified role, False otherwise.
		"""
		if user_details:
			user_groups = cls.get_enum(user_details.get("groups", [3]))
			return role in user_groups
		return False

	@staticmethod
	def get_groups_code(groups: list):
		if not groups:
			return "U"

		group_value = groups[0] + groups[-1]
		if group_value > 1 and len(groups) > 2:
			group_value = min(groups) * 2

		group_roles = {0: "D", 1: "DO", 2: "O", 4: "S", 6: "U"}

		return group_roles.get(group_value, "U")

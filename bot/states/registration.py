from enum import Enum


class RegState(Enum):
	USER_GROUP_CHOOSING: str = "group"
	SERVICE_GROUP_REGISTRATION: str = "service_group"
	SUPPLIER_GROUP_REGISTRATION: str = "supplier_group"
	LOCATION_CHOOSING: str = "location"
	DONE: str = "done"

	def __str__(self):
		return self.value

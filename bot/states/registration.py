from enum import Enum


class RegState(Enum):
	SELECT_USER_GROUP: str = "group"
	INPUT_NAME: str = "name"
	SELECT_CATEGORIES: str = "category"
	INPUT_WORK_EXPERIENCE: str = "experience"
	SELECT_REGIONS: str = "regions"
	SELECT_SEGMENT: str = "segment"
	SELECT_SOCIALS: str = "socials url"
	SELECT_ADDRESS: str = "address"
	SUBMIT_REGISTRATION: str = "submit registration"
	VERIFICATION: str = "verification"
	SUBMIT_VERIFICATION_CODE: str = "submit verification code"
	DONE: str = "done"

	def __str__(self):
		return self.value

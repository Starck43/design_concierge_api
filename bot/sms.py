import re
from os import getenv
import dataclasses

from bot.logger import log
from bot.utils import fetch


@dataclasses.dataclass()
class TSMSResponse:
	id: str = "0"
	error: bool = True
	status_code: int = -1
	status_text: str = ""
	balance: float = 0


class SMSTransport:
	_URL = "https://sms.ru/sms/send"
	_API_ID = getenv("SMS_TOKEN")

	async def send(self, body: str, to: str) -> TSMSResponse:
		phone = to.replace('+', '')
		if not self.validate_phone(phone):
			log.warning(f"Phone validation: Invalid number {phone}")
			return TSMSResponse()

		params = {"api_id": self._API_ID, "to": phone, "msg": body, "json": 1}
		response, _, _, _ = await fetch(self._URL, params=params)

		if response and response["status"] == "OK":
			phone = response["sms"][phone]

			if phone["status"] == "OK":
				return TSMSResponse(
					error=False,
					status_code=phone["status_code"],
					status_text=phone["status_text"],
					balance=response['balance'],
					id=phone["sms_id"]
				)
			response["status"] = phone["status"]
			response["status_code"] = phone["status_code"]
			response["status_text"] = phone["status_text"]

		log.error("SMS error status %s", response)
		return TSMSResponse(
			status_code=response["status_code"],
			status_text=response["status_text"],
			balance=response["balance"],
		)

	@classmethod
	def validate_phone(cls, number):
		return re.match(r"^7[0-9]{10}$", number)

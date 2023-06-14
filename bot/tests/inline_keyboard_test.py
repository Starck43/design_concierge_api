import unittest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from bot.utils import update_inline_keyboard


class TestUpdateInlineKeyboard(unittest.TestCase):
	def setUp(self):
		self.inline_keyboard = [
			[InlineKeyboardButton("Button 1", callback_data="1")],
			[InlineKeyboardButton("Button 2", callback_data="2")],
			[InlineKeyboardButton("Button 3", callback_data="3")],
		]
		self.active_value = "2"
		self.new_active_value = "3"

	def test_update_inline_keyboard_bold(self):
		expected_output = InlineKeyboardMarkup(
			(
				(
					InlineKeyboardButton("Button 1", callback_data="1"),
				),
				(
					InlineKeyboardButton("Button 2", callback_data="2"),
				),
				(
					InlineKeyboardButton("<b>Button 3</b>", callback_data="3"),
				),
			)
		)
		update_inline_keyboard(self.inline_keyboard, self.active_value, button_type="bold")
		output = update_inline_keyboard(self.inline_keyboard, self.new_active_value, button_type="bold")
		self.assertEqual(output.to_dict(), expected_output.to_dict())

	def test_update_inline_keyboard_checkbox(self):
		expected_output = InlineKeyboardMarkup(
			(
				(
					InlineKeyboardButton("Button 1", callback_data="1"),
				),
				(
					InlineKeyboardButton("Button 2", callback_data="2"),
				),
				(
					InlineKeyboardButton("Button 3 ☑️", callback_data="3"),
				),
			)
		)
		update_inline_keyboard(self.inline_keyboard, self.active_value, button_type="checkbox")
		update_inline_keyboard(self.inline_keyboard, self.active_value, button_type="checkbox")
		output = update_inline_keyboard(self.inline_keyboard, self.new_active_value, button_type="checkbox")
		self.assertEqual(output.to_dict(), expected_output.to_dict())

	def test_update_inline_keyboard_radiobutton(self):
		expected_output = InlineKeyboardMarkup(
			(
				(
					InlineKeyboardButton("⚪️ Button 1", callback_data="1"),
				),
				(
					InlineKeyboardButton("⚪️ Button 2", callback_data="2"),
				),
				(
					InlineKeyboardButton("🔘 Button 3", callback_data="3"),
				),
			)
		)
		update_inline_keyboard(self.inline_keyboard, self.active_value, button_type="radiobutton")
		output = update_inline_keyboard(self.inline_keyboard, self.new_active_value, button_type="radiobutton")
		self.assertEqual(output.to_dict(), expected_output.to_dict())

	def test_update_inline_keyboard_invalid_button_type(self):
		expected_output = InlineKeyboardMarkup(
			(
				(
					InlineKeyboardButton("Button 1", callback_data="1"),
				),
				(
					InlineKeyboardButton("<b>Button 2</b>", callback_data="2"),
				),
				(
					InlineKeyboardButton("Button 3", callback_data="3"),
				),
			)
		)
		output = update_inline_keyboard(self.inline_keyboard, self.active_value, button_type="bold")
		self.assertEqual(output.to_dict(), expected_output.to_dict())


if __name__ == "__main__":
	unittest.main()

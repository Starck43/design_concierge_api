from typing import Optional

from telegram import Message, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.constants.keyboards import SEGMENT_KEYBOARD
from bot.handlers.common import select_supplier_segment
from bot.handlers.rating import show_total_detail_rating
from bot.states.group import Group
from bot.utils import (
	extract_fields, format_output_text, format_output_link, detect_social, generate_map_url, calculate_years_of_work,
)


async def show_user_card_message(
		message: Message,
		context: ContextTypes.DEFAULT_TYPE,
		user: dict,
		reply_markup: InlineKeyboardMarkup = None,
		show_all: bool = True
) -> Optional[Message]:
	# TODO: Решить какие поля скрывать для базового тарифа (show_all)
	if not user:
		return

	context.chat_data["last_message_id"] = None
	rating_string = f' ⭐{user["total_rating"]}' if user["total_rating"] else ""
	categories = extract_fields(user["categories"], field_names="name")
	regions = extract_fields(user["regions"], field_names="name")
	main_region = user["main_region"]["name"] if user.get("main_region") else None
	work_experience = calculate_years_of_work(user["business_start_year"])
	address_caption = f'{user["address"]}{" (на карте)" if user["address"] else ""}'
	geo_link = generate_map_url(user["address"], user["name"])
	phone_caption = "Позвонить" if user["phone"] else ""
	segment = None

	if Group.has_role(user, Group.SUPPLIER):
		if not user["segment"] is None:
			segment = SEGMENT_KEYBOARD[user["segment"]]
		else:
			segment = "не установлен"

	# TODO: сделать экранирование спецсимволов для ссылок в detect_social
	# отобразим сообщение карточки с полными данными
	inline_message = await message.reply_text(
		f'{format_output_text("", user["name"] + rating_string, value_tag="*")}\n'
		f'{format_output_text("", user["description"], value_tag="_")}'
		f'{format_output_link("📍", address_caption, geo_link)}'
		f'{format_output_link("📞️", phone_caption, user["phone"], link_type="tel")}'
		f'{format_output_link("🌐", user["site_url"], user["site_url"])}'
		f'{format_output_link(*detect_social(user["socials_url"]))}'
		f'{format_output_text("Сфера деятельности", categories, default_value="не выбрана", value_tag="`")}'
		f'{format_output_text("Основной регион", main_region, default_value="не установлен", value_tag="`")}'
		f'{format_output_text("Другие регионы", regions, value_tag="`")}'
		f'{format_output_text("Опыт работы", work_experience, value_tag="`")}'
		f'{format_output_text("Сегмент", segment, value_tag="`")}',
		reply_markup=reply_markup
	)
	
	await select_supplier_segment(message, context, user=user)
	await show_total_detail_rating(message, context, user=user)

	return inline_message

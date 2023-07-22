from typing import Union, Optional

from telegram import CallbackQuery, Update, Message
from telegram.ext import ContextTypes

from bot.constants.keyboards import SEGMENT_KEYBOARD
from bot.constants.menus import back_menu
from bot.constants.messages import offer_to_set_segment_message, show_rating_title_message
from bot.handlers.common import get_state_menu, get_user_rating_data
from bot.utils import (
	extract_fields, rating_to_string, format_output_text, format_output_link, detect_social, generate_map_url,
	calculate_years_of_work
)


async def user_details(
		query: Union[CallbackQuery, Update],
		context: ContextTypes.DEFAULT_TYPE,
		title: str = None,
		show_all: bool = True
) -> Optional[Message]:

	# TODO: Решить какие поля скрывать для базового тарифа (show_all)
	chat_data = context.chat_data
	chat_data.pop("saved_details_message", None)  # почистим сохраненное сообщение с карточкой пользователя

	selected_user = chat_data.get("selected_user")
	if selected_user is None:
		await query.message.reply_text("Нет данных", reply_markup=back_menu)
		return None

	_, _, _, markup_menu, inline_markup = get_state_menu(context)

	total_rate = f'⭐ {selected_user["total_rate"]}' if selected_user["total_rate"] else ""
	full_name = selected_user.get("name", "")
	categories = extract_fields(selected_user["categories"], field_names="name")
	regions = extract_fields(selected_user["regions"], field_names="name")
	main_region = selected_user["main_region"]["name"] if selected_user.get("main_region") else None
	work_experience = calculate_years_of_work(selected_user["business_start_year"])
	address_caption = f'{selected_user["address"]}{" (на карте)" if selected_user["address"] else ""}'
	geo_link = generate_map_url(selected_user["address"], full_name)
	phone_caption = "Позвонить" if selected_user["phone"] else ""

	if max(selected_user["groups"]) == 2:
		if selected_user["segment"]:
			segment = SEGMENT_KEYBOARD[selected_user["segment"]]
		else:
			segment = "не установлен"
	else:
		segment = ""

	reply_message = await query.message.reply_text(
		(title or
		 f'{"✅" if selected_user["user_id"] else ""} '
		 f'*{selected_user["username"].upper()}*\n'
		 ) + total_rate,
		reply_markup=markup_menu
	)
	chat_data["saved_details_message"] = await query.message.reply_text(
		f'{format_output_text("Полное название", full_name, value_tag="*")}\n'
		f'{format_output_text("", selected_user["description"], value_tag="_")}'
		f'{format_output_link("📍", address_caption, geo_link)}'
		f'{format_output_link("📞️", phone_caption, selected_user["phone"], link_type="tel")}'
		f'{format_output_link("🌐", selected_user["site_url"], selected_user["site_url"])}'
		f'{format_output_link(*detect_social(selected_user["socials_url"]))}'
		f'{format_output_text("`Сфера деятельности`", categories, default_value="не выбрана", value_tag="_")}'
		f'{format_output_text("`Основной регион`", main_region, default_value="не установлен", value_tag="_")}'
		f'{format_output_text("`Другие регионы`", regions, value_tag="_")}'
		f'{format_output_text("`Опыт работы`", work_experience, value_tag="_")}'
		f'{format_output_text("`Сегмент`", segment, value_tag="_")}',
		reply_markup=inline_markup
	)

	if max(selected_user["groups"]) == 2 and not selected_user["user_id"] and not selected_user["segment"]:
		await offer_to_set_segment_message(query.message)

	_, _, avg_rating_text = get_user_rating_data(context, selected_user)

	message = await show_rating_title_message(query.message, avg_rating_text)
	chat_data["saved_rating_message"] = message
	chat_data["last_message_id"] = message.message_id

	return reply_message

from typing import Optional

from telegram import Message, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.constants.keyboards import SEGMENT_KEYBOARD
from bot.handlers.common import select_supplier_segment, edit_or_reply_message
from bot.handlers.rating import show_total_detail_rating
from bot.states.group import Group
from bot.utils import (
	extract_fields, format_output_text, format_output_link, detect_social, generate_map_url, calculate_years_of_work,
)


async def show_user_card_message(
		context: ContextTypes.DEFAULT_TYPE,
		user: dict,
		message_id: int = None,
		reply_markup: InlineKeyboardMarkup = None,
		show_all: bool = True
) -> Optional[Message]:
	# TODO: Решить какие поля скрывать для базового тарифа (show_all)
	# TODO: сделать экранирование спецсимволов для ссылок в detect_social
	# TODO: сделать скрытие полей от других при разных условиях:
	#  при договоренности на бирже услуг или в зависимости от тарифа
	if not user:
		return

	context.chat_data["last_message_id"] = None
	rating_string = f' ⭐{user["total_rating"]}' if user.get("total_rating") else ""
	address_caption = f'{user["address"]} (на карте)' if user.get("address") else ""
	geo_link = generate_map_url(user.get("address"), user["name"])
	categories = extract_fields(user.get("categories"), field_names="name")
	regions = extract_fields(user.get("regions"), field_names="name")
	main_region = user.get("main_region", {}).get("name", None)
	work_experience = calculate_years_of_work(user.get("business_start_year"))
	segment = None
	done_orders = None
	placed_orders = None
	executor_done_orders = None

	if Group.has_role(user, Group.DESIGNER):
		# счетчик размещенных заказов
		placed_orders = user.get("placed_orders_count")
		# счетчик завершенных заказов
		done_orders = user.get("done_orders_count")

	if Group.has_role(user, Group.OUTSOURCER):
		# счетчик выполненных заказов
		executor_done_orders = user.get("executor_done_orders_count")

	if Group.has_role(user, Group.SUPPLIER):
		if not user.get("segment") is None:
			segment = SEGMENT_KEYBOARD[user["segment"]]
		else:
			segment = "не установлен"

	# отобразим сообщение карточки с полными данными
	inline_message = await edit_or_reply_message(
		context,
		f'{format_output_text("", user["name"] + rating_string, tag="*")}'
		f'{format_output_text("", user.get("description"), tag="_")}'
		f'\n'
		f'{format_output_link(geo_link, caption=address_caption, icon="📍")}'
		f'{format_output_link(user.get("phone"), icon="📞️", link_type="tel")}'
		f'{format_output_link(user.get("email"), icon="📧", link_type="email")}'
		f'{format_output_link(user.get("site_url"), icon="🌐")}'
		f'{format_output_link(**detect_social(user.get("socials_url")))}'
		f'{format_output_text("Сфера деятельности", categories, default_value="не выбрана", tag="`")}'
		f'{format_output_text("Основной регион", main_region, default_value="не установлен", tag="`")}'
		f'{format_output_text("Другие регионы", regions, tag="`")}'
		f'{format_output_text("Опыт работы", work_experience, tag="`")}'
		f'{format_output_text("Сегмент", segment, tag="`")}'
		f'\n'
		f'{format_output_text("Размещено заказов", placed_orders, tag="`")}'
		f'{format_output_text("Завершено заказов", done_orders, tag="`")}'
		f'{format_output_text("Выполнено заказов", executor_done_orders, tag="`")}',
		message=message_id,
		return_message_id=False,
		reply_markup=reply_markup
	)
	
	await select_supplier_segment(context, user=user)
	await show_total_detail_rating(context, user=user)

	return inline_message

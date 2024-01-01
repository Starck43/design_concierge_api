from typing import Optional

from api.models import Country, Region, UserGroup, Category, User
from api.utils import read_json_data


def import_regions_data(filename: str) -> Optional[int]:
	data = read_json_data(filename)
	if data is None:
		return None

	count = 0
	country_code = data[0].get('country_code', 'ru')
	try:
		country = Country.objects.get(code=country_code)
	except Country.DoesNotExist:
		return None

	for obj in data:
		name = obj.get('name')
		place_id = obj.get('place_id')
		osm_id = obj.get('osm_id')

		try:
			region = Region.objects.get(osm_id=osm_id)
			region.name = name
			region.place_id = place_id
			region.save()

		except Region.DoesNotExist:
			region = Region(
				name=name,
				country=country,
				place_id=place_id,
				osm_id=osm_id
			)
			region.save()
			count += 1

	return count


def import_categories_data(filename: str) -> Optional[int]:
	data = read_json_data(filename)
	if data is None:
		return None

	count = 0
	for obj in data:
		name = obj.get("name")
		group_code = obj.get('group')
		if group_code and name:
			group, _ = UserGroup.objects.get_or_create(code=group_code)
			category, created = Category.objects.get_or_create(name=name, defaults={'group': group})
			if created:
				count += 1
			elif category.group.code != group_code:
				category.group = group
				category.save()
	return count


def import_users_data(filename: str) -> Optional[int]:
	data = read_json_data(filename)
	if data is None:
		return None

	count = 0
	for obj in data:
		name = obj.get("name")
		category_names = obj.get("categories")
		region_osm = obj.get("region")
		address = obj.get("address", "")
		phone = obj.get("phone", "")

		user, created = User.objects.get_or_create(name=name, address=address, defaults={"phone": phone})
		if created:
			try:
				region = Region.objects.get(osm_id=region_osm)
				user.main_region = region
				user.save()
				count += 1
			except Region.DoesNotExist:
				pass

		if category_names:
			default_group = UserGroup.objects.get(code=2)
			if isinstance(category_names, str):
				category_names = [category_names]  # Convert single category name to a list

			for category_name in category_names:
				category, _ = Category.objects.get_or_create(name=category_name, defaults={"group": default_group})
				user.categories.add(category)

	return count

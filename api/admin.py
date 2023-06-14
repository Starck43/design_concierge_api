from django.contrib import admin

from bot.constants.data import categories_list, users_list
from bot.constants.regions import ALL_REGIONS

from .models import (
	UserGroup,
	Category,
	Country,
	Region,
	User,
	Designer,
	Outsourcer,
	Supplier,
	Favourite,
	Rate,
	Feedback,
)


class CategoryInline(admin.TabularInline):
	model = Category
	extra = 1
	fields = ['name', 'group', ]


class UserGroupAdmin(admin.ModelAdmin):
	inlines = [CategoryInline]


class RegionInline(admin.TabularInline):
	model = Region
	extra = 1


class FavouriteInline(admin.TabularInline):
	model = Favourite
	extra = 1
	fk_name = "designer"


class RateInline(admin.TabularInline):
	model = Rate
	extra = 1
	fk_name = "author"


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
	inlines = [CategoryInline]


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
	inlines = [RegionInline]


@admin.register(Designer)
class DesignerAdmin(admin.ModelAdmin):
	readonly_fields = ["user_id"]
	inlines = [FavouriteInline]


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
	list_display = ['name', 'country', 'in_top']
	list_display_links = ['name']

	actions = ['import_regions']

	def import_regions(self, request, queryset):
		country = Country.objects.get(code="ru")
		for data in ALL_REGIONS:
			region = Region(
				name=data['name'],
				country=country,
				place_id=data['place_id'],
				osm_id=data['osm_id']
			)
			region.save()
		self.message_user(request, "Список импортирован успешно!")

	import_regions.short_description = "Импорт списка объектов из констант"


class CategoryAdmin(admin.ModelAdmin):
	list_display = ['id', 'name', 'group']
	list_display_links = ['name']

	actions = ['import_categories']

	def import_categories(self, request, queryset):
		for data in categories_list:
			if data["id"] >=0:
				group_code = data['group']
				user_group = UserGroup.objects.get(code=group_code)
				category = Category(
					name=data['name'],
					group=user_group
				)
				category.save()
		self.message_user(request, "Список импортирован успешно!")

	import_categories.short_description = "Импорт списка объектов из констант"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	actions = ['import_users']

	def get_object(self, request, object_id, from_field=None):
		obj = super().get_object(request, object_id, from_field)
		# здесь вы можете выполнить любую логику, связанную с объектом
		return obj

	def import_users(self, request, queryset):
		for data in users_list:
			if data['id'] >= 0:
				category = Category.objects.get(pk=data['category'])
				group = UserGroup.objects.get(code=data['groups'])
				region = Region.objects.get(osm_id=115100)
				user = User(
					username=data['name'],
					address=data.get('address', ''),
					phone=data.get('phone', ''),
				)
				user.save()
				user.categories.add(category)
				user.groups.add(group)
				user.represented_regions.add(region)
		self.message_user(request, "Список импортирован успешно!")

	import_users.short_description = "Импорт списка объектов из констант"


admin.site.register(Category, CategoryAdmin)
admin.site.register(Outsourcer)
admin.site.register(Supplier)
admin.site.register(Favourite)
admin.site.register(Rate)
admin.site.register(Feedback)

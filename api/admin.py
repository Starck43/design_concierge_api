from django.contrib import admin

from bot.constants.data import categories_list, users_list
from bot.constants.regions import ALL_REGIONS
from .forms import UserForm

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
	Rating,
	Feedback,
	Order,
	File, Support,
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


class RatingInline(admin.TabularInline):
	model = Rating
	extra = 1
	fk_name = "author"


class FileInlineAdmin(admin.TabularInline):
	model = File
	extra = 1


@admin.register(UserGroup)
class UserGroupAdmin(admin.ModelAdmin):
	inlines = [CategoryInline]


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
	inlines = [RegionInline]


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
	list_display = ['name', 'country', 'in_top']
	list_display_links = ['name']

	actions = ['import_regions']

	def import_regions(self, request, queryset):
		country = Country.objects.get(code="ru")
		for data in ALL_REGIONS:
			if int(data["id"]) >= 0:
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
			if data["id"] >= 0:
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
	form = UserForm
	inlines = [FileInlineAdmin]
	search_fields = ['name', 'username']
	actions = ['import_users', 'update_ratings']
	readonly_fields = ['user_id','total_rating']
	list_display = ['id', 'user_id', 'username', 'access', 'symbol_rate']
	list_display_links = ['id', 'user_id', 'username']
	#
	# @admin.display(description='Имя пользователя')
	# def user_name(self, obj):
	# 	return obj.name or obj.username

	@admin.display(description='Рейтинг', empty_value='')
	def symbol_rate(self, obj):
		return f'⭐{obj.total_rating}' if obj.total_rating else None

	def get_object(self, request, object_id, from_field=None):
		obj = super().get_object(request, object_id, from_field)
		return obj

	def update_ratings(self, request, queryset):
		for obj in queryset:
			obj.update_total_rating()
		self.message_user(request, "Рейтинг(и) успешно обновлены!")

	update_ratings.short_description = "Обновить общий рейтинг у выбранных записей"

	def import_users(self, request, queryset):
		for data in users_list:
			if data['id'] >= 0:
				category = Category.objects.get(pk=data['category'])
				region = Region.objects.get(osm_id=115100)
				user = User(
					username=data['name'],
					address=data.get('address', ''),
					phone=data.get('phone', ''),
				)
				user.save()
				user.categories.add(category)
				user.regions.add(region)
		self.message_user(request, "Список импортирован успешно!")

	import_users.short_description = "Импорт списка объектов из констант"


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
	actions = ['delete_selected']
	list_display = ['receiver', 'author_user_name']
	list_display_links = ['receiver']

	@admin.display(description='Автор оценки')
	def author_user_name(self, obj):
		return obj.author.username

	def get_exclude(self, request, obj=None):
		exclude_fields = super().get_exclude(request, obj)
		if obj.receiver.categories.filter(group=1).exists():
			exclude_fields = [field.name for field in obj._meta.fields if field.null]
		return exclude_fields

	def delete_selected(self, request, queryset):
		for obj in queryset:
			obj.delete()
		self.message_user(request, "Рейтинг(и) были успешно удалены!")

	delete_selected.short_description = "Удалить отмеченные записи"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ['title', 'owner', 'date', 'current_status', 'approved_executor']
	list_display_links = ['title']

	@admin.display(description='Дата завершения', empty_value='не указана')
	def date(self, obj):
		return obj.expire_date

	@admin.display(description='Статус', empty_value='')
	def current_status(self, obj):
		if obj.status == 0:
			status = '🟠'
		elif obj.status == 1:
			status = '🟢'
		elif obj.status == 2:
			status = '📢'
		else:
			status = '🏁'
		return status

	@admin.display(description='Исполнитель', empty_value='')
	def approved_executor(self, obj):
		return "✅ " + obj.executor.username if obj.executor and obj.executor not in obj.responded_users.all() else ""


admin.site.register(Category, CategoryAdmin)
# admin.site.register(Outsourcer)
# admin.site.register(Supplier)
admin.site.register(Favourite)
admin.site.register(Support)
admin.site.register(Feedback)
admin.site.register(File)

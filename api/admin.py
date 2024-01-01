from django.contrib import admin

from .forms import UserForm
from .models import (
	UserGroup,
	Category,
	Country,
	Region,
	User,
	Favourite,
	Rating,
	Feedback,
	Order,
	Support,
	File, Log, Event,
)
from .logic import import_users_data, import_categories_data, import_regions_data

admin.site.site_title = 'Консьерж Сервис'
admin.site.site_header = 'Консьерж Сервис'


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
		count = import_regions_data('import/regions.json')
		if count is None:
			self.message_user(request, 'Ошибка импортирования файла!')
		else:
			self.message_user(request, f'{count} объектов импортировано успешно!')

	import_regions.short_description = "Импорт регионов из файла"


class CategoryAdmin(admin.ModelAdmin):
	list_display = ['id', 'name', 'group']
	list_display_links = ['name']
	ordering = ['group', 'name']
	actions = ['import_categories']

	def import_categories(self, request, queryset):
		count = import_categories_data('import/categories.json')
		if count is None:
			self.message_user(request, 'Ошибка импортирования файла!')
		else:
			self.message_user(request, f'{count} объектов импортировано успешно!')

	import_categories.short_description = "Импорт видов деятельности из файла"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
	form = UserForm
	inlines = [FileInlineAdmin]
	search_fields = ['name', 'contact_name', 'username']
	actions = ['import_users', 'update_ratings']
	readonly_fields = ['total_rating']
	list_display = ['id', 'user_id', 'name', 'access', 'symbol_rate']
	list_display_links = ['id', 'user_id', 'name']

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
		count = import_users_data('import/users.json')
		if count is None:
			self.message_user(request, 'Ошибка импортирования файла!')
		else:
			self.message_user(request, f'{count} объектов импортировано успешно!')

	import_users.short_description = "Импорт пользователей из файла"


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
	actions = ['delete_selected']
	list_display = ['receiver', 'author_name']
	list_display_links = ['receiver']

	@admin.display(description='Автор оценки')
	def author_name(self, obj):
		return obj.author.name or "<отсутствует>"

	def get_exclude(self, request, obj=None):
		exclude_fields = super().get_exclude(request, obj)
		# obj and obj.receiver.categories.values_list('group__code', flat=True)
		if obj and obj.receiver.categories.filter(group__code=1).exists():
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
		return "✳️ " + obj.executor.name if obj.executor and obj.executor not in obj.responded_users.all() else ""


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
	list_display = ['type', 'title', 'start_date', 'end_date']
	list_display_links = ['title']
	ordering = ['start_date']
	list_filter = ['type', 'group']
	date_hierarchy = 'start_date'
	list_per_page = 20


admin.site.register(Category, CategoryAdmin)
# admin.site.register(Outsourcer)
# admin.site.register(Supplier)
admin.site.register(Favourite)
admin.site.register(Support)
admin.site.register(Feedback)
admin.site.register(File)
admin.site.register(Log)

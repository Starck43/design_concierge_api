import os
import re
from enum import Enum

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Avg, F, FloatField, Case, When
from django.utils import timezone
from rest_framework.authtoken.models import Token

from api.logic import user_directory_path, MediaFileStorage


def phone_regex(value):
	pattern = r'^(\+?\d{1,3})?[\s-]?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}$'
	if not re.match(pattern, value):
		raise ValidationError('Неверный формат телефона')


class Group(Enum):
	DESIGNER = 0, 'Дизайнеры и архитекторы'
	OUTSOURCER = 1, 'Аутсорсеры'
	SUPPLIER = 2, 'Поставщики товаров'

	def __new__(cls, value, label):
		obj = object.__new__(cls)
		obj._value_ = value
		obj.label = label
		return obj

	def __str__(self):
		return self.label

	@classmethod
	def get_choices(cls):
		if not hasattr(cls, '_choices'):
			cls._choices = [(member.value, member.label) for member in cls]
		return cls._choices

	@classmethod
	def get_values(cls):
		if not hasattr(cls, '_values'):
			cls._values = [member.value for member in cls]
		return cls._values

	@classmethod
	def get_labels(cls):
		if not hasattr(cls, '_values'):
			cls._labels = [member.label for member in cls]
		return cls._labels

	@classmethod
	def get_label_by_value(cls, value):
		for member in cls:
			if member.value == value:
				return member.label
		raise ValueError(f"Число {value} не найдено в {cls.__name__} значении")


class UserGroup(models.Model):
	code = models.SmallIntegerField('Код группы', choices=Group.get_choices(), unique=True)

	class Meta:
		verbose_name = 'Группа'
		verbose_name_plural = 'Группы пользователей'

	def __str__(self):
		return Group.get_label_by_value(self.code)


class Country(models.Model):
	name = models.CharField('Название страны', max_length=20, unique=True)
	code = models.CharField('Буквенный код страны', max_length=2, unique=True)
	numeric_code = models.SmallIntegerField('Числовой 3-х значный код страны', unique=True)

	class Meta:
		verbose_name = 'Страна'
		verbose_name_plural = 'Страны'

	def __str__(self):
		return self.name


class Region(models.Model):
	name = models.CharField('Название региона', max_length=45, unique=True)
	country = models.ForeignKey(
		Country, verbose_name='Страна', to_field='code', on_delete=models.SET_NULL, related_name='regions', null=True
	)
	osm_id = models.IntegerField('OSM код', unique=True, blank=True)
	place_id = models.IntegerField('Код местности', unique=True, blank=True)
	in_top = models.BooleanField('В списке рекомендуемых', null=True, blank=True, default=False)

	class Meta:
		verbose_name = 'Регион'
		verbose_name_plural = 'Регионы'

	def __str__(self):
		return self.name


class Category(models.Model):
	name = models.CharField('Название категории/вида деятельности', max_length=100)
	group = models.ForeignKey(
		UserGroup,
		verbose_name='Группа',
		to_field='code',
		on_delete=models.SET_NULL,
		related_name='categories',
		null=True
	)

	class Meta:
		verbose_name = 'Вид деятельности'
		verbose_name_plural = 'Виды деятельности'

	def __str__(self):
		return f'{self.name}'


class User(models.Model):
	ACCESS_CHOICES = ((-2, 'Недоступен'), (-1, 'Не подтвержден'), (0, 'Базовый'), (1, 'Расширенный'), (2, 'Премиум'),)
	SEGMENT_CHOICES = ((0, 'Премиум, Средний+'), (1, 'Средний'), (2, 'Средний-, Эконом'),)

	user_id = models.CharField('ID пользователя', max_length=10, blank=True)
	username = models.CharField('Имя пользователя', max_length=50)
	name = models.CharField('Полное название', max_length=150, blank=True)
	access = models.SmallIntegerField('Вид доступа', choices=ACCESS_CHOICES, default=0)
	description = models.TextField('Описание', blank=True)
	categories = models.ManyToManyField(Category, verbose_name='Виды деятельности', related_name='users')
	business_start_year = models.PositiveSmallIntegerField('Опыт работы', null=True, blank=True,
	                                                       help_text="Год начала деятельности")
	main_region = models.ForeignKey(
		Region, verbose_name='Основной регион', on_delete=models.SET_NULL, related_name='user_main_region', null=True
	)
	regions = models.ManyToManyField(Region, verbose_name='Дополнительные регионы', related_name='users_add_regions',
	                                 blank=True)
	segment = models.SmallIntegerField('Сегмент рынка', choices=SEGMENT_CHOICES, null=True, blank=True)
	address = models.CharField('Адрес', max_length=150, null=True, blank=True)
	phone = models.CharField('Телефон', validators=[phone_regex], max_length=20, blank=True)
	email = models.EmailField('Электронная почта', max_length=30, blank=True)
	socials_url = models.URLField('Ссылка на соцсеть', blank=True)
	site_url = models.URLField('Ссылка на сайт', blank=True)
	created_date = models.DateField('Дата регистрации', auto_now_add=True)

	total_rating = models.FloatField('Общий рейтинг', default=0)
	token = models.ForeignKey(Token, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_token')

	class Meta:
		verbose_name = 'Пользователь'
		verbose_name_plural = 'Пользователи'
		ordering = ('-created_date',)

	def __str__(self):
		return f'{self.name or self.username}'

	def save(self, *args, **kwargs):
		is_new = self.pk is None
		super().save(*args, **kwargs)

		if is_new:
			self.update_total_rating()

	def delete(self, *args, **kwargs):
		# Удаление прикрепленных файлов при удалении пользователя
		for file in self.files.all():
			file.delete()
		super().delete(*args, **kwargs)

	def update_total_rating(self):
		self.total_rating = self.calculate_total_rating()
		if self.segment == "":
			self.segment = None
		self.save()

	@classmethod
	def format_rating(cls, rates: dict, receiver_id: int = None, author_id: int = None):
		if not rates:
			return {}
		formatted_rates = {}
		if author_id:
			formatted_rates['author_id'] = author_id
			if receiver_id:
				formatted_rates['receiver_id'] = receiver_id

		for field_name, val in rates.items():
			field = field_name.rstrip('_avg')
			formatted_rates[field] = val

		return formatted_rates

	def calculate_total_rating(self, author: int = None):
		all_fields = [field.name for field in Rating._meta.fields if
		              isinstance(field, models.PositiveSmallIntegerField)]
		required_fields = [field.name for field in Rating._meta.fields if
		                   isinstance(field, models.PositiveSmallIntegerField) and not field.null]

		query = Q(receiver=self)
		if author:
			query &= Q(author=author)

		rating = Rating.objects.filter(query).aggregate(
			total=Case(
				When(
					receiver__categories__group=1,
					then=Avg(sum(F(field) for field in required_fields)) / len(required_fields)
				),
				When(
					receiver__categories__group=2,
					then=Avg(sum(F(field) for field in all_fields)) / len(all_fields)
				),
				output_field=FloatField(),
				default=0
			)
		)

		return round(rating.get('total', 0), 1)

	def calculate_avg_ratings(self, author: int = None):
		query = Q(receiver=self)
		if author:
			query &= Q(author=author)

		if self.categories.filter(group=1).exists():  # required fields
			fields = [
				field.name for field in Rating._meta.fields
				if isinstance(field, models.PositiveSmallIntegerField) and not field.null
			]

		elif self.categories.filter(group=2).exists():
			fields = [
				field.name for field in Rating._meta.fields
				if isinstance(field, models.PositiveSmallIntegerField)
			]

		else:
			return None

		avg_rating = Rating.objects.filter(query).aggregate(
			**{f'{field}_avg': Avg(F(field)) for field in fields}
		)

		if not avg_rating:
			return None

		no_rating = not all(val for val in avg_rating.values())
		if no_rating:
			return None

		return self.format_rating(avg_rating, receiver_id=self.pk, author_id=author)

	@property
	def voted_users_count(self):
		return self.voted_users.count()

	def get_token(self):
		if self.access > 0:
			return self.generate_token()
		return None

	def generate_token(self):
		superuser = get_user_model().objects.filter(is_superuser=True).first()
		token, created = Token.objects.update_or_create(user=superuser)
		self.token = token
		self.save()
		return token.key


class UserManager(models.Manager):
	def __init__(self, group: Group):
		super().__init__()
		self.group = group.value

	def get_queryset(self):
		return super().get_queryset().filter(categories__group=self.group)


class Designer(User):
	class Meta:
		proxy = True
		verbose_name = 'Дизайнер'
		verbose_name_plural = 'Дизайнеры'

	objects = UserManager(Group.DESIGNER)


class Outsourcer(User):
	class Meta:
		proxy = True
		verbose_name = 'Аутсорсер'
		verbose_name_plural = 'Аутсорсеры'

	objects = UserManager(Group.OUTSOURCER)


class Supplier(User):
	class Meta:
		proxy = True
		verbose_name = 'Поставщик'
		verbose_name_plural = 'Поставщики'

	objects = UserManager(Group.SUPPLIER)


class Rating(models.Model):
	author = models.ForeignKey(
		User,
		verbose_name='Автор оценки',
		on_delete=models.CASCADE,
		related_name='rated_users',
		# limit_choices_to=Q(categories__group=Group.DESIGNER.value)
	)
	receiver = models.ForeignKey(
		User,
		verbose_name='Оцениваемый',
		on_delete=models.CASCADE,
		related_name='voted_users',
		# limit_choices_to=~Q(categories__group=Group.DESIGNER.value)
	)
	quality = models.PositiveSmallIntegerField('Качество продукции', null=True, blank=True)
	deadlines = models.PositiveSmallIntegerField('Соблюдение сроков')
	sales_service_quality = models.PositiveSmallIntegerField('Качество сервиса при продаже')
	service_delivery_quality = models.PositiveSmallIntegerField(
		'Качество сервиса при выполнении работ',
		help_text='(если это предусмотрено характером продажи или услуги)',
		null=True,
		blank=True,
	)
	designer_program_quality = models.PositiveSmallIntegerField('Работа с дизайнерами', null=True, blank=True)
	location = models.PositiveSmallIntegerField('Удобство расположения', null=True, blank=True)
	modified_date = models.DateField('Дата последнего обновления', auto_now=True)

	class Meta:
		verbose_name = 'Рейтинг'
		verbose_name_plural = 'Рейтинг'

	def __str__(self):
		return f'Рейтинг для поставщика {self.receiver}'

	def delete(self, *args, **kwargs):
		receiver = self.receiver
		super().delete(*args, **kwargs)
		receiver.update_total_rating()

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		self.receiver.update_total_rating()

	@property
	def avg_rating(self):
		if self.receiver.categories.filter(group=1).exists(): # required fields
			fields = [
				field.name for field in self._meta.fields
				if isinstance(field, models.PositiveSmallIntegerField) and not field.null
			]

		else:
			fields = [
				field.name for field in self._meta.fields
				if isinstance(field, models.PositiveSmallIntegerField)
			]

		avg_values = [value for value in (getattr(self, field, None) for field in fields) if value is not None]
		return round(sum(avg_values) / len(avg_values), 1) if avg_values else None


class Favourite(models.Model):
	designer = models.ForeignKey(
		User, verbose_name='Дизайнер/архитектор', on_delete=models.CASCADE, related_name='favourites'
	)
	supplier = models.ForeignKey(
		User,
		verbose_name='Избранный поставщик',
		on_delete=models.CASCADE,
		limit_choices_to=~Q(categories__group=Group.DESIGNER.value)
	)

	class Meta:
		verbose_name = 'Избранное'
		verbose_name_plural = 'Избранные поставщики'
		unique_together = ['designer', 'supplier']

	def __str__(self):
		return f'{self.supplier}'


class Feedback(models.Model):
	text = models.TextField('Отзыв от дизайнера')
	author = models.ForeignKey(User, verbose_name='Автор', on_delete=models.CASCADE, related_name='feedback_receivers')
	receiver = models.ForeignKey(
		User,
		verbose_name='Получатель',
		on_delete=models.CASCADE,
		related_name='feedback_authors',
		limit_choices_to=~Q(categories__group=Group.DESIGNER.value),
	)
	created_date = models.DateField('Дата создания отзыва', auto_now_add=True)

	class Meta:
		verbose_name = 'Отзыв о поставщике'
		verbose_name_plural = 'Отзывы'

	def __str__(self):
		return f'Отзыв о поставщике {self.receiver}'


class Order(models.Model):
	STATUS_CHOICES = (
		(0, 'приостановлен'), (1, 'активный'), (2, 'этап сдачи'), (3, 'завершен'), (4, 'досрочно завершен'),)
	owner = models.ForeignKey(
		User,
		verbose_name='Автор заказа',
		on_delete=models.CASCADE,
		related_name='orders',
		limit_choices_to=Q(categories__group=Group.DESIGNER.value),
	)
	title = models.CharField('Название заказа', max_length=100)
	description = models.TextField('Описание заказа', blank=True)
	categories = models.ManyToManyField(
		Category,
		verbose_name='Категории',
		related_name='categories_orders',
		limit_choices_to=Q(group=Group.OUTSOURCER.value),
	)
	responded_users = models.ManyToManyField(
		User,
		verbose_name='Откликнувшиеся на заказ',
		related_name='user_order',
		limit_choices_to=Q(categories__group=Group.OUTSOURCER.value),
		blank=True,
	)
	executor = models.ForeignKey(
		User,
		verbose_name='Выбран в качестве исполнителя',
		on_delete=models.SET_NULL,
		related_name='executor_order',
		limit_choices_to=Q(categories__group=Group.OUTSOURCER.value),
		null=True,
		blank=True
	)

	price = models.PositiveIntegerField('Стоимость услуги', null=True, blank=True)
	expire_date = models.DateField('Дата завершения', null=True, blank=True)
	status = models.PositiveSmallIntegerField('Статус заказа', choices=STATUS_CHOICES, default=1)

	class Meta:
		verbose_name = 'Заказ на бирже'
		verbose_name_plural = 'Биржа услуг'

	def add_responding_user(self, user_id):
		try:
			user_id = int(user_id)
			self.responded_users.add(user_id)
		except ValueError:
			pass

	def remove_responding_user(self, user_id):
		try:
			user_id = int(user_id)
			self.responded_users.remove(user_id)
		except ValueError:
			pass

	def __str__(self):
		return self.title


class Support(models.Model):
	user = models.ForeignKey(User, verbose_name='Автор', on_delete=models.CASCADE, related_name='asked_users')
	message_id = models.IntegerField('ID сообщения', blank=True)
	question = models.TextField('Вопрос', blank=True)
	answer = models.TextField('Ответ', blank=True)
	created_date = models.DateTimeField('Дата регистрации', auto_now=True)
	replied_date = models.DateTimeField('Дата ответа', blank=True, null=True, editable=False)

	class Meta:
		verbose_name = 'Вопрос в техподдержку'
		verbose_name_plural = 'Вопросы в техподдержку'

	def __str__(self):
		return self.user.username


class File(models.Model):
	user = models.ForeignKey(User, verbose_name='Автор', on_delete=models.CASCADE, related_name='files')
	file = models.FileField(upload_to=user_directory_path, storage=MediaFileStorage(), blank=True)

	class Meta:
		verbose_name = 'Файл'
		verbose_name_plural = 'Файлы пользователей'

	def delete(self, *args, **kwargs):
		# Удаление файла с диска
		if self.file:
			file_path = self.file.path
			if os.path.exists(file_path):
				os.remove(file_path)
		super().delete(*args, **kwargs)

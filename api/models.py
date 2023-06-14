import re
from enum import Enum

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.crypto import get_random_string

from rest_framework.authtoken.models import Token


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
	code = models.SmallIntegerField('Код группы', unique=True, choices=Group.get_choices())

	class Meta:
		verbose_name = 'Группа'
		verbose_name_plural = 'Группы пользователей'

	def __str__(self):
		return Group.get_label_by_value(self.code)


class Category(models.Model):
	name = models.CharField('Название категории/вида деятельности', max_length=100)
	group = models.ForeignKey(
		UserGroup, verbose_name='Группа', on_delete=models.SET_NULL, related_name='categories', null=True
	)

	class Meta:
		verbose_name = 'Вид деятельности'
		verbose_name_plural = 'Виды деятельности'

	def __str__(self):
		return f'{self.name}'


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


class User(models.Model):
	ACCESS_CHOICES = ((0, 'Базовый'), (1, 'Расширенный'), (-1, 'Недоступен'),)
	SEGMENT_CHOICES = (("S0", 'Премиум, Средний+'), ("S1", 'Средний'), ("S2", 'Средний-, Эконом'),)

	user_id = models.CharField('ID пользователя', max_length=10, blank=True)
	username = models.CharField('Название/имя пользователя', max_length=100)
	groups = models.ManyToManyField(UserGroup, verbose_name='Группы')
	access = models.SmallIntegerField('Вид доступа', choices=ACCESS_CHOICES, default=0)
	description = models.TextField('Описание', blank=True)
	categories = models.ManyToManyField(Category, verbose_name='Виды деятельности', blank=True)
	work_experience = models.PositiveSmallIntegerField('Сколько лет на рынке', null=True, blank=True)
	main_region = models.ForeignKey(
		Region, verbose_name='Рабочий регион', on_delete=models.SET_NULL, related_name='users', null=True, blank=True
	)
	represented_regions = models.ManyToManyField(Region, verbose_name='Регионы представления', blank=True)
	segment = models.CharField('Сегмент рынка', max_length=2, choices=SEGMENT_CHOICES, blank=True)
	address = models.CharField('Адрес', max_length=150, null=True, blank=True)
	phone = models.CharField('Контактный телефон', validators=[phone_regex], max_length=20, blank=True)
	email = models.EmailField('Электронная почта', max_length=30, blank=True)
	socials_url = models.URLField('Ссылка на соцсеть', blank=True)
	site_url = models.URLField('Ссылка на сайт', blank=True)
	created_date = models.DateField('Дата регистрации пользователя', auto_now_add=True)

	token = models.ForeignKey(Token, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_token')

	class Meta:
		verbose_name = 'Пользователь'
		verbose_name_plural = 'Пользователи'

	def __str__(self):
		return f'{self.username} ({self.user_id})'

	def get_token(self):
		if self.access > 0:
			return self.generate_token()
		return None

	def generate_token(self, days: int = 7):
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
		return super().get_queryset().filter(groups__code=self.group)


class Designer(User):
	class Meta:
		proxy = True
		verbose_name = 'Дизайнер'
		verbose_name_plural = 'Дизайнеры'

	objects = UserManager(Group.DESIGNER)

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		user_group, created = UserGroup.objects.get_or_create(code=Group.DESIGNER.value)
		self.groups.add(user_group)


class Outsourcer(User):
	class Meta:
		proxy = True
		verbose_name = 'Аутсорсер'
		verbose_name_plural = 'Аутсорсеры'

	objects = UserManager(Group.OUTSOURCER)

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		user_group, created = UserGroup.objects.get_or_create(code=Group.OUTSOURCER.value)
		self.groups.add(user_group)


class Supplier(User):
	class Meta:
		proxy = True
		verbose_name = 'Поставщик'
		verbose_name_plural = 'Поставщики'

	objects = UserManager(Group.SUPPLIER)

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		user_group, created = UserGroup.objects.get_or_create(code=Group.SUPPLIER.value)
		self.groups.add(user_group)


class Favourite(models.Model):
	designer = models.ForeignKey(
		Designer, verbose_name='Дизайнер/архитектор', on_delete=models.CASCADE, related_name='favourites'
	)
	supplier = models.ForeignKey(
		User,
		verbose_name='Избранный поставщик',
		on_delete=models.CASCADE,
		limit_choices_to=~Q(groups__code=Group.DESIGNER.value)
	)

	class Meta:
		verbose_name = 'Избранное'
		verbose_name_plural = 'Избранные поставщики'

	def __str__(self):
		return f'{self.supplier}'


class Rate(models.Model):
	author = models.ForeignKey(Designer, verbose_name='Автор', on_delete=models.CASCADE, related_name='left_rate')
	receiver = models.ForeignKey(
		User,
		verbose_name='Получатель',
		on_delete=models.CASCADE,
		related_name='received_rate',
		limit_choices_to=~Q(groups__code=Group.DESIGNER.value),
	)
	quality = models.PositiveSmallIntegerField('Качество продукции', blank=True)
	deadlines = models.PositiveSmallIntegerField('Соблюдение сроков')
	sales_service_quality = models.PositiveSmallIntegerField('Качество сервиса при продаже товаров/услуг')
	service_delivery_quality = models.PositiveSmallIntegerField(
		'Качество сервиса при установке/выполнении работ',
		help_text='(если это предусмотрено характером продажи или услуги)',
		blank=True,
	)
	designer_program_quality = models.PositiveSmallIntegerField('Программа работы с дизайнерами', blank=True)
	location = models.PositiveSmallIntegerField('Месторасположение', blank=True)
	modified_date = models.DateField('Дата последнего обновления', auto_now=True)

	class Meta:
		verbose_name = 'Рейтинг'
		verbose_name_plural = 'Рейтинг'

	def __str__(self):
		return f'Рейтинг для поставщика {self.receiver}'


class Feedback(models.Model):
	text = models.TextField('Отзыв от дизайнера')
	author = models.ForeignKey(Designer, verbose_name='Автор', on_delete=models.CASCADE, related_name='left_feedback')
	receiver = models.ForeignKey(
		User,
		verbose_name='Получатель',
		on_delete=models.CASCADE,
		related_name='received_feedback',
		limit_choices_to=~Q(groups__code=Group.DESIGNER.value),
	)
	created_date = models.DateField('Дата создания отзыва', auto_now_add=True)

	class Meta:
		verbose_name = 'Отзыв о поставщике'
		verbose_name_plural = 'Отзывы'

	def __str__(self):
		return f'Отзыв о поставщике {self.receiver}'

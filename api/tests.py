import datetime
import json

from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError

from api.models import (
	phone_regex,
	Group,
	UserGroup,
	Category,
	Region,
	User,
	Designer,
	Outsourcer,
	Supplier
)

res_data = {
	'access': 0,
	'address': None,
	'categories': [],
	'created_date': '2023-06-18',
	'description': '',
	'email': '',
	'groups': [0],
	'id': 1,
	'main_region': None,
	'phone': '',
	'represented_regions': [],
	'segment': '',
	'site_url': '',
	'socials_url': '',
	'token': None,
	'user_id': '596846298',
	'username': 'Starck',
	'business_start_year': None
}


class FetchUserListTestCase(TestCase):
	def setUp(self):
		self.client = Client()
		self.url = reverse('user-list', args=[])

	def test_get_user_200(self):
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, 200)


class FetchUserDetailTestCase(TestCase):
	def setUp(self):
		self.client = Client()
		self.user_id = '596846298'
		self.url = reverse('user-detail', args=[self.user_id])

	def test_get_unknown_user(self):
		response = self.client.get(self.url)
		self.assertEqual(response.status_code, 404)

	def test_create_user(self):
		self.url = reverse('user-create', args=[])
		self.data = {
			"user_id": self.user_id,
			"username": "Starck",
			"groups": [0]
		}
		res_data["created_date"] = datetime.date.today().strftime('%Y-%m-%d')

		response = self.client.post(
			self.url,
			data=json.dumps(self.data),
			content_type='application/json'
		)
		self.assertEqual(response.status_code, 201)
		self.assertEqual(
			response.json(),
			res_data
		)

class PhoneRegexTestCase(TestCase):
	def test_valid_phone_numbers(self):
		valid_numbers = [
			'+7(123)456-78-90',
			'8 (123) 456-78-90',
			'123-456-78-90',
			'123 456 78 90',
			'(123) 456-78-90',
		]
		for number in valid_numbers:
			try:
				phone_regex(number)
			except ValidationError:
				self.fail(f'ValidationError raised for valid phone number: {number}')

	def test_invalid_phone_numbers(self):
		invalid_numbers = [
			'1234567890',
			'123 456 78 9',
			'123-456-78',
			'12 34 56 78 90',
			'123456789012345',
		]
		for number in invalid_numbers:
			with self.assertRaises(ValidationError):
				phone_regex(number)


class GroupTestCase(TestCase):
	def test_group_choices(self):
		choices = Group.get_choices()
		self.assertEqual(len(choices), 3)
		self.assertIn((Group.DESIGNER.value, 'Дизайнеры и архитекторы'), choices)
		self.assertIn((Group.OUTSOURCER.value, 'Аутсорсеры'), choices)
		self.assertIn((Group.SUPPLIER.value, 'Поставщики товаров'), choices)

	def test_group_values(self):
		values = Group.get_values()
		self.assertEqual(len(values), 3)
		self.assertIn(Group.DESIGNER.value, values)
		self.assertIn(Group.OUTSOURCER.value, values)
		self.assertIn(Group.SUPPLIER.value, values)

	def test_group_labels(self):
		labels = Group.get_labels()
		self.assertEqual(len(labels), 3)
		self.assertIn('Дизайнеры и архитекторы', labels)
		self.assertIn('Аутсорсеры', labels)
		self.assertIn('Поставщики товаров', labels)


class UserTestCase(TestCase):
	def setUp(self):
		self.group = UserGroup.objects.create(name=Group.DESIGNER.value)
		self.category = Category.objects.create(name='Test Category', group=Group.DESIGNER.value)
		self.region = Region.objects.create(name='Test Region', country=None, place_id=1, osm_id=1)

	def test_user_creation(self):
		user = User.objects.create(
			name='Test User',
			business_start_year=5,
			main_region=self.region,
		)
		user.groups.add(self.group)
		user.categories.add(self.category)
		self.assertEqual(user.name, 'Test User')

		self.assertEqual(user.business_start_year, 5)
		self.assertEqual(user.main_region, self.region)
		self.assertIn(self.group, user.groups.all())
		self.assertIn(self.category, user.categories.all())


def test_designer_creation(self):
	designer = Designer.objects.create(
		name='Test Designer',
		business_start_year=5,
		main_region=self.region,
	)
	designer.groups.add(self.group)
	designer.categories.add(self.category)
	self.assertEqual(designer.name, 'Test Designer')

	self.assertEqual(designer.business_start_year, 5)
	self.assertEqual(designer.main_region, self.region)
	self.assertIn(self.group, designer.groups.all())
	self.assertIn(self.category, designer.categories.all())


def test_outsourcer_creation(self):
	outsourcer = Outsourcer.objects.create(
		name='Test Outsourcer',
		business_start_year=5,
		main_region=self.region,
	)
	outsourcer.groups.add(self.group)
	outsourcer.categories.add(self.category)
	self.assertEqual(outsourcer.name, 'Test Outsourcer')

	self.assertEqual(outsourcer.business_start_year, 5)
	self.assertEqual(outsourcer.main_region, self.region)
	self.assertIn(self.group, outsourcer.groups.all())
	self.assertIn(self.category, outsourcer.categories.all())


def test_supplier_creation(self):
	supplier = Supplier.objects.create(
		name='Test Supplier',
		business_start_year=5,
		main_region=self.region,
	)
	supplier.groups.add(self.group)
	supplier.categories.add(self.category)
	self.assertEqual(supplier.name, 'Test Supplier')

	self.assertEqual(supplier.business_start_year, 5)
	self.assertEqual(supplier.main_region, self.region)
	self.assertIn(self.group, supplier.groups.all())
	self.assertIn(self.category, supplier.categories.all())

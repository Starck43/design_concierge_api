import datetime
import json

from django.test import TestCase, Client
from django.urls import reverse

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
	'work_experience': None
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

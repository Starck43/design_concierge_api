from django.core import exceptions
from django.db import models
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Category, User, Rate, Designer, Region
from .serializers import (CategorySerializer, UserSerializer, RateSerializer, RegionSerializer)


class RegionList(generics.ListAPIView):
	queryset = Region.objects.all()
	serializer_class = RegionSerializer


class RegionDetail(generics.RetrieveAPIView):
	queryset = Region.objects.all()
	serializer_class = RegionSerializer


class CategoryList(generics.ListAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer

	def get_queryset(self):
		queryset = super().get_queryset()
		group = self.request.query_params.get('group')

		if group:
			groups = list(map(int, group.split(',')))
			queryset = queryset.filter(group__in=groups)

		return queryset


class CategoryDetail(generics.RetrieveAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer


class UserList(generics.ListAPIView):
	queryset = User.objects.all()
	serializer_class = UserSerializer

	def get_queryset(self):
		queryset = super().get_queryset()
		category = self.request.query_params.get('category')
		group = self.request.query_params.get('group')

		if category:
			queryset = queryset.filter(categories__id=category)

		if group:
			groups = list(map(int, group.split(',')))
			queryset = queryset.filter(groups__code__in=groups)

		return queryset


class UserDetail(APIView):
	lookup_field = 'user_id'

	def get_user(self, user_id):
		try:
			user = User.objects.get(user_id=user_id)
			print(user)
			return user
		except User.DoesNotExist:
			return Response(status=status.HTTP_404_NOT_FOUND)
		except Exception:
			return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

	def get(self, request, user_id=None):
		user = self.get_user(user_id)
		if not isinstance(user, User):
			return user
		serializer = UserSerializer(user)
		token = user.get_token()
		headers = {'token': token}
		return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)

	def post(self, request):
		if not request.path.endswith('/create/'):
			return Response(status=status.HTTP_400_BAD_REQUEST)

		serializer = UserSerializer(data=request.data)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data, status=status.HTTP_201_CREATED)

		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	def patch(self, request, user_id):
		user = self.get_user(user_id)
		if not isinstance(user, User):
			return user
		serializer = UserSerializer(user, data=request.data, partial=True)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data, status=status.HTTP_200_OK)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	def delete(self, request, user_id):
		user = self.get_user(user_id)
		if not isinstance(user, User):
			return user
		user.delete()
		return Response(status=status.HTTP_204_NO_CONTENT)
	

class UpdateUsersRates(APIView):
	# Использовать вместе с токеном в заголовке запроса
	# permission_classes = (IsAuthenticated,)

	def post(self, request, user_id):
		designer = get_object_or_404(Designer, user_id=user_id)
		rates = request.data
		avg_rates = []

		for rate in rates:
			rate['author'] = designer.id
			rate['receiver'] = rate.get('id', None)

			if rate['receiver'] is not None:
				# Если рейтинг для этого автора и получателя уже существует, то обновим его
				try:
					rating = Rate.objects.get(author=rate['author'], receiver_id=rate['receiver'])
					serializer = RateSerializer(rating, data=rate, partial=True)
				except Rate.DoesNotExist:
					serializer = RateSerializer(data=rate, partial=True)
			else:
				serializer = RateSerializer(data=rate, partial=True)

			try:
				serializer.is_valid(raise_exception=True)
			except ValidationError as e:
				return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
			rating = serializer.save()

			# Получим обновленный рейтинг и вернем его ответом
			avg_rates.append({
				"id": rate['receiver'],
				"rating": rating.calculate_average_rate(),
			})
		return Response(data=avg_rates, status=status.HTTP_200_OK)


# Получение списка вопросов для выставления рейтинга
class RateQuestionView(APIView):
	def get(self, request):
		try:
			fields = Rate._meta.get_fields()
		except exceptions:
			return Response([])

		all_fields_dict = {}
		required_fields_dict = {}

		for field in fields:
			if isinstance(field, models.PositiveSmallIntegerField):
				field_name = field.name
				field_verbose_name = field.verbose_name
				field_blank = field.blank

				all_fields_dict[field_name] = field_verbose_name

				if not field_blank:
					required_fields_dict[field_name] = field_verbose_name

		return Response([
			required_fields_dict,
			all_fields_dict,
		])

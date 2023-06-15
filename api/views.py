from django.core import exceptions
from django.db import models
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, User, Rate, Designer
from .serializers import (CategorySerializer, UserSerializer, RateSerializer)


class CategoryList(generics.ListCreateAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer


class CategoryDetail(generics.RetrieveUpdateDestroyAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer


class UserList(generics.ListCreateAPIView):
	# permission_classes = (IsAuthenticated,)
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

	def post(self, request, *args, **kwargs):
		new_user = request.query_params.get('new_user', False)  # Получаем значение параметра url 'new_user/' из запроса
		# new_user = request.data.get('new_user', False)  # Получаем значение параметра '?new_user' из запроса
		serializer = UserSerializer(data=request.data)
		if serializer.is_valid():
			user = serializer.save()

			if new_user:
				token = user.get_token()
				data = {
					'user': UserSerializer(user).data,
					'token': token
				}
			else:
				data = {
					'user': UserSerializer(user).data
				}
			return Response(data, status=status.HTTP_201_CREATED)

		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetail(generics.RetrieveUpdateDestroyAPIView):
	queryset = User.objects.all()
	serializer_class = UserSerializer
	lookup_field = 'user_id'  # Поле, используемое для поиска пользователя

	def get(self, request, *args, **kwargs):
		response = super().get(request, *args, **kwargs)
		user = self.get_object()
		token = user.get_token()
		response.data['token'] = token
		return response


class UpdateUsersRates(APIView):
	# Использовать вместе с токеном в заголовке запроса
	# permission_classes = (IsAuthenticated,)

	def post(self, request, user_id, *args, **kwargs):
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
				return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
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

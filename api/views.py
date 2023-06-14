from django.core import exceptions
from django.db import models
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, User, Rate
from .serializers import (CategorySerializer, UserSerializer)


class CategoryList(generics.ListCreateAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer


class CategoryDetail(generics.RetrieveUpdateDestroyAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer


class UserList(generics.ListCreateAPIView):
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
		new_user = request.query_params.get('new_user', False)  # Получаем значение параметра 'new_user' из запроса
		# new_user = request.data.get('new_user', False)  # Получаем значение параметра 'new_user' из запроса
		serializer = UserSerializer(data=request.data)

		if serializer.is_valid():
			user = serializer.save()

			if new_user:
				# Создание и сохранение токена для нового пользователя
				token, created = Token.objects.get_or_create(user=user)
				data = {
					'user': UserSerializer(user).data,
					'token': token.key
				}
			else:
				# Возвращаем данные пользователя без токена
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

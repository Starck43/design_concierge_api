import requests
from django.core import exceptions
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q, ManyToOneRel, ManyToManyRel, OneToOneRel
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Category, User, Rate, Region, File
from .serializers import (
	CategorySerializer, UserListSerializer, RateSerializer, RegionSerializer, UserDetailSerializer, FileUploadSerializer
)


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
		groups = self.request.query_params.getlist('group')
		related_users = self.request.query_params.get('related_users')
		region = self.request.query_params.get('region')

		# Check if any of the parameters are present
		if groups or related_users or region:
			# Create an empty Q object to hold the filters
			q = Q()

			if groups:
				groups = list(map(int, groups))
				q &= Q(group__in=groups)

			if related_users:
				users_filter = Q(users__isnull=False)
				if region:
					users_filter &= Q(user_region_id=region)
				q &= users_filter

			# Apply the filters to the queryset
			queryset = queryset.filter(q).distinct()

		return queryset


class CategoryDetail(generics.RetrieveAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer


class UserList(generics.ListAPIView):
	queryset = User.objects.all()
	serializer_class = UserListSerializer

	def get_queryset(self):
		queryset = super().get_queryset()
		category = self.request.query_params.get('category')
		groups = self.request.query_params.getlist('group')

		if category:
			queryset = queryset.filter(categories__id=category)

		if groups:
			groups = list(map(int, groups))
			queryset = queryset.filter(categories__group__in=groups)

		return queryset.order_by('-total_rate', 'username')

	def get(self, request, *args, **kwargs):
		id = request.query_params.get('id')
		user_id = request.query_params.get('user_id')
		is_rated = request.query_params.get('is_rated')
		params = {}
		if id:
			params['id'] = id
		if user_id:
			params['user_id'] = user_id

		if params:
			try:
				user = User.objects.get(**params)
				if is_rated:
					if Rate.objects.filter(author=user).exists():
						user.has_given_rating = True
					else:
						user.has_given_rating = False

				serializer = UserDetailSerializer(user)
				return Response(serializer.data)

			except User.DoesNotExist:
				return Response(status=status.HTTP_404_NOT_FOUND)

		else:
			return super().get(request, *args, **kwargs)

	def get_serializer_context(self):
		context = super().get_serializer_context()
		context['category'] = self.request.query_params.get('category', None)
		return context


class UserDetail(APIView):
	def get_user(self, pk):
		user_id = self.request.query_params.get('user_id')

		try:
			query = {"id": pk}
			if user_id:
				query.update({"user_id": user_id})

			return User.objects.get(**query)

		except User.DoesNotExist:
			return Response(status=status.HTTP_404_NOT_FOUND)

		except Exception:
			return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

	def get(self, request, pk=None):
		user = self.get_user(pk)
		related_designer_id = request.query_params.get('related_user')
		context = {}

		if not isinstance(user, User):
			return user

		if related_designer_id:
			try:
				# получим по id дизайнера и привяжем к пользователю рейтинг дизайнера, если он есть
				designer = User.objects.get(id=related_designer_id)
				context = {'designer': designer}
			except User.DoesNotExist:
				pass

		serializer = UserDetailSerializer(user, context=context)
		token = user.get_token()
		headers = {'token': token}
		return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)

	def post(self, request):
		if not request.path.endswith('/create/'):
			return Response(status=status.HTTP_400_BAD_REQUEST)

		serializer = UserDetailSerializer(data=request.data)

		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data, status=status.HTTP_201_CREATED)

		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	def patch(self, request, pk):
		user = self.get_user(pk)
		if not isinstance(user, User):
			return user
		serializer = UserDetailSerializer(user, data=request.data, partial=True)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data, status=status.HTTP_200_OK)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	def delete(self, request, pk):
		user = self.get_user(pk)
		if not isinstance(user, User):
			return user
		user.delete()
		return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateRates(APIView):
	# Использовать вместе с токеном в заголовке запроса
	# permission_classes = (IsAuthenticated,)
	lookup_field = 'user_id'

	def post(self, request, user_id):
		designer = get_object_or_404(User, user_id=user_id)
		receiver_rates = request.data
		user_ratings = []

		for rate in receiver_rates:
			receiver_id = rate.pop("receiver_id", None)
			# Если пользователь выставляет оценки самому себе, то вернем код 304
			if receiver_id == designer.id:
				return Response(data=[], status=status.HTTP_304_NOT_MODIFIED)

			try:
				# Если рейтинг для этого автора и получателя уже существует, то обновим его
				rating = Rate.objects.get(author_id=designer.id, receiver_id=receiver_id)
				serializer = RateSerializer(rating, data=rate, partial=True)
			except Rate.DoesNotExist:
				rate.update({"author": designer.id, "receiver": receiver_id})
				serializer = RateSerializer(data=rate, partial=True)

			try:
				serializer.is_valid(raise_exception=True)
			except ValidationError as e:
				return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
			rating = serializer.save()

			# Получим обновленный рейтинг и вернем его ответом
			user_ratings.append({
				"id": receiver_id,
				"username": rating.receiver.username,
				"author_rate": rating.calculate_average_rate(),
				"total_rate": rating.receiver.total_rate
			})
		return Response(data=user_ratings, status=status.HTTP_201_CREATED)


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


class UserFieldNamesView(APIView):
	""" Чтение названий полей модели User"""

	def get(self, request, *args, **kwargs):
		excludes = ["id", "user_id", "total_rate", "created_date", "token"]
		field_names = {
			f.name: f.verbose_name or f.name for f in User._meta.get_fields()
			if f.name not in excludes and not isinstance(f, (ManyToOneRel, ManyToManyRel, OneToOneRel))
		}
		return Response(field_names)


class FileUploadView(APIView):
	lookup_field = 'user_id'

	def post(self, request, user_id):
		user = get_object_or_404(User, user_id=user_id)
		serializer = FileUploadSerializer(data=request.data)
		if serializer.is_valid():
			files = serializer.validated_data['files']
			successfully_saved_files = []

			for url in files:
				response = requests.get(url)
				if response.status_code == 200:
					url = url.split('/')[-1]
					file_obj = File(user=user)
					file_obj.file.save(url, ContentFile(response.content))
					file_obj.save()
					successfully_saved_files.append(url)

			if len(successfully_saved_files) == len(files):
				message = 'Все файлы были получены успешно!'
			elif len(successfully_saved_files) > 0:
				message = 'Только часть файлов была получена!'
			else:
				message = 'Файлы не были получены!'

			return Response({'message': message, 'saved_files': successfully_saved_files}, status=201)

		else:
			return Response(serializer.errors, status=400)

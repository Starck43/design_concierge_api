import itertools
from collections import OrderedDict
from datetime import date, datetime, timedelta
from functools import cached_property

import requests
from django.core import exceptions
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q, ManyToOneRel, ManyToManyRel, OneToOneRel, F, Count, Field, Max
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import (
	get_object_or_404, ListAPIView, RetrieveUpdateDestroyAPIView, RetrieveAPIView, ListCreateAPIView
)
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import Category, User, Rating, Region, File, Order, Favourite, Group, Support, Message, Log, UserGroup, \
	Event
from bot.utils import convert_date
from .logic import get_date_range
from .parser import load_events
from .serializers import (
	CategorySerializer, UserListSerializer, RatingSerializer, RegionSerializer, UserDetailSerializer,
	FileUploadSerializer, OrderSerializer, FavouriteSerializer, SupportSerializer, MessageSerializer, LogSerializer,
	EventSerializer
)


class RegionList(ListAPIView):
	queryset = Region.objects.all()
	serializer_class = RegionSerializer


class RegionDetail(RetrieveAPIView):
	queryset = Region.objects.all()
	serializer_class = RegionSerializer


class CategoryList(ListAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer

	def get_queryset(self):
		queryset = super().get_queryset()
		groups = self.request.query_params.getlist('groups')
		exclude_empty = self.request.query_params.get('exclude_empty')
		regions = self.request.query_params.getlist('regions')

		queryset = queryset.annotate(user_count=Count('users'))

		if groups:
			queryset = queryset.filter(group__in=groups)

		if exclude_empty and not str(exclude_empty).lower() == "false":
			queryset = queryset.filter(users__isnull=False)

		if regions:
			queryset = queryset.filter(users__main_region_id__in=regions)

		return queryset.distinct()


class CategoryDetail(RetrieveAPIView):
	queryset = Category.objects.all()
	serializer_class = CategorySerializer


class UserList(ListAPIView):
	queryset = User.objects.filter(access__gt=-1)
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

		return queryset.order_by('-total_rating', 'name')

	def get(self, request, *args, **kwargs):
		offset = request.query_params.get('offset', 0)
		limit = request.query_params.get('limit')
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
					if Rating.objects.filter(author=user).exists():
						user.is_rated = True
					else:
						user.is_rated = False

				serializer = UserDetailSerializer(user)
				return Response(serializer.data)

			except User.DoesNotExist:
				return Response(status=status.HTTP_404_NOT_FOUND)

		else:
			queryset = self.get_queryset()

			if limit:
				offset = int(offset)
				limit = int(limit)
				queryset = queryset[offset:offset+limit]

			serializer = self.get_serializer(queryset, many=True)
			return Response(serializer.data)

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
		related_user_id = request.query_params.get('related_user')
		with_details = request.query_params.get('with_details')
		context = {}

		if not isinstance(user, User):
			return user

		token = user.get_token()
		headers = {'token': token}

		if not with_details or (with_details and with_details.lower() == 'false'):
			data = {
				"id": user.id,
				"user_id": user.user_id,
				"name": user.name,
				"contact_name": user.contact_name,
				"username": user.username or "",
				"categories": user.categories.values_list("id", flat=True),
				"groups": user.categories.values_list('group', flat=True).distinct(),
				"total_rating": user.total_rating
			}
			return Response(data, status=status.HTTP_200_OK, headers=headers)

		if related_user_id:
			try:
				context['related_user'] = int(related_user_id)
				# проверим Избранное для дизайнера и поставщика
				Favourite.objects.get(designer=related_user_id, supplier=user)
				user.in_favourite = True

			except (ValueError, Favourite.DoesNotExist):
				user.in_favourite = False

		else:
			try:
				# добавим Избранное для пользователя, если оно есть
				supplier = Favourite.objects.filter(designer=user)
				context['favourites'] = FavouriteSerializer(supplier, many=True).data
			except Favourite.DoesNotExist:
				pass

		serializer = UserDetailSerializer(user, context=context)
		return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)

	def post(self, request, pk=None):
		if pk is None:
			if not request.path.endswith('/create/'):
				return Response(status=status.HTTP_400_BAD_REQUEST)

			serializer = UserDetailSerializer(data=request.data)
			if serializer.is_valid():
				serializer.save()
				return Response(serializer.data, status=status.HTTP_201_CREATED)

		else:
			user = self.get_user(pk)
			if not isinstance(user, User):
				return user

			serializer = UserDetailSerializer(user, data=request.data)
			if serializer.is_valid():
				serializer.save()
				return Response(serializer.data, status=status.HTTP_200_OK)

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


class RatingListView(ListAPIView):
	serializer_class = RatingSerializer

	def get_queryset(self):
		receiver_id = self.kwargs['receiver_id']
		return Rating.objects.filter(receiver_id=receiver_id)


class UpdateRatingView(APIView):
	# Использовать вместе с токеном в заголовке запроса
	# permission_classes = (IsAuthenticated,)
	lookup_field = 'user_id'

	def post(self, request, user_id):
		if not request.data:
			return Response(data=[], status=status.HTTP_304_NOT_MODIFIED)

		author = get_object_or_404(User, user_id=user_id)
		author_id = author.id
		rating_data = []
		for rate in request.data:
			receiver_id = rate.pop('receiver_id', None)
			# Если пользователь выставляет оценки самому себе, то вернем код 304
			if receiver_id == author_id:
				return Response(data=[], status=status.HTTP_304_NOT_MODIFIED)

			try:
				# Если рейтинг для этого автора и получателя уже существует, то обновим его
				rating = Rating.objects.get(author_id=author_id, receiver_id=receiver_id)
				serializer = RatingSerializer(rating, data=rate, partial=True)
			except Rating.DoesNotExist:
				rate.update({'author': author_id, 'receiver': receiver_id})
				serializer = RatingSerializer(data=rate, partial=True)

			try:
				serializer.is_valid(raise_exception=True)
			except ValidationError as e:
				return Response(str(e), status=status.HTTP_400_BAD_REQUEST)
			rating = serializer.save()

			# Получим обновленный рейтинг и вернем его ответом
			rating_data.append({
				"receiver_id": receiver_id,
				"author_id": author_id,
				"related_total_rating": rating.avg_rating
			})
		return Response(data=rating_data, status=status.HTTP_200_OK)


# Чтение Избранного для дизайнера
class FavouriteListView(ListAPIView):
	serializer_class = FavouriteSerializer

	def get_queryset(self):
		user_id = self.kwargs.get('user_id')
		return Favourite.objects.select_related('designer').filter(designer__user_id=user_id)


class UpdateFavouriteView(APIView):
	def get_favourite(self, user_id, supplier_id):
		return get_object_or_404(Favourite, designer__user_id=user_id, supplier__id=supplier_id)

	def get(self, request, user_id, supplier_id):
		favourite = self.get_favourite(user_id, supplier_id)
		serializer = FavouriteSerializer(favourite)
		return Response(serializer.data, status=status.HTTP_200_OK)

	def post(self, request, user_id, supplier_id):
		designer = get_object_or_404(User, user_id=user_id)
		supplier = get_object_or_404(User, id=supplier_id)
		favourite, created = Favourite.objects.get_or_create(designer=designer, supplier=supplier)
		serializer = FavouriteSerializer(favourite)
		status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
		return Response(serializer.data, status=status_code)

	def delete(self, request, user_id, supplier_id):
		favourite = self.get_favourite(user_id, supplier_id)
		# supplier_name = str(favourite)
		favourite.delete()
		return Response(data={}, status=status.HTTP_204_NO_CONTENT)


# Получение списка заказов
class OrderListView(ListAPIView):
	serializer_class = OrderSerializer
	queryset = Order.objects.all()

	@cached_property
	def filtered_queryset(self):
		queryset = super().get_queryset()
		cat_ids = self.request.query_params.getlist('categories')  # категории, в которых созданы заказы
		owner_id = self.request.query_params.get('owner_id')  # id создателя заказов
		executor_id = self.request.query_params.get('executor_id')  # id исполнителя заказов
		exclude_owner_id = self.request.query_params.get('exclude_owner_id')  # id исполнителя для исключения из выборки
		order_status = self.request.query_params.getlist(
			'status')  # статус заказа: 0 - снят, 1 - активный, 2 - завершен
		actual_order = self.request.query_params.get('actual')  # флаг заказа с действующей датой или бессрочно

		q = Q()
		if cat_ids:
			# Присоединение категорий с к запросу
			q &= Q(categories__id__in=cat_ids)

		if owner_id:
			q &= Q(owner_id=owner_id)

		if executor_id:
			q &= Q(executor_id=executor_id)

		if order_status:
			if isinstance(order_status, list):
				q &= Q(status__in=order_status)
			else:
				q &= Q(status=order_status)

		if actual_order and actual_order.lower() != "false":
			q &= (Q(executor__isnull=True) | Q(executor__in=F('responded_users'))) & (
					Q(expire_date__gte=date.today()) | Q(expire_date__isnull=True)
			)

		if exclude_owner_id:
			q &= ~Q(owner=exclude_owner_id)

		return queryset.filter(q).order_by('-status', '-executor', 'expire_date')

	def get_queryset(self):
		return self.filtered_queryset.distinct()


# Обновление и удаление заказа
class OrderDetail(RetrieveUpdateDestroyAPIView):
	queryset = Order.objects.all()
	serializer_class = OrderSerializer

	def post(self, request, *args, **kwargs):
		if request.path.endswith('/create/'):
			serializer = self.get_serializer(data=request.data, partial=True)
			if serializer.is_valid():
				serializer.save()
				return Response(serializer.data, status=status.HTTP_201_CREATED)

		else:
			instance = self.get_object()
			serializer = self.get_serializer(instance, data=request.data, partial=True)
			if serializer.is_valid():
				# если заказ приостановлен или завершен, то очистим список претендентов
				if request.data.get('status') in [0, 3]:
					serializer.validated_data['responded_users'] = []

				user_id = request.query_params.get('add_user')
				if user_id:
					instance.add_responding_user(user_id)  # добавление пользователя в список претендентов

				user_id = request.query_params.get('remove_user')
				if user_id:
					instance.remove_responding_user(user_id)  # удаление пользователя из списка претендентов

				user_id = request.query_params.get('clear_executor')
				if user_id:
					instance.executor = None
					instance.remove_responding_user(
						user_id)  # удаление существующего исполнителя из списка претендентов

				serializer.save()

				return Response(serializer.data, status=status.HTTP_200_OK)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	def delete(self, request, *args, **kwargs):
		instance = self.get_object()
		self.perform_destroy(instance)
		return Response(status=status.HTTP_204_NO_CONTENT)


# Получение списка вопросов для выставления рейтинга
class RatingQuestionsView(APIView):
	def get(self, request):
		try:
			fields = Rating._meta.get_fields()
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

	@classmethod
	def get_fields(cls):
		sortable_private_fields = [f for f in User._meta.private_fields if isinstance(f, Field)]
		return sorted(itertools.chain(User._meta.concrete_fields, sortable_private_fields, User._meta.many_to_many),
		              key=lambda f: f.creation_counter)

	def get(self, request, *args, **kwargs):
		fields = [
			'name', 'contact_name', 'username', 'description', 'categories', 'main_region', 'regions',
			'business_start_year', 'segment', 'address', 'phone', 'email', 'socials_url', 'site_url'
		]
		excludes = [
			"id", "access", "user_id", "total_rating", "business_start_year", "created_date", "keywords", "token"
		]

		field_names = {
			field.name: field.verbose_name or field.name for field in self.get_fields()
			if field.name not in excludes
		}
		return Response(field_names)


class SupportListView(ListCreateAPIView):
	serializer_class = SupportSerializer

	def get_queryset(self):
		user_id = self.kwargs.get('user_id')
		if user_id:
			return Support.objects.filter(user__user_id=user_id)

		return Support.objects.all()


class SupportDetail(RetrieveUpdateDestroyAPIView):
	serializer_class = SupportSerializer

	def get_object(self):
		user_id = self.kwargs['user_id']
		message_id = self.kwargs['message_id']
		return get_object_or_404(Support, user__user_id=user_id, message_id=int(message_id))

	def post(self, request, user_id, message_id):
		user = User.objects.get(user_id=user_id)
		support, created = Support.objects.get_or_create(user=user, message_id=message_id)
		serializer = SupportSerializer(support, data=request.data, partial=True)
		if serializer.is_valid():
			if created:
				serializer.save()
				return Response(serializer.data, status=status.HTTP_201_CREATED)
			else:
				if support.answer:
					support.replied_date = timezone.now()
				serializer.update(support, serializer.validated_data)
				return Response(serializer.data, status=status.HTTP_200_OK)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
				message = 'Файлы успешно отправлены!'
			elif len(successfully_saved_files) > 0:
				message = 'Файлы частично отправлены!'
			else:
				message = 'Ошибка получения файлов!'

			return Response({'message': message, 'saved_files': successfully_saved_files}, status=201)

		else:
			return Response(serializer.errors, status=400)


class MessageListCreateView(APIView):
	lookup_field = 'order_id'

	def get(self, request, order_id):
		return Message.objects.filter(order=order_id)

	def post(self, request, *args, **kwargs):
		if request.path.endswith('/create/'):
			serializer = MessageSerializer(data=request.data, partial=True)
			if serializer.is_valid():
				serializer.save()
				return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserSearchView(APIView):
	def get(self, request):
		query_params = request.query_params

		categories = query_params.getlist('categories', [])
		total_rating = query_params.get('rating', None)
		segment = query_params.get('segment', None)
		keywords = query_params.get('keywords', None)

		_AND = Q()

		if categories:
			_AND &= Q(categories__in=categories)

		if total_rating:
			_AND &= Q(total_rating__gte=total_rating)

		if segment:
			_AND &= Q(segment=segment)

		if keywords:
			keywords_list = keywords.split(",")
			_OR = Q()
			for keyword in keywords_list:
				_OR |= (Q(name__icontains=keyword) | Q(username__icontains=keyword)) | Q(keywords__icontains=keyword)
				_OR |= Q(description__icontains=keyword) | Q(address__icontains=keyword)
				_OR |= Q(categories__name__icontains=keyword) | Q(categories__keywords__icontains=keyword)
				_OR |= Q(site_url__icontains=keyword)
			_AND &= Q(_OR)

		queryset = User.objects.filter(_AND).distinct()
		serializer = UserListSerializer(queryset, many=True)
		return Response(serializer.data)


class LogView(APIView):
	queryset = Log.objects.all()
	serializer_class = LogSerializer

	def post(self, request):
		data = request.data.copy()
		user_id = data.pop('user_id', None)
		user = User.objects.filter(user_id=user_id).first()
		if user:
			data['user'] = user.id

		serializer = LogSerializer(data=data, partial=True)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data, status=status.HTTP_201_CREATED)

		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EventListView(APIView):
	def get(self, request, **kwargs):
		group = request.query_params.get('group', None)
		month = request.query_params.get('month')
		year = request.query_params.get('year')
		events_type = int(request.query_params.get('events_type'))
		now = datetime.now()
		group_list = [int(group)] if group is not None else [0, 1]

		query = Q(type=events_type, group__code__in=group_list, excluded=False)
		events = Event.objects.filter(query)
		# Получаем дату последнего обновления событий
		last_update = events.aggregate(Max('modified_at'))['modified_at__max']
		# получаем диапазон поиска событий в таблице в зависимости от переданных параметров запроса
		start_date, end_date = get_date_range(datetime.strptime(month + "." + year, "%m.%Y") if month else None)

		# Если в дате последнего обновления сменился месяц, то выполним загрузку событий и удалим прошедшие события
		if not events or events and last_update and last_update.month != now.month:
			# Удаляем прошедшие события из базы данных
			events.filter(end_date__month__lt=now.month).delete()

			# Парсим и загружаем новые события в своей категории для группы в БД
			load_events(events_type, int(group), start_date, end_date)

		query &= Q(start_date__gte=start_date, start_date__lte=end_date)
		# Получаем события для группы
		events = Event.objects.filter(query)

		serializer = EventSerializer(events, many=True)
		return Response(serializer.data)

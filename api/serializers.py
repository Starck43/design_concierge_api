from rest_framework import serializers
from rest_framework.relations import PrimaryKeyRelatedField

from .models import (
	Category, User, UserGroup, Designer, Outsourcer, Supplier, Favourite, Rating, Feedback, Order, Support, Log, Event
)
from .models import Region, Country


class UserGroupSerializer(serializers.ModelSerializer):
	class Meta:
		model = UserGroup
		fields = ['code']


class CountrySerializer(serializers.ModelSerializer):
	class Meta:
		model = Country
		fields = ['name', 'code']


class RegionSerializer(serializers.ModelSerializer):
	country = CountrySerializer()

	class Meta:
		model = Region
		fields = ['id', 'name', 'country', 'in_top']

	def to_representation(self, instance):
		data = super().to_representation(instance)
		# Получаем объект страны и сериализуем его, используя to_field
		country = instance.country
		data['country'] = CountrySerializer(country).data
		return data


class CategorySerializer(serializers.ModelSerializer):
	user_count = serializers.IntegerField(read_only=True)

	class Meta:
		model = Category
		fields = ['id', 'name', 'group', 'user_count']


class UserListSerializer(serializers.ModelSerializer):
	groups = serializers.SerializerMethodField()

	class Meta:
		model = User
		fields = ['id', 'name', 'username', 'groups', 'total_rating']
		ordering = ['-total_rating']

	def get_groups(self, obj):
		return list(obj.categories.values_list('group', flat=True).distinct())

	def to_representation(self, instance):
		representation = super().to_representation(instance)
		representation['name'] = instance.name
		representation['username'] = instance.username or ""
		category = self.context.get('category')
		if category:
			representation['category'] = int(category)
		representation['total_rating'] = instance.total_rating if instance.total_rating else None

		return representation


class UserDetailSerializer(UserListSerializer):
	categories = CategorySerializer(many=True, read_only=True, partial=True)
	main_region = RegionSerializer(read_only=True, partial=True)
	regions = RegionSerializer(many=True, read_only=True, partial=True)
	detail_rating = serializers.SerializerMethodField(read_only=True)
	related_detail_rating = serializers.SerializerMethodField(read_only=True)
	is_rated = serializers.BooleanField(read_only=True)
	voted_users_count = serializers.SerializerMethodField()
	placed_orders_count = serializers.SerializerMethodField()
	done_orders_count = serializers.SerializerMethodField()
	executor_done_orders_count = serializers.SerializerMethodField()
	in_favourite = serializers.BooleanField(read_only=True)
	favourites = serializers.SerializerMethodField(read_only=True)

	class Meta:
		model = User
		# fields = '__all__'
		exclude = ('token',)

	def get_detail_rating(self, obj):
		return obj.calculate_avg_ratings()

	def get_related_detail_rating(self, obj):
		user_id = self.context.get('related_user')
		if not user_id:
			return None
		return obj.calculate_avg_ratings(author=user_id)

	def get_voted_users_count(self, obj):
		return obj.voted_users_count

	def get_placed_orders_count(self, obj):
		return obj.placed_orders_count

	def get_done_orders_count(self, obj):
		return obj.done_orders_count

	def get_executor_done_orders_count(self, obj):
		return obj.executor_done_orders_count

	def get_favourites(self, obj):
		return self.context.get('favourites', [])

	def to_internal_value(self, data):
		validated_data = super().to_internal_value(data)
		# Преобразование списка категорий в список объектов Category
		if data.get('categories'):
			validated_data['categories'] = Category.objects.filter(id__in=data['categories'])
		# Преобразование списка регионов в список объектов Region
		if data.get('regions'):
			validated_data['regions'] = Region.objects.filter(id__in=data['regions'])
		# Преобразование id региона в объект Region
		if data.get('main_region'):
			validated_data['main_region'] = Region.objects.get(id=data.get('main_region'))

		return validated_data

	def create(self, validated_data):
		categories = validated_data.pop('categories', [])
		regions = validated_data.pop('regions', [])
		user = User.objects.create(**validated_data)
		user.categories.set(categories)
		user.regions.set(regions)
		return user

	def update(self, instance, validated_data):
		categories = validated_data.pop('categories', None)
		regions = validated_data.pop('regions', None)  # Извлекаем regions из validated_data

		if categories:
			instance.categories.set(categories)
		if regions:
			instance.regions.set(regions)
		else:
			instance.regions.set([])

		return super().update(instance, validated_data)


class DesignerSerializer(serializers.ModelSerializer):
	class Meta:
		model = Designer
		fields = '__all__'


class OutsourcerSerializer(serializers.ModelSerializer):
	class Meta:
		model = Outsourcer
		fields = '__all__'


class SupplierSerializer(serializers.ModelSerializer):
	class Meta:
		model = Supplier
		fields = '__all__'


class FavouriteSerializer(serializers.ModelSerializer):
	class Meta:
		model = Favourite
		fields = '__all__'

	def to_representation(self, instance):
		return {
			'id': instance.supplier.id,
			'name': instance.supplier.name,
			'username': instance.supplier.username,
			'total_rating': instance.supplier.total_rating
		}


class RatingSerializer(serializers.ModelSerializer):
	# avg_rating = serializers.SerializerMethodField(read_only=True)

	class Meta:
		model = Rating
		fields = '__all__'

	def to_representation(self, instance):
		return {
			'author_id': instance.author.id,
			'author_name': str(instance.author),
			'avg_rating': instance.avg_rating
		}


class FeedbackSerializer(serializers.ModelSerializer):
	class Meta:
		model = Feedback
		fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
	categories = CategorySerializer(many=True, read_only=True)
	responded_users = UserListSerializer(many=True, read_only=False, partial=True)
	executor = PrimaryKeyRelatedField(many=False, queryset=User.objects.all())

	class Meta:
		model = Order
		fields = '__all__'

	def create(self, validated_data):
		cat_ids = self.initial_data.get('categories')
		if cat_ids:
			validated_data['categories'] = Category.objects.filter(id__in=cat_ids)
		return super().create(validated_data)

	def update(self, instance, validated_data):
		# Обработка обновления вложенных полей с read_only=False
		responded_users_data = validated_data.pop('responded_users', None)
		if responded_users_data is not None:
			# Обновление списка responded_users
			instance.responded_users.set(responded_users_data)

		# Обновление остальных полей
		return super().update(instance, validated_data)

	def to_representation(self, instance):
		order_data = super().to_representation(instance)
		order_data['executor_id'] = instance.executor.user_id if instance.executor else None
		order_data['owner_id'] = instance.owner.user_id if instance.owner else None
		order_data['owner_name'] = instance.owner.name
		executor = instance.executor

		if executor and executor not in instance.responded_users.all():
			order_data['executor_name'] = executor.name

		return order_data


class SupportSerializer(serializers.ModelSerializer):
	class Meta:
		model = Support
		fields = '__all__'

	def to_representation(self, instance):
		support_data = super().to_representation(instance)
		support_data['chat_id'] = instance.user.user_id
		support_data['name'] = instance.user.name
		support_data['is_replied'] = bool(instance.answer)

		return support_data


class MessageSerializer(serializers.ModelSerializer):
	class Meta:
		model = Support
		fields = '__all__'


class FileUploadSerializer(serializers.Serializer):
	files = serializers.ListField(child=serializers.URLField())

	def validate_files(self, value):
		for url in value:
			# Add any additional validation logic for each URL if needed
			if not url.startswith('https://api.telegram.org'):
				raise serializers.ValidationError('URL must start with https://api.telegram.org')
		return value


class LogSerializer(serializers.ModelSerializer):
	class Meta:
		model = Log
		fields = '__all__'


class EventSerializer(serializers.ModelSerializer):
	class Meta:
		model = Event
		fields = '__all__'

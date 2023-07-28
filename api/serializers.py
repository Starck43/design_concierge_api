from abc import ABC

from rest_framework import serializers

from .models import Category, User, UserGroup, Designer, Outsourcer, Supplier, Favourite, Rate, Feedback, Order
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
	class Meta:
		model = Category
		fields = ['id', 'name', 'group']


class UserListSerializer(serializers.ModelSerializer):
	groups = serializers.SerializerMethodField()

	class Meta:
		model = User
		fields = ['id', 'username', 'groups', 'total_rate']
		ordering = ['-total_rate']

	def get_groups(self, obj):
		return list(obj.categories.values_list('group', flat=True).distinct())

	def to_representation(self, instance):
		representation = super().to_representation(instance)
		representation['total_rate'] = instance.total_rate if instance.total_rate else None
		category = self.context.get('category')
		if category:
			representation['category'] = int(category)
		return representation


class UserDetailSerializer(UserListSerializer):
	categories = CategorySerializer(many=True, read_only=True, partial=True)
	regions = RegionSerializer(many=True, read_only=True, partial=True)
	main_region = RegionSerializer(many=False, read_only=True, partial=True)
	average_rating = serializers.SerializerMethodField()
	designer_rating = serializers.SerializerMethodField()
	rate_count = serializers.SerializerMethodField()
	has_given_rating = serializers.BooleanField(read_only=True)

	class Meta:
		model = User
		# fields = '__all__'
		exclude = ('token',)

	def format_rating(self, rates: dict):
		if rates is None:
			return {}
		formatted_rates = {'receiver_id': self.instance.id}
		for field_name, rate in rates.items():
			field = field_name.rstrip('_avg')
			formatted_rates[field] = rate

		return formatted_rates

	def get_average_rating(self, obj):
		avg_rating = obj.calculate_average_rating()
		return self.format_rating(avg_rating)

	def get_designer_rating(self, obj):
		designer = self.context.get('designer')
		if designer:
			designer_rating = obj.calculate_average_rating(designer)
			return self.format_rating(designer_rating)
		return {}

	def get_rate_count(self, obj):
		return obj.get_rate_count()

	def to_internal_value(self, data):
		validated_data = super().to_internal_value(data)
		# Преобразование списка категорий в список объектов Category
		validated_data['categories'] = Category.objects.filter(id__in=data.get('categories', []))
		# Преобразование списка регионов в список объектов Region
		validated_data['regions'] = Region.objects.filter(id__in=data.get('regions', []))

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
			instance.regions.set(regions)  # Используем метод set() для обновления значений regions
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


class RateSerializer(serializers.ModelSerializer):
	avg_rating = serializers.SerializerMethodField(read_only=True)

	class Meta:
		model = Rate
		fields = ['avg_rating']

	def to_representation(self, instance):
		return {
			'author_id': instance.author.id,
			'author_name': str(instance.author),
			'avg_rating': instance.calculate_average_rate()
		}


class FeedbackSerializer(serializers.ModelSerializer):
	class Meta:
		model = Feedback
		fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
	categories = CategorySerializer(many=True, read_only=True, partial=True)

	class Meta:
		model = Order
		fields = '__all__'


class FileUploadSerializer(serializers.Serializer):
	files = serializers.ListField(child=serializers.URLField())

	def validate_files(self, value):
		for url in value:
			# Add any additional validation logic for each URL if needed
			if not url.startswith('https://api.telegram.org'):
				raise serializers.ValidationError('URL must start with https://api.telegram.org')
		return value

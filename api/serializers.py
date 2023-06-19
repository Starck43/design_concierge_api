from .models import Region

from .models import Category, User, UserGroup, Designer, Outsourcer, Supplier, Favourite, Rate, Feedback
from rest_framework import serializers


class UserGroupSerializer(serializers.ModelSerializer):
	class Meta:
		model = UserGroup
		fields = ('code',)


class CategorySerializer(serializers.ModelSerializer):
	class Meta:
		model = Category
		fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
	groups = serializers.SerializerMethodField() # только на чтение для get-запросов

	represented_regions = serializers.PrimaryKeyRelatedField(
		many=True,
		queryset=Region.objects.all(),
		required=False
	)
	categories = serializers.PrimaryKeyRelatedField(
		many=True,
		queryset=Category.objects.all(),
		required=False
	)

	class Meta:
		model = User
		#fields = '__all__'
		exclude = ('token',)

	def get_groups(self, obj):
		# return list(obj.groups.values_list('code', flat=True))
		return list(obj.categories.values_list('group', flat=True).distinct())

	def to_internal_value(self, data):
		groups_data = data.pop('groups', [])
		validated_data = super().to_internal_value(data)
		if groups_data:
			groups_data = list(map(int, groups_data))
			user_groups = UserGroup.objects.filter(code__in=groups_data).values_list('code', 'id')
			user_groups_dict = dict(user_groups)
			validated_data['groups'] = [user_groups_dict[int(code)] for code in groups_data]

		return validated_data

	def create(self, validated_data):
		groups = validated_data.pop('groups', [])
		categories = validated_data.pop('categories', [])
		regions = validated_data.pop('regions', [])  # Извлекаем regions из validated_data
		user = User.objects.create(**validated_data)
		user.groups.set(groups)
		user.categories.set(categories)
		user.regions.set(regions)  # Используем метод set() для установки значений regions
		return user

	def update(self, instance, validated_data):
		groups = validated_data.pop('groups', None)
		categories = validated_data.pop('categories', None)
		regions = validated_data.pop('regions', None)  # Извлекаем regions из validated_data
		if groups is not None:
			instance.groups.set(groups)
		if categories is not None:
			instance.categories.set(categories)
		if regions is not None:
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
	class Meta:
		model = Rate
		fields = '__all__'


class FeedbackSerializer(serializers.ModelSerializer):
	class Meta:
		model = Feedback
		fields = '__all__'


class RegionSerializer(serializers.ModelSerializer):
	class Meta:
		model = Region
		fields = ('id', 'name')

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
	groups = serializers.SerializerMethodField()

	class Meta:
		model = User
		fields = '__all__'

	def get_groups(self, obj):
		return list(obj.groups.values_list('code', flat=True))



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

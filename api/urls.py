from django.urls import path
from .views import RateQuestionView, CategoryList, CategoryDetail, UserList, UserDetail, UpdateUsersRates

app_name = 'api'

urlpatterns = [
	path('categories/', CategoryList.as_view(), name='category-list'),
	path('categories/<int:pk>/', CategoryDetail.as_view(), name='category-detail'),
	path('users/', UserList.as_view(), name='user-list'),
	path('users/<str:user_id>/', UserDetail.as_view(), name='user-detail'),
	path('users/<str:user_id>/update_rates/', UpdateUsersRates.as_view(), name='update-users-rates'),

	# path('regions/', RegionList.as_view(), name='region-list'),
	path('get_rate_questions/', RateQuestionView.as_view(), name='get_rate_questions'),
]

# примеры запросов:
# categories/ - получение всех категорий
# categories/{id} - получение категории с id
# categories/?group={0,1,2} - получение всех категорий для групп 0, 1, 2

# users/ - получение всех пользователей
# users/?category={id} - получение всех пользователей для категории с id
# users/?group={0,1,2} - получение всех пользователей из группы 0, 1, 2
# users/?new_user (POST) - регистрация нового пользователя
# users/<user_id>/ (GET, PUT, PATCH) - получение, обновление или частичное обновление данных пользователя user_id
# users/<user_id>/update_rate/ (PUT, UPDATE) - обновление или частичное обновление рейтинга от пользователя user_id
# get_rate_questions/ (GET) - получение списка вопросов для рейтинга

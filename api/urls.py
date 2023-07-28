from django.urls import path
from .views import (
	RateQuestionsView, CategoryList, CategoryDetail, UserList, UserDetail, UpdateRatingView, RegionList, RegionDetail,
	UserFieldNamesView, FileUploadView, OrderListCreateView, OrderRetrieveUpdateDestroyView, RatingListView
)


urlpatterns = [
	path('regions/', RegionList.as_view(), name='region-list'),
	path('regions/<int:pk>/', RegionDetail.as_view(), name='region-detail'),
	path('categories/', CategoryList.as_view(), name='category-list'),
	path('categories/<int:pk>/', CategoryDetail.as_view(), name='category-detail'),
	path('users/', UserList.as_view(), name='user-list'),
	path('users/<int:pk>/', UserDetail.as_view(), name='user-detail'),
	path('users/create/', UserDetail.as_view(), name='user-create'),
	path('users/<str:user_id>/update_ratings/', UpdateRatingView.as_view(), name='update-user-ratings'),
	path('users/<str:user_id>/upload/', FileUploadView.as_view(), name='files-upload'),

	path('orders/', OrderListCreateView.as_view(), name='order-list'),
	path('orders/<int:pk>/', OrderRetrieveUpdateDestroyView.as_view(), name='order-detail'),

	path('rating/<int:receiver_id>/authors/', RatingListView.as_view(), name='rating-authors'),
	path('rating/questions/', RateQuestionsView.as_view(), name='rate-questions'),

	# path('regions/', RegionList.as_view(), name='region-list'),
	path('user_field_names/', UserFieldNamesView.as_view(), name='user_field_names'),
]

# примеры запросов:
# regions/ (GET) - получение всех регионов
# regions/{id} (GET) - получение региона с id

# categories/ (GET) - получение всех категорий
# categories/<id>/ (GET) - получение категории с id
# categories/?group={0,1,2} (GET) - получение всех категорий для групп 0, 1, 2
# categories/?related_users={all} (GET) - получение всех категорий для связанных пользователей
# categories/?region={region.id} (GET) - получение всех категорий для id региона

# users/ (GET) - получение всех пользователей
# users/?category={id} (GET) - получение всех пользователей для категории с id
# users/?group={0,1,2} (GET) - получение всех пользователей из группы 0, 1, 2
# users/?id={id} (GET) - получение пользователя по id (более короткий ответ)
# users/?user_id={user_id} (GET) - получение пользователя по user_id telegram (более короткий ответ)
# users/?user_id={user_id}&is_rated=true (GET) - получение пользователя по user_id telegram
# с добавлением поля has_given_rating в ответе, обозначающим, что у пользователя есть хотя бы один рейтинг
# users/create/ (POST) - регистрация нового пользователя
# users/<user_id>/update_ratings/ (POST, PATCH) - обновление или частичное обновление рейтинга от пользователя с user_id
# users/<id>/ (GET, PUT, PATCH) - получение, обновление или частичное обновление данных пользователя с id
# users/<id>/?related_user={author_id}/ (GET) - получение пользователя с добавлением данных рейтинга от author_id
# users/<user_id>/upload/ (POST) - отправка url файлов на сервер для пользователя с user_id

# orders/ (GET, POST) - получение списка заказов и создание нового заказа пользователя
# orders/<id>/ (GET, PUT, PATCH, DELETE) - получение заказа, обновление и удаление заказа пользователя с id

# rating/<int:receiver_id>/authors/ (GET) - получение списка авторов, которые выставили оценки пользователю с receiver_id
# rating/questions/ (GET) - получение списка вопросов для рейтинга

# user_field_names/ (GET) - получение имен полей данных пользователя

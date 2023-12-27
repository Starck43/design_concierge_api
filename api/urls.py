from django.urls import path

from .views import (
	RatingQuestionsView, CategoryList, CategoryDetail, UserList, UserDetail, UpdateRatingView, RegionList, RegionDetail,
	UserFieldNamesView, FileUploadView, OrderListView, OrderDetail, RatingListView, FavouriteListView,
	UpdateFavouriteView, SupportListView, SupportDetail, UserSearchView, MessageListCreateView, LogView, EventListView
)

urlpatterns = [
	path('regions/', RegionList.as_view(), name='region-list'),
	path('regions/<int:pk>/', RegionDetail.as_view(), name='region-detail'),
	path('categories/', CategoryList.as_view(), name='category-list'),
	path('categories/<int:pk>/', CategoryDetail.as_view(), name='category-detail'),
	path('users/', UserList.as_view(), name='user-list'),
	path('users/<int:pk>/', UserDetail.as_view(), name='user-detail'),
	path('users/create/', UserDetail.as_view(), name='user-create'),
	path('users/<str:user_id>/update_ratings/', UpdateRatingView.as_view(), name='user-ratings-update'),
	path('users/<str:user_id>/favourites/', FavouriteListView.as_view(), name='user-favourite-list'),
	path('users/<str:user_id>/favourites/<int:supplier_id>/', UpdateFavouriteView.as_view(),
	     name='user-favourites-update'),
	path('users/<str:user_id>/upload/', FileUploadView.as_view(), name='files-upload'),

	path('orders/', OrderListView.as_view(), name='order-list'),
	path('orders/<int:pk>/', OrderDetail.as_view(), name='order-detail'),
	path('orders/create/', OrderDetail.as_view(), name='order-create'),

	path('rating/<int:receiver_id>/authors/', RatingListView.as_view(), name='rating-authors'),
	path('rating/questions/', RatingQuestionsView.as_view(), name='rating-questions'),

	path('supports/', SupportListView.as_view()),
	path('supports/<str:user_id>/', SupportListView.as_view()),
	path('supports/<str:user_id>/<int:message_id>/', SupportDetail.as_view()),

	path('messages/<int:order_id>/', MessageListCreateView.as_view(), name='message-list-create'),
	path('messages/create/', MessageListCreateView.as_view(), name='message-list-create'),
	path('search/', UserSearchView.as_view(), name='user-search'),

	# path('regions/', RegionList.as_view(), name='region-list'),
	path('user_field_names/', UserFieldNamesView.as_view(), name='user-field-names'),

	path('logs/', LogView.as_view(), name='log'),
	path('events/', EventListView.as_view(), name='event-list'),
	path('events/<str:month>/', EventListView.as_view(), name='events-per-month'),
]

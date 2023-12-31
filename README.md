# design concierge api
API для чат бота телеграм

## endpoints

- regions/ (GET) - получение всех регионов
- regions/{id} (GET) - получение региона с id

- categories/ (GET) - получение всех категорий
- categories/<id>/ (GET) - получение категории с id
- categories/?group={0,1,2} (GET) - получение всех категорий для групп 0, 1, 2
- categories/?related_users={all} (GET) - получение всех категорий для связанных пользователей
- categories/?region={region.id} (GET) - получение всех категорий для id региона

- users/ (GET) - получение всех пользователей
- users/?offset=0&limit=10 (GET) - получение ограниченного количества пользователей со смещением в таблице
- users/?category={id} (GET) - получение всех пользователей для категории с id
- users/?group={0,1,2} (GET) - получение всех пользователей из группы 0, 1, 2
- users/?id={id} (GET) - получение пользователя по id (более короткий ответ)
- users/?user_id={user_id} (GET) - получение пользователя по user_id telegram (более короткий ответ)
- users/?user_id={user_id}&is_rated=true (GET) - получение пользователя по user_id telegram
- с добавлением поля is_rated в ответе, обозначающим, что у пользователя есть хотя бы один рейтинг
- users/create/ (POST) - регистрация нового пользователя
- users/<user_id>/update_ratings/ (POST, PATCH) - обновление или частичное обновление рейтинга от пользователя с user_id
- users/<user_id>/favourites/ (GET) - получение списка избранного для дизайнера по его user_id
- users/<user_id>/favourites/<int:supplier_id>/ (GET, POST, DELETE) - получение избранного, добавление и удаление
- users/<id>/ (GET, PUT, PATCH) - получение, обновление или частичное обновление данных пользователя с id
- users/<id>/?related_user={author_id}/ (GET) - получение пользователя с добавлением данных рейтинга от author_id
- users/<user_id>/upload/ (POST) - отправка url файлов на сервер для пользователя с user_id


- orders/ (GET, POST) - получение списка заказов и создание нового заказа пользователя
- orders/?owner_id={id}?categories={cat_id}&status={0|1|2}&actual={true}&executor_id={executor_id} (GET) -
- получение списка заказов пользователя c параметрами
- orders/<id>/?executor_id={executor_id} (GET, PUT, PATCH, DELETE) -
- получение заказа, обновление и удаление заказа пользователя с id

- rating/<int:receiver_id>/authors/ (GET) - получение списка авторов, которые выставили оценки пользователю с id
- rating/questions/ (GET) - получение списка вопросов для рейтинга

- supports/ (GET) - получение списка всех вопросов в поддержку
- supports/<user_id>/ (GET) - получение списка вопросов в поддержку от пользователя user_id
- supports/<user_id>/<message_id>/ (GET, POST, DELETE) - получение, обновление и удаление вопроса
- из поддержки по message_id и user_id

- user_field_names/ (GET) - получение имен полей данных пользователя

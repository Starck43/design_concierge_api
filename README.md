# designer concierge
Чат бот телеграм для дизайнеров

## Хранилище данных в телеграм (context)

### user_data:
    Контекст персональных данных пользователя, загружаемый при необходимости с сервера

### chat_data:
    Контекст данных, имеющий отношение к чату, 
    включая его статус, состояние диалога, сообщений, клавиатуры, геопозиция и др.

- `sections`
массив сохраненных состояний раздела
```json lines
[{
    "state": <MenuState>, // type Enum
    "query_message": <Message.text>, // type str
    "messages": [<TGMessage>], // type list
    "reply_markup": <Message.reply_markup>, // type ReplyKeyboardMarkup
    "callback": <Callback>, // type Callback
    "save_full_messages": <Boolean>, // type bool
}]
```

- `categories`
список, хранящий выбранные категории при регистрации или при анкетировании.


- `user_role`
Хранится роль текущего пользователя при работе на Бирже услуг (creator, contender, executor)


- `selected_cat`
объект с данными для текущей категории {id, name, group}


- `selected_user`
объект с подробными данными о текущем пользователе {id, name, contact_name, region, total_rating и др}


- `temp_message`
  (dict) Временные сообщения в текущей секции, которые удаляются после возврата на верхний уровень меню.


- `warn_message_id`
  (int) ID информационного сообщения. Удаляется на экране после перехода в другую секцию


- `last_message_id`
  (int) ID сообщения для обращения внутри текущей секции. Очищается при возврате назад


- `last_message_ids`
  (dict) Словарь ID сообщений для временного хранения в пределах секции. Очищается при переходе в другую секцию 


- `local_data`
    Словарь для хранения промежуточных данных в текущей секции. Очищается при возврате назад

### bot_data:
    Контекст общедоступных данных для всех пользователей бота


- `user_field_names`
Словарь названий полей модели User для изменения в профиле пользователя
```json5
{
    "name": "Полное название",
    "contact_name": "Имя контактного лица",
    "username": "Имя пользователя Telegram",
    "access": "Вид доступа",
    "description": "Описание",
    "business_start_year": "Год начала деятельности",
    "main_region": "Основной регион",
    "segment": "Сегмент рынка",
    "address": "Адрес",
    "phone": "Контактный телефон",
    "email": "Электронная почта",
    "socials_url": "Ссылка на соцсеть",
    "site_url": "Ссылка на сайт",
    "categories": "Виды деятельности",
    "regions": "Дополнительные регионы"
}
```

- `rating_questions`
список вопросов для выставления рейтинга для двух групп поставщиков: аутсорсеры и поставщики
```json5
[
    {
        "deadlines": "Соблюдение сроков",
        "sales_service_quality": "Качество сервиса при продаже товаров/услуг"
    },
    {
        "quality": "Качество продукции",
        "deadlines": "Соблюдение сроков",
        "sales_service_quality": "Качество сервиса при продаже товаров/услуг",
        "service_delivery_quality": "Качество сервиса при установке/выполнении работ",
        "designer_program_quality": "Работа с дизайнерами",
        "location": "Удобство расположения"
    }
]
```

## Для разработчиков
- [ссылка на TODO для реализации](docs/TODO.md)


## Additional
example 1: https://github.com/ohld/django-telegram-bot

import re
from datetime import datetime
from typing import Optional

from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, filters, CallbackQueryHandler, \
    ContextTypes

from bot.bot_settings import CHANNEL_ID
from bot.constants.menus import main_menu, reg_menu, questionnaire_menu
from bot.constants.messages import server_error_message, welcome_start_message, before_start_reg_message
from bot.constants.patterns import DONE_PATTERN, PROFILE_PATTERN, BACK_PATTERN, NEXT_PATTERN, CANCEL_PATTERN, SERVICES_PATTERN, \
    COOPERATION_REQUESTS_PATTERN, START_PATTERN, DESIGNER_PATTERN
from bot.conversations.registration import registration_dialog
from bot.handlers.cooperation import cooperation_requests, fetch_supplier_requests
from bot.handlers.done import done, send_error_message_callback
from bot.handlers.main import main, designer_menu_choice, activity_select_callback, supplier_select_callback
from bot.handlers.profile import profile
from bot.handlers.registration import create_registration_link
from bot.handlers.services import fetch_supplier_services, services
from bot.handlers.utils import check_user_in_channel
from bot.logger import log
from bot.utils import determine_greeting, generate_reply_keyboard, generate_inline_keyboard, update_inline_keyboard, get_org, clear_results, get_dict, fetch_user_data

from bot.states.main import MenuState
from bot.constants.messages import cansel_questionnaire
from api.models import Group

from django.contrib.sites.models import Site
import requests
import json


current_site = Site.objects.get_current()


async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    """Send a message when the command /start is issued."""
    parameters = context.args
    user = update.message.from_user
    user_data = context.user_data

    # is_user_in_channel = await check_user_in_channel(CHANNEL_ID, user.id, context.bot)
    # Получение данных с сервера
    res = await fetch_user_data(user.id)

    if res.get("error", None):
        await server_error_message(update.message, context, error_data=res)
        return MenuState.DONE_MENU

    data = res.get("data", {})
    if not data.get("user_id", None):
        await welcome_start_message(update.message)

        if parameters and parameters[0].lower() == "register":
            await before_start_reg_message(update.message)

        else:
            await create_registration_link(update, context)
        return ConversationHandler.END

    else:
        reply_text = f'{update.message.from_user.first_name}, мы уже начали диалог, если Вы помните'

    url = current_site.domain + '/api/categories/?group={1,2}'
    user_data['categories'] = json.loads(requests.get(url).text)
    user_name = user_data["details"].get("username", user.full_name)
    user_data["details"] = {
        "group": Group.DESIGNER.value,
        "username": user_name,
    }
    user_data["previous_state"] = ConversationHandler.END
    user_data["current_state"] = MenuState.QUESTIONNAIRE_CAT
    user_data["current_keyboard"] = questionnaire_menu
    await update.message.reply_text(reply_text, reply_markup=user_data["current_keyboard"])

    return await show_categories(update, context)
    # return await main(update, context)


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE, count: int = 0):
    user_data = context.user_data
    if count == len(user_data['categories']):
        user_data["previous_state"] = user_data["current_state"]
        user_data["current_state"] = MenuState.QUESTIONNAIRE_QUES
        url = current_site.domain + f'/api/get_rate_questions/'
        user_data['questions_list'] = json.loads(requests.get(url).text)
        user_data.pop('current_category', None)
        await show_questions(update, context)
    else:
        cat = user_data['categories'][count]
        user_data["current_category"] = count
        id, name = cat['id'], cat['name']
        url = current_site.domain + f'/api/users/?category={id}'
        user_data['user_in_cat'] = json.loads(requests.get(url).text)

        inline_markup = generate_inline_keyboard(user_data["user_in_cat"], callback_data="id",
                                                 item_key="username")

        await update.message.reply_text(
            f"{count+1}/{len(user_data['categories'])} " + name, reply_markup=inline_markup,
        )
    # await update.message.delete()
    return user_data["current_state"]


async def show_questions(update: Update, context: ContextTypes.DEFAULT_TYPE, count: int = 0):
    user_data = context.user_data
    if count == len(user_data['poll_users']):
        user_data["previous_state"] = user_data["current_state"]
        user_data["current_state"] = MenuState.QUESTIONNAIRE_END
        user_data.pop('current_org', None)
        reply_markup = generate_inline_keyboard(
            data=["Сохранить результат",
                  "Не сохранять"],
            callback_data=["save", "no"],
            vertical=True
        )
        user_data["current_keyboard"] = reply_markup
        new_mess = await update.message.reply_text(
            text='Опрос завершен', reply_markup=None
        )
        await new_mess.edit_reply_markup(reply_markup=reply_markup)
    else:
        user_data["current_org"] = count
        user = user_data['poll_users'][count]
        group = max(user['groups'])
        questions_group = user_data['questions_list'][group-1]
        questions_keys = questions_group.keys()
        user_data["current_keyboard"] = questionnaire_menu
        await update.message.reply_text(
            text=user['username'], reply_markup=user_data["current_keyboard"]
        )
        for count, question in enumerate(questions_keys):
            inline_markup = generate_inline_keyboard(data=['⭐️', '⭐️', '⭐️', '⭐️', '⭐️'], callback_data=[f"rate__{user['id']}__{question}__{rate}" for rate in range(1, 6)],
                                                     item_key="username")

            await update._bot.send_message(chat_id=update.message.chat_id,
                                           text=questions_group[question], reply_markup=inline_markup,
                                           )
    # await update.message.delete()
    return user_data["current_state"]


async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    """Back to level up screen."""
    user_data = context.user_data
    user_group = user_data["details"]["group"]

    previous_state = user_data.get("previous_state", None)
    if previous_state is not None:
        user_data["current_state"] = previous_state
    current_keyboard = user_data.get("current_keyboard", None)

    await update.message.delete()

    if context.error or previous_state == MenuState.MAIN_MENU or previous_state is None:
        return await main(update, context)

    if previous_state and previous_state != ConversationHandler.END:
        menu_markup = generate_reply_keyboard(current_keyboard)
        await update.message.reply_text(
            previous_state,
            reply_markup=menu_markup,
        )
    return previous_state


async def go_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:

    user_data = context.user_data
    if user_data["current_state"] == MenuState.QUESTIONNAIRE_CAT:
        return await show_categories(update, context, user_data['current_category']+1)
    else:
        return await show_questions(update, context, user_data['current_org']+1)


async def cansel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    user_data = context.user_data
    user_data["previous_state"] = user_data["current_state"]
    user_data["current_state"] = MenuState.QUESTIONNAIRE_CANSEL
    await cansel_questionnaire(update.message, buttons=["Да", "Нет"])
    return user_data["current_state"]

done_handler = MessageHandler(
    filters.TEXT & filters.Regex(
        re.compile(DONE_PATTERN, re.IGNORECASE)
    ),
    done
)

back_handler = MessageHandler(
    filters.TEXT & filters.Regex(
        re.compile(BACK_PATTERN, re.IGNORECASE)
    ),
    go_back
)
next_handler = MessageHandler(
    filters.TEXT & filters.Regex(
        re.compile(NEXT_PATTERN, re.IGNORECASE)
    ),
    go_next
)
cansel_handler = MessageHandler(
    filters.TEXT & filters.Regex(
        re.compile(CANCEL_PATTERN, re.IGNORECASE)
    ),
    cansel
)
designer_main_menu_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.Regex(
        re.compile(DESIGNER_PATTERN, re.IGNORECASE)
    ),
    designer_menu_choice
)

profile_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.Regex(
        re.compile(PROFILE_PATTERN, re.IGNORECASE)
    ),
    profile
)

services_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.Regex(
        re.compile(SERVICES_PATTERN, re.IGNORECASE)
    ),
    services
)

cooperation_requests_handler = MessageHandler(
    filters.TEXT & ~filters.COMMAND & filters.Regex(
        re.compile(COOPERATION_REQUESTS_PATTERN, re.IGNORECASE)
    ),
    cooperation_requests
)


async def go_to_main(query, user_data):
    user_data["previous_state"] = user_data["current_state"]
    user_data["current_state"] = MenuState.MAIN_MENU

    user_group = user_data["details"].get("group", Group.DESIGNER.value)
    keyboard = main_menu.get(user_group, None)
    menu_markup = generate_reply_keyboard(keyboard)

    await query.get_bot().send_message(chat_id=query.message.chat_id,
                                       text='Основной раздел:' if user_data[
                                            "previous_state"] == MenuState.MAIN_MENU else 'Выберите интересующий раздел:', reply_markup=menu_markup
                                       )

    return user_data["current_state"]


async def cansel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    button_data = query.data
    user_data = context.user_data
    await query.message.delete()
    if button_data == 'yes':
        return await go_to_main(query, user_data)
    else:

        user_data["current_state"] = user_data["previous_state"]
        return user_data["current_state"]


async def end_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    button_data = query.data

    user_data = context.user_data
    await query.message.delete()
    if button_data == 'save':
        for result in user_data['poll_results']:
            url = current_site.domain + \
                f'/api/users/{result["id"]}/update_rates/'
            requests.post(url, data=json.dumps(result))

    return await go_to_main(query, user_data)


async def organizations_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    button_data = query.data
    user_data = context.user_data
    if not 'poll_users' in user_data:
        user_data['poll_users'] = []
    finded_org = get_org(user_data['user_in_cat'], int(button_data))
    if finded_org in user_data['poll_users']:
        user_data['poll_users'].remove(finded_org)
    else:
        user_data['poll_users'].append(finded_org)
    updated_keyboard = update_inline_keyboard(
        query.message.reply_markup.inline_keyboard, active_value=button_data, button_type='checkbox')
    await query.message.edit_reply_markup(reply_markup=updated_keyboard)
    return user_data["current_state"]


async def rate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    await query.answer()
    button_data = query.data
    user_data = context.user_data
    user_id = int(query.data.split('__')[1])
    if not 'poll_results' in user_data:
        user_data['poll_results'] = []
        new_dict = {'id': user_id}
        user_data['poll_results'].append(new_dict)
    else:
        new_dict = get_dict(user_data['poll_results'], user_id)
        if not new_dict:
            new_dict = {'id': user_id}
            user_data['poll_results'].append(new_dict)
    key = query.data.split('__')[2]
    rate = int(query.data.split('__')[3])
    if key in new_dict and new_dict[key] == rate:
        del new_dict[key]
        active_value = '0'
    else:
        new_dict[key] = rate
        active_value = button_data

    # if new_dict in user_data['poll_results']:
    #     user_data['poll_results'].remove(new_dict)
    #     active_value = '0'
    # else:
    #     user_data['poll_results'] = clear_results(
    #         user_data['poll_results'], new_dict)
    #     user_data['poll_results'].append(new_dict)
    #     active_value = button_data
    updated_keyboard = update_inline_keyboard(
        query.message.reply_markup.inline_keyboard, active_value=active_value, button_type='rate')
    await query.message.edit_reply_markup(reply_markup=updated_keyboard)
    return user_data["current_state"]


main_dialog = ConversationHandler(
    entry_points=[
        CommandHandler('start', start_conversation),
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(
            re.compile(START_PATTERN, re.IGNORECASE)
        ), start_conversation),
    ],
    states={
        MenuState.DONE_MENU: [
            done_handler,
            CallbackQueryHandler(send_error_message_callback, pattern='error'),
        ],
        MenuState.MAIN_MENU: [
            done_handler,
            profile_handler,
            designer_main_menu_handler,
            services_handler,
            cooperation_requests_handler,
        ],
        MenuState.QUESTIONNAIRE_CAT: [
            CallbackQueryHandler(organizations_callback),
            next_handler,
            cansel_handler,
        ],
        MenuState.QUESTIONNAIRE_QUES: [
            CallbackQueryHandler(rate_callback),
            next_handler,
            cansel_handler,
        ],
        MenuState.QUESTIONNAIRE_END: [
            CallbackQueryHandler(end_callback),
        ],
        MenuState.QUESTIONNAIRE_CANSEL: [
            CallbackQueryHandler(cansel_callback),
        ],
        MenuState.SUPPLIERS_REGISTER: [
            CallbackQueryHandler(activity_select_callback),
            back_handler,
        ],
        MenuState.SUPPLIER_CHOOSING: [
            CallbackQueryHandler(supplier_select_callback),
            back_handler,
        ],
        MenuState.PROFILE: [
            back_handler,
        ],
        MenuState.SERVICES: [
            back_handler,
            CallbackQueryHandler(fetch_supplier_services),
        ],
        MenuState.COOP_REQUESTS: [
            back_handler,
            CallbackQueryHandler(fetch_supplier_requests),
        ],
        MenuState.NEW_USER: [
            registration_dialog,
        ],
    },
    fallbacks=[
        MessageHandler(filters.TEXT & ~filters.COMMAND, go_back)
    ]
)

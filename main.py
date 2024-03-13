import config
import imaplib
import logging
import requests
import schedule
import sqlite3 as sq
import telebot
import threading
import time

from pytz import timezone
from telebot import types


logging.basicConfig(
    level=logging.INFO,
    filename="logs.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s")
# schedule_logger = logging.getLogger('schedule')
# schedule_logger.setLevel(level=logging.DEBUG)

bot = telebot.TeleBot(config.telegram_token)

commands = [
    "Заблокировать МТС",
    "Разблокировать МТС",
    "Статус блокировки МТС"
]

keyboard_main = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard_main.add(*[types.KeyboardButton(comm) for comm in commands])


def get_token():
    login = config.mts_login
    password = config.mts_password
    time_live_token = 86400
    url = "https://api.mts.ru/token"
    params = {
        "grant_type": "client_credentials",
        "validity_period": time_live_token
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(
        url=url,
        auth=(login, password),
        headers=headers,
        params=params
        )
    response = response.json()
    return response["access_token"]


def check_user(message):
    user_id = message.chat.id
    with sq.connect(config.database) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT count() FROM contacts WHERE data = ?",
            (user_id,)
        )
        result = cur.fetchone()[0]
    return result


def get_balance():
    try:
        token = get_token()
        url = "https://api.mts.ru/b2b/v1/Bills/CheckBalanceByAccount?fields=MOAF&accountNo=277702602686"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            url=url,
            headers=headers
        )
        response = response.json()
        balance = response[0]["customerAccountBalance"][0]["remainedAmount"]["amount"]
        return balance
    except Exception:
        logging.critical(msg="func get_balance - error", exc_info=True)


def get_block_info(number):
    try:
        token = get_token()
        url = "https://api.mts.ru/b2b/v1/Product/ProductInfo?category.name=MobileConnectivity"\
              "&marketSegment.characteristic.name=MSISDN"\
              f"&marketSegment.characteristic.value={number}&productOffering.actionAllowed=none"\
              "&productOffering.productSpecification.productSpecificationType.name=block&applyTimeZone=true"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            url=url,
            headers=headers
        )
        response = response.json()
        if response:
            name = response[0]["name"]
            status = response[0]["status"]
            start_block = response[0]["validFor"]["startDateTime"]
            return name, status, start_block
        else:
            return 0
    except Exception:
        logging.critical(msg="func get_block_info - error", exc_info=True)


def get_block_info_first(message):
    try:
        if check_user(message):
            msg = bot.send_message(chat_id=message.chat.id, text="Введи номер (7xxxxxxxxxx)")
            bot.register_next_step_handler(message=msg, callback=get_block_info_second)
        else:
            bot.send_message(chat_id=message.chat.id, text="В другой раз")
    except Exception:
        logging.critical(msg="func get_block_info_first - error", exc_info=True)


def get_block_info_second(message):
    try:
        number = message.text
        result = get_block_info(number)
        if result:
            bot.send_message(
                chat_id=message.chat.id,
                text=f"Имя: {result[0]}\nСтатус: {result[1]}\nДата активации: {result[2]}"
            )
        else:
            bot.send_message(chat_id=message.chat.id, text="Блокировка отсутсвует")
    except Exception:
        logging.critical(msg="func get_block_info_second - error", exc_info=True)


def add_block_first(message):
    try:
        if check_user(message):
            msg = bot.send_message(chat_id=message.chat.id, text="Введи номер (7xxxxxxxxxx)")
            bot.register_next_step_handler(message=msg, callback=add_block)
        else:
            bot.send_message(chat_id=message.chat.id, text="В другой раз")
    except Exception:
        logging.critical(msg="func add_block_first - error", exc_info=True)


def add_block(message):
    try:
        number = message.text
        if not get_block_info(number):
            token = get_token()
            url = f"https://api.mts.ru/b2b/v1/Product/ModifyProduct?msisdn={number}"
            headers = {"Authorization": f"Bearer {token}"}
            js_data = {"characteristic": [{"name": "MobileConnectivity"}], "item": [{"action": "create", "product": {"externalID": "BL0005", "productCharacteristic": [{"name": "ResourceServiceRequestItemType", "value": "ResourceServiceRequestItem"}]}}]}
            response = requests.post(
                url=url,
                headers=headers,
                json=js_data
            )
            response = response.json()
            logging.info(msg=f"func add_block: {response}")
            text = "Успех"
        else:
            text = "Блокировока на номере уже есть"
        bot.send_message(chat_id=message.chat.id, text=text)
    except Exception:
        logging.critical(msg="func add_block - error", exc_info=True)


def del_block_first(message):
    try:
        if check_user(message):
            msg = bot.send_message(chat_id=message.chat.id, text="Введи номер (7xxxxxxxxxx)")
            bot.register_next_step_handler(message=msg, callback=del_block)
        else:
            bot.send_message(chat_id=message.chat.id, text="В другой раз")
    except Exception:
        logging.critical(msg="func add_block_first - error", exc_info=True)


def del_block(message):
    try:
        number = message.text
        if get_block_info(number):
            token = get_token()
            url = f"https://api.mts.ru/b2b/v1/Product/ModifyProduct?msisdn={number}"
            headers = {"Authorization": f"Bearer {token}"}
            js_data = {"characteristic": [{"name": "MobileConnectivity"}], "item": [{"action": "delete", "product": {"externalID": "BL0005", "productCharacteristic": [{"name": "ResourceServiceRequestItemType", "value": "ResourceServiceRequestItem"}]}}]}
            response = requests.post(
                url=url,
                headers=headers,
                json=js_data
            )
            response = response.json()
            logging.info(msg=f"func del_block: {response}")
            text = "Успех"
        else:
            text = "Блокировок на номере нет"
        bot.send_message(chat_id=message.chat.id, text=text)
    except Exception:
        logging.critical(msg="func del_block - error", exc_info=True)


# def add_car(message):
#     try:
#         inline_keys = []
#         with sq.connect(config.database) as con:
#             cur = con.cursor()
#             cur.execute("SELECT id, brand FROM car_brands")
#             result = cur.fetchall()
#         for record in result:
#             inline_keys.append(
#                 types.InlineKeyboardButton(
#                     text=record[1],
#                     callback_data=f"add_car_brand {record[0]}"
#                 )
#             )
#         inline_keys.append(
#             types.InlineKeyboardButton(
#                 text="Новая марка",
#                 callback_data="add_new_brand"
#             )
#         )
#         keyboard = types.InlineKeyboardMarkup()
#         keyboard.add(*inline_keys)
#         bot.send_message(
#             message.from_user.id,
#             text="Выбери марку",
#             reply_markup=keyboard
#         )
#     except Exception:
#         logging.critical("func add_car - error", exc_info=True)


# def add_car_model(message, call_data):
#     try:
#         brand_id = call_data.split()[0]
#         inline_keys = []
#         with sq.connect(config.database) as con:
#             cur = con.cursor()
#             cur.execute("SELECT id, model FROM car_models")
#             result = cur.fetchall()
#         for record in result:
#             inline_keys.append(
#                 types.InlineKeyboardButton(
#                     text=record[1],
#                     callback_data=f"add_car_model {record[0]};{brand_id}"
#                 )
#             )
#         inline_keys.append(
#             types.InlineKeyboardButton(
#                 text="Новая модель",
#                 callback_data="add_new_model"
#             )
#         )
#         keyboard = types.InlineKeyboardMarkup()
#         keyboard.add(*inline_keys)
#         bot.send_message(
#             message.from_user.id,
#             text="Выбери модель",
#             reply_markup=keyboard
#         )
#     except Exception:
#         logging.critical("func add_car_model - error", exc_info=True)


# def add_car_generation(message, call_data):
#     try:
#         brand_id, model_id = call_data.split()[0].split(";")
#         inline_keys = []
#         with sq.connect(config.database) as con:
#             cur = con.cursor()
#             cur.execute("SELECT id, generation FROM car_generations")
#             result = cur.fetchall()
#         for record in result:
#             inline_keys.append(
#                 types.InlineKeyboardButton(
#                     text=record[1],
#                     callback_data=f"add_car_generation {record[0]};{brand_id};{model_id}"
#                 )
#             )
#         inline_keys.append(
#             types.InlineKeyboardButton(
#                 text="Новое поколение",
#                 callback_data="add_new_generation"
#             )
#         )
#         keyboard = types.InlineKeyboardMarkup()
#         keyboard.add(*inline_keys)
#         bot.send_message(
#             message.from_user.id,
#             text="Выбери поколение",
#             reply_markup=keyboard
#         )
#     except Exception:
#         logging.critical("func add_car_generation - error", exc_info=True)


# def check_email(imap_server, email_login, email_password, teleg_id):
#     try:
#         mailbox = imaplib.IMAP4_SSL(imap_server)
#         mailbox.login(email_login, email_password)
#         mailbox.select()
#         unseen_msg = mailbox.uid('search', "UNSEEN", "ALL")
#         id_unseen_msgs = unseen_msg[1][0].decode("utf-8").split()
#         logging.info(msg=f"{email_login}: {id_unseen_msgs}")
#         if id_unseen_msgs:
#             bot.send_message(
#                 teleg_id,
#                 text=f"На почте {email_login} есть непрочитанные письма, в кол-ве {len(id_unseen_msgs)} шт."
#             )
#     except Exception:
#         logging.error("func check email - error", exc_info=True)


# def get_emails():
#     try:
#         with sq.connect(config.database) as con:
#             cur = con.cursor()
#             cur.execute("""
#                 SELECT human, data
#                 FROM contacts
#                 WHERE contact_type = 1
#             """)
#             contacts = cur.fetchall()
#             for contact in contacts:
#                 cur.execute(f"""
#                     SELECT data
#                     FROM contacts
#                     WHERE human = {contact[0]}
#                     AND contact_type = 3
#                 """)
#                 check_email(
#                     email_login=contact[1],
#                     teleg_id=cur.fetchone()[0],
#                     imap_server=config.imap_yandex,
#                     email_password=config.email_passwords[0]
#                 )
#     except Exception:
#         logging.error("func get_emails- error", exc_info=True)


# def schedule_main():
#     schedule.every().day.at(
#         "09:00",
#         timezone(config.timezone_my)
#         ).do(get_emails)
#     schedule.every().day.at(
#         "15:00",
#         timezone(config.timezone_my)
#         ).do(get_emails)
#     schedule.every().day.at(
#         "20:00",
#         timezone(config.timezone_my)
#         ).do(get_emails)
#
#     while True:
#         schedule.run_pending()
#         time.sleep(1)


# @bot.callback_query_handler(func=lambda call: True)
# def callback_query(call):
#     if "add_car_brand" in call.data:
#         add_car_model(call.message, call.data)
#     elif "add_car_model" in call.data:
#         add_car_generation(call.message, call.data)

@bot.message_handler(commands=['start'])
def start_message(message):
    if check_user(message):
        bot.send_message(
            message.chat.id,
            text="Привет! Лови клавиатуру",
            reply_markup=keyboard_main
        )
    else:
        bot.send_message(message.chat.id, text="Привет!")


@bot.message_handler(commands=['commands', 'help'])
def help_message(message):
    if check_user(message):
        bot.send_message(
            message.chat.id,
            text="Лови клавиатуру",
            reply_markup=keyboard_main
        )
    else:
        bot.send_message(chat_id=message.chat.id, text="В другой раз")


@bot.message_handler(content_types=['text'])
def take_text(message):
    if message.text.lower() == commands[0].lower():
        add_block_first(message)
    elif message.text.lower() == commands[1].lower():
        del_block_first(message)
    elif message.text.lower() == commands[2].lower():
        get_block_info_first(message)
    else:
        logging.warning(f"func take_text: not understend question: {message.text}")
        bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')


if __name__ == "__main__":
    # threading.Thread(target=schedule_main).start()
    bot.infinity_polling()

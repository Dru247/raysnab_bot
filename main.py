import config
import imaplib
import logging
import mts_api
import requests
import schedule
import sqlite3 as sq
import telebot
import threading

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

commands = ["МТС.Операции с номерами"]
keyboard_main = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard_main.add(*[types.KeyboardButton(comm) for comm in commands])


def check_user(message):
    try:
        user_id = message.chat.id
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT count() FROM contacts WHERE data = ?",
                (user_id,)
            )
            result = cur.fetchone()[0]
        return result
    except Exception:
        logging.critical(msg="func check_user - error", exc_info=True)


def mts_main(message):
    try:
        if check_user(message):
            msg = bot.send_message(chat_id=message.chat.id, text="Введи номер или номера в столбик")
            bot.register_next_step_handler(message=msg, callback=mts_get_action)
        else:
            bot.send_message(chat_id=message.chat.id, text="В другой раз")
    except Exception:
        logging.critical(msg="func mst_main - error", exc_info=True)


def mts_get_action(message):
    try:
        keyboard = types.InlineKeyboardMarkup()
        numbers = message.text.replace("\n", ";")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                INSERT INTO cb_numbers (people_id, number)
                VALUES ((SELECT human FROM contacts WHERE data = ? AND contact_type = 3), ?)
                """,
                (message.chat.id, numbers)
            )
        keys = [
            ("Разблок.", "mts_unblock_number"),
            ("Разблок. рандом (3-12 ч.)", "mts_unblock_random"),
            ("Заблок.", "mts_block_number"),
            ("Заблок. в конце месяца", "mts_block_last_day")
        ]
        if len(numbers.split(";")) < 2:
            keys.append(("Статус блокировки", f"mts_status_block {numbers}"))
        keyboard.add(*[types.InlineKeyboardButton(text=key[0], callback_data=key[1]) for key in keys])
        bot.send_message(
            message.from_user.id,
            text="Выбери команду",
            reply_markup=keyboard
        )
    except Exception:
        logging.critical(msg="func check_numbers - error", exc_info=True)


def get_block_status(number):
    try:
        token = mts_api.get_token()
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
        logging.info(msg=f"func get_block_status: {response}")
        if response:
            name = response[0]["name"]
            status = response[0]["status"]
            start_block = response[0]["validFor"]["startDateTime"]
            return name, status, start_block
        else:
            return 0
    except Exception:
        logging.critical(msg="func get_block_status - error", exc_info=True)


def get_block_info(message, call_data):
    try:
        number = call_data.split()[1]
        result = get_block_status(number)
        if result:
            bot.send_message(
                chat_id=message.chat.id,
                text=f"Имя: {result[0]}\nСтатус: {result[1]}\nДата активации: {result[2]}"
            )
        else:
            bot.send_message(chat_id=message.chat.id, text="Блокировка отсутсвует")
    except Exception:
        logging.critical(msg="func get_block_info - error", exc_info=True)


def get_balance():
    try:
        token = mts_api.get_token()
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


def mts_add_block(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT number FROM cb_numbers
                WHERE people_id = (SELECT human FROM contacts WHERE data = ? AND contact_type = 3)
                ORDER BY id DESC
                LIMIT 1
                """,
                (message.chat.id,)
            )
            numbers = cur.fetchone()[0].split(";")
        all_time = f"Время обработки запроса: ~{round(len(numbers) * 0.5)} мин."
        bot.send_message(message.chat.id, text=all_time)
        result = "Результат запроса:"
        for number in numbers:
            check, number = mts_api.check_number(number)
            if check:
                response = mts_api.add_block(number)
                if response[0]:
                    result += f"\n{number}: {response[1]} - Номер в блокировке"
                else:
                    result += f"\n{number}: {response[1]} - {response[2]}"
            else:
                result += f"\n{number}: Ошибка - Номер некорректен"
        bot.send_message(message.chat.id, text=result)
    except Exception:
        logging.critical(msg="func mts_add_block - error", exc_info=True)


def mts_del_block(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT number FROM cb_numbers
                WHERE people_id = (SELECT human FROM contacts WHERE data = ? AND contact_type = 3)
                ORDER BY id DESC
                LIMIT 1
                """,
                (message.chat.id,)
            )
            numbers = cur.fetchone()[0].split(";")
        all_time = f"Время обработки запроса: ~{round(len(numbers) * 0.5)} мин."
        bot.send_message(message.chat.id, text=all_time)
        result = "Результат запроса:"
        for number in numbers:
            check, number = mts_api.check_number(number)
            if check:
                response = mts_api.del_block(number)
                if response[0]:
                    result += f"\n{number}: {response[1]} - Номер активен"
                else:
                    result += f"\n{number}: {response[1]} - {response[2]}"
            else:
                result += f"\n{number}: Ошибка - Номер некорректен"
        bot.send_message(message.chat.id, text=result)
    except Exception:
        logging.critical(msg="func mts_del_block - error", exc_info=True)


def mts_del_block_random(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT number FROM cb_numbers
                WHERE people_id = (SELECT human FROM contacts WHERE data = ? AND contact_type = 3)
                ORDER BY id DESC
                LIMIT 1
                """,
                (message.chat.id,)
            )
            numbers = cur.fetchone()[0].split(";")
        all_time = f"Время обработки запроса: ~{round(len(numbers) * 0.5)} мин."
        bot.send_message(message.chat.id, text=all_time)
        result = "Результат запроса:"
        for number in numbers:
            check, number = mts_api.check_number(number)
            if check:
                response = mts_api.del_block_random_hours(number)
                if response[0]:
                    result += f"\n{number}: {response[1]} - Время события: {response[3][:-7]}"
                else:
                    result += f"\n{number}: {response[1]} - {response[2]}"
            else:
                result += f"\n{number}: Ошибка - Номер некорректен"
        bot.send_message(message.chat.id, text=result)
    except Exception:
        logging.critical(msg="func mts_del_block_random - error", exc_info=True)


def mts_add_block_last_day(message):
    try:
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(
                """
                SELECT number FROM cb_numbers
                WHERE people_id = (SELECT human FROM contacts WHERE data = ? AND contact_type = 3)
                ORDER BY id DESC
                LIMIT 1
                """,
                (message.chat.id,)
            )
            numbers = cur.fetchone()[0].split(";")
        all_time = f"Время обработки запроса: ~{round(len(numbers) * 0.5)} мин."
        bot.send_message(message.chat.id, text=all_time)
        result = "Результат запроса:"
        for number in numbers:
            check, number = mts_api.check_number(number)
            if check:
                response = mts_api.add_block_last_day(number)
                if response[0]:
                    result += f"\n{number}: {response[1]} - Время события: {response[3]}"
                else:
                    result += f"\n{number}: {response[1]} - {response[2]}"
            else:
                result += f"\n{number}: Ошибка - Номер некорректен"
        bot.send_message(message.chat.id, text=result)
    except Exception:
        logging.critical(msg="func mts_add_block_last_day - error", exc_info=True)


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
        text = "Привет! Лови клавиатуру!\nЧтобы получить описание введи /help"
        bot.send_message(
            message.chat.id,
            text=text,
            reply_markup=keyboard_main
        )
    else:
        bot.send_message(message.chat.id, text="Привет!")


@bot.message_handler(commands=['commands', 'help'])
def help_message(message):
    if check_user(message):
        text = ("1. Можно вводить команды, недожидаясь завершения другой\n"
                "2. Можно вводить номера через 7, 8 или без первой цифры, т.е. 79998887766, 89998887766, 9998887766\n"
                "3. Можно вводить команду с несколькоми номерами, "
                "нужно вводить их в столбик, без дополнительных знаков. Например:\n"
                "9998887766\n"
                "79998887766\n"
                "89998887766"
                '4. "Разблокировка рандом" разблокирует номера в диапазоне 3-12 часов после отправки команды'
                '5. "Блоркировка в конце месяца" запускает отложенную блокировку в 23:5N:NN в последний день месяца')
        bot.send_message(
            message.chat.id,
            text=text,
            reply_markup=keyboard_main
        )
    else:
        bot.send_message(chat_id=message.chat.id, text="В другой раз")


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if "mts_block_number" in call.data:
        threading.Thread(target=mts_add_block, args=(call.message,)).start()
    elif "mts_unblock_number" in call.data:
        threading.Thread(target=mts_del_block, args=(call.message,)).start()
    elif "mts_status_block" in call.data:
        threading.Thread(target=get_block_info, args=(call.message, call.data)).start()
    elif "mts_unblock_random" in call.data:
        threading.Thread(target=mts_del_block_random, args=(call.message,)).start()
    elif "mts_block_last_day" in call.data:
        threading.Thread(target=mts_add_block_last_day, args=(call.message,)).start()


@bot.message_handler(content_types=['text'])
def take_text(message):
    if check_user(message):
        if message.text.lower() == commands[0].lower():
            mts_main(message)
        else:
            logging.warning(f"func take_text: not understend question: {message.text}")
            bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')
    else:
        bot.send_message(chat_id=message.chat.id, text="В другой раз")


if __name__ == "__main__":
    # threading.Thread(target=schedule_main).start()
    bot.infinity_polling()

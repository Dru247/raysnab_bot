import config
import dj_api
import imaplib
import logging
import mts_api
import openpyxl as op
import schedule
import sqlite3 as sq
import telebot
import time
import threading

from io import BytesIO
from pytz import timezone
from telebot import types


logging.basicConfig(
    level=logging.INFO,
    filename="logs.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s")
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.DEBUG)

bot = telebot.TeleBot(config.telegram_token)

commands = [
    "МТС.Операции с номерами",
    "Список болванок МТС",
    "xlsx.номера",
    'Трекер->СИМ-карта'
]
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
            keys.append(("Замена сим-карты", f"mts_exchange_sim {numbers}"))
        keyboard.add(*[types.InlineKeyboardButton(text=key[0], callback_data=key[1]) for key in keys])
        bot.send_message(
            message.from_user.id,
            text="Выбери команду",
            reply_markup=keyboard
        )
    except Exception:
        logging.critical(msg="func check_numbers - error", exc_info=True)


def mts_block_info(message, call_data):
    try:
        number = call_data.split()[1]
        check, number = mts_api.check_number(number)
        if check:
            error, result, text = mts_api.get_block_info(number)
            if error:
                msg_text = text
            elif result:
                msg_text = f"Добровольная блокировка: ACTIVE\nДата активации: {text}"
            else:
                msg_text = "Добровольная блокировка отсутвует"
        else:
            msg_text = "Неверный формат номера"
        bot.send_message(chat_id=message.chat.id, text=msg_text)
    except Exception:
        logging.critical(msg="func mts_block_info - error", exc_info=True)


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


def mts_exchange_sim(message, call_data):
    try:
        number = call_data.split()[1]
        check, number = mts_api.check_number(number)
        if check:
            msg = bot.send_message(chat_id=message.chat.id, text="Введи последние 4е знака ICCID")
            bot.register_next_step_handler(message=msg, callback=mts_exchange_sim_second, number=number)
    except Exception:
        logging.critical(msg="func mts_exchange_sim - error", exc_info=True)


def mts_exchange_sim_second(message, number):
    try:
        last_iccid = message.text
        if last_iccid.isdigit():
            error, result, text = mts_api.get_vacant_sim_card_exchange(number, last_iccid)
            if result:
                iccid, imsi = text.split()
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton(
                        text="Да",
                        callback_data=f"mts_yes_exchange_sim {number};{imsi}"
                    ),
                    types.InlineKeyboardButton(
                        text="Нет",
                        callback_data=f"mts_no_exchange_sim {number};{imsi}"
                    )
                )
                bot.send_message(
                    chat_id=message.chat.id,
                    text=f"{number} +> {iccid}. Меняем?",
                    reply_markup=keyboard)
            else:
                bot.send_message(chat_id=message.chat.id, text=f"{text}")
    except Exception:
        logging.critical(msg="func mts_exchange_sim_second - error", exc_info=True)


def mts_yes_exchange_sim(message, call_data):
    try:
        number, imsi = call_data.split()[1].split(";")
        _, result, _ = mts_api.get_block_info(number)
        if result:
            mts_api.del_block(number)
        result, text = mts_api.get_exchange_sim_card(number, imsi)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                text="Да",
                callback_data=f"mts_block_exchange_sim {number}"
            ),
            types.InlineKeyboardButton(
                text="Нет",
                callback_data=f"mts_noblock_exchange_sim {number}"
            )
        )
        bot.send_message(
            chat_id=message.chat.id,
            text=f"{result} - {text}.\nПодключаем Добровольную блокировку?",
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func mts_yes_exchange_sim - error", exc_info=True)


def mts_block_exchange_sim(message, call_data):
    try:
        number = call_data.split()[1]
        response = mts_api.add_block(number)
        if response[0]:
            msg_text = f"\n{number}: {response[1]} - Номер в блокировке"
        else:
            msg_text = f"\n{number}: {response[1]} - {response[2]}"
        bot.send_message(chat_id=message.chat.id, text=msg_text)
    except Exception:
        logging.critical(msg="func mts_block_exchange_sim - error", exc_info=True)


def mts_exchange_no(message):
    try:
        bot.send_message(chat_id=message.chat.id, text="Есть отмена")
    except Exception:
        logging.critical(msg="func mts_exchange_sim_second - error", exc_info=True)


def mts_get_balance():
    try:
        error, result = mts_api.get_balance()
        if error:
            msg_text = f"Ошибка - {result}"
        else:
            with sq.connect(config.database) as con:
                cur = con.cursor()
                cur.execute("SELECT balance FROM mts_balances ORDER BY id DESC LIMIT 1")
                old_balance = cur.fetchone()[0]
                cur.execute("INSERT INTO mts_balances (balance) VALUES (?)", (result,))
            difference = float(result) - old_balance
            msg_text = f"МТС Баланс: {round(result, 2)} ({round(difference, 2)})\nПерерасход:"
            for record in mts_api.get_balance_numbers():
                number, balance = record
                msg_text += f"\n{number} - {balance}"
        bot.send_message(chat_id=config.telegram_my_id, text=msg_text)
    except Exception:
        logging.critical(msg="func mts_get_balance - error", exc_info=True)


def mts_check_balance():
    try:
        records = mts_api.get_balance_numbers(config.critical_balance)
        if records:
            msg_text = "МТС Перерасход:"
            for record in records:
                number, balance = record
                msg_text += f"\n{number} - {balance}"
            with sq.connect(config.database) as con:
                cur = con.cursor()
                cur.execute("SELECT data FROM contacts WHERE contact_type = 3")
                result = cur.fetchall()
                for send in result:
                    bot.send_message(chat_id=send[0], text=msg_text)
    except Exception:
        logging.critical(msg="func mts_check_balance - error", exc_info=True)


def check_email(imap_server=config.imap_server_yandex, email_login=config.ya_mary_email_login, email_password=config.ya_mary_email_password, teleg_id=config.id_teleg_mary):
    try:
        mailbox = imaplib.IMAP4_SSL(imap_server)
        mailbox.login(email_login, email_password)
        mailbox.select()
        unseen_msg = mailbox.uid('search', "UNSEEN", "ALL")
        id_unseen_msgs = unseen_msg[1][0].decode("utf-8").split()
        logging.info(msg=f"{email_login}: {id_unseen_msgs}")
        if id_unseen_msgs:
            bot.send_message(
                teleg_id,
                text=f"На почте {email_login} есть непрочитанные письма, в кол-ве {len(id_unseen_msgs)} шт."
            )
    except Exception:
        logging.error("func check email - error", exc_info=True)


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

def xlsx_numbers(message):
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Загрузи xlsx")
        bot.register_next_step_handler(message=msg, callback=get_xlsx_numbers)
    except Exception:
        logging.error("func xlsx_numbers - error", exc_info=True)


def get_xlsx_numbers(message):
    try:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        numbers = {
            "МТС": [],
            "МЕГА": [],
            "СИМ2М": []
        }
        excel_doc = op.open(filename=BytesIO(downloaded_file), data_only=True)
        sheet_names = excel_doc.sheetnames
        sheet = excel_doc[sheet_names[0]]
        count_row = 2
        while sheet.cell(row=count_row, column=1).value is not None:
            data_row = sheet.cell(row=count_row, column=1).value.split(", ")
            for data in data_row:
                data = data.split(": ")
                if data[0].isdigit():
                    if data[0][5] != "0":
                        numbers["СИМ2М"].append(data[1])
                    else:
                        if len(data[0]) == 20:
                            numbers["МТС"].append(data[1])
                        else:
                            numbers["МЕГА"].append(data[1])
            count_row += 1
        for key in numbers:
            msg_text = key + "\n"
            for value in numbers[key]:
                msg_text += value + "\n"
            bot.send_message(chat_id=message.chat.id, text=msg_text)
        excel_doc.close()
    except Exception:
        logging.error("func get_xlsx_numbers - error", exc_info=True)


def get_sim_tracker(message):
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Напиши imei")
        bot.register_next_step_handler(message=msg, callback=request_sim_tracker)
    except Exception:
        logging.error("func get_sim_tracker - error", exc_info=True)


def request_sim_tracker(message):
    try:
        imei = message.text
        sim_cards = dj_api.get_sim(terminal_imei=imei)
        msg_text = str()
        for sim in sim_cards:
            msg_text += str(sim) + "\n"
        bot.send_message(chat_id=message.chat.id, text=msg_text)
    except Exception:
        logging.error("func request_sim_tracker - error", exc_info=True)


def get_request_vacant_sim_card_exchange(message):
    try:
        result_text = str()
        request_list = mts_api.request_vacant_sim_card_exchange()
        for simcard in request_list.get('simList'):
            result_text += simcard.get('iccId') + "\n"
        bot.send_message(chat_id=message.chat.id, text=result_text)

    except Exception:
        logging.critical(msg="func get_request_vacant_sim_card_exchange - error", exc_info=True)


def schedule_main():
    try:
        schedule.every().day.at("06:00", timezone(config.timezone_my)).do(mts_get_balance)
        schedule.every().hour.at(":00").do(mts_check_balance)
        schedule.every().day.at("09:00", timezone(config.timezone_my)).do(check_email)
        schedule.every().day.at("15:00", timezone(config.timezone_my)).do(check_email)
        schedule.every().day.at("21:00", timezone(config.timezone_my)).do(check_email)

        while True:
            schedule.run_pending()
            time.sleep(1)

    except Exception:
        logging.error("func schedule_main - error", exc_info=True)


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
                "89998887766\n"
                '4. "Разблокировка рандом" разблокирует номера в диапазоне 3-12 часов после отправки команды\n'
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
        threading.Thread(target=mts_block_info, args=(call.message, call.data)).start()
    elif "mts_unblock_random" in call.data:
        threading.Thread(target=mts_del_block_random, args=(call.message,)).start()
    elif "mts_block_last_day" in call.data:
        threading.Thread(target=mts_add_block_last_day, args=(call.message,)).start()
    elif "mts_exchange_sim" in call.data:
        threading.Thread(target=mts_exchange_sim, args=(call.message, call.data)).start()
    elif "mts_yes_exchange_sim" in call.data:
        threading.Thread(target=mts_yes_exchange_sim, args=(call.message, call.data)).start()
    elif "mts_no_exchange_sim" in call.data:
        threading.Thread(target=mts_exchange_no, args=(call.message,)).start()
    elif "mts_block_exchange_sim" in call.data:
        threading.Thread(target=mts_block_exchange_sim, args=(call.message, call.data)).start()
    elif "mts_noblock_exchange_sim" in call.data:
        threading.Thread(target=mts_exchange_no, args=(call.message,)).start()


@bot.message_handler(content_types=['text'])
def take_text(message):
    if check_user(message):
        if message.text.lower() == commands[0].lower():
            mts_main(message)
        elif message.text.lower() == commands[1].lower():
            get_request_vacant_sim_card_exchange(message)
        elif message.text.lower() == commands[2].lower():
            xlsx_numbers(message)
        elif message.text.lower() == commands[3].lower():
            get_sim_tracker(message)
        else:
            logging.warning(f"func take_text: not understend question: {message.text}")
            bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')
    else:
        bot.send_message(chat_id=message.chat.id, text="В другой раз")


if __name__ == "__main__":
    threading.Thread(target=schedule_main).start()
    bot.infinity_polling()

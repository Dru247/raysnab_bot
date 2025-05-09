import api_dj
import api_glonasssoft
import api_mts
import datetime
import calendar
import configs
import imaplib
import logging
import openpyxl as op
import schedule
import sqlite3 as sq
import time
import threading

from dateutil.relativedelta import relativedelta
from io import BytesIO
from PIL import Image
from pytz import timezone
from pyzbar.pyzbar import decode
from telebot import TeleBot, types


logging.basicConfig(
    level=logging.INFO,
    filename="logs.log",
    filemode="a",
    format="%(asctime)s %(filename)s:%(lineno)s%(funcName)20s() %(levelname)s %(message)s")
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.DEBUG)

bot = TeleBot(configs.telegram_token)

commands = [
    'Статус блокировки',
    'Разблокировать номер',
    'Заблокировать номер',
    'Замена СИМ-карты',
    'Список болванок МТС',
    'Список СИМ-карт',
    'Оплата',
    'Проверки',
    'Чья смена?',
    'Запас',
    'Прайс'
]
install_commands = [commands[9], commands[10]]
keyboard_main = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
keyboard_main.add(*[types.KeyboardButton(comm) for comm in commands])

keyboard_install = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
keyboard_install.add(*[types.KeyboardButton(comm) for comm in install_commands])

install_telegram_id = [
    int(configs.telegram_malashin_id),
    int(configs.telegram_sumbulov_id),
    int(configs.telegram_my_930_id)
]

def check_user(message):
    """Проверяет пользователя на право выполнения команд"""
    try:
        user_id = message.chat.id
        with sq.connect(configs.database) as con:
            cur = con.cursor()
            cur.execute(
                "SELECT count() FROM contacts WHERE data = ?",
                (user_id,)
            )
            result = cur.fetchone()[0]
        return result
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_number(number):
    """Проверяет номера симок на корректность"""
    try:
        number = number.strip()
        if number.isdigit():
            len_number = len(number)
            if len_number == 10:
                number = "7" + number
                return True, number
            elif len_number == 11:
                number = "7" + number[1:]
                return True, number
            else:
                logging.info(msg=f"func check_number: {number}")
                return False, number
        else:
            logging.info(msg=f"func check_number: {number}")
            return False, number
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_date(date_target):
    """Проверяет дату"""
    try:
        date_target = datetime.datetime.strptime(date_target, '%Y-%m-%d')
        return isinstance(date_target, datetime.date)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def cut_msg_telegram(text_msg):
    """Обрезает сообщения по максимальному значению символов в сообщении Телеграм"""
    try:
        max_char_msg_telegram = 4096
        msgs = list()
        list_rows = text_msg.split('\n')
        one_msg = str()
        len_char = 0

        for row in list_rows:
            row += '\n'
            if len(row) + len_char > max_char_msg_telegram:
                msgs.append(one_msg)
                one_msg = row
                len_char = len(row)
            else:
                one_msg += row
                len_char += len(row)

        msgs.append(one_msg)
        return msgs
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_request_number(message):
    """Запрашивает номер симки"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Введи номер сим-карты")
        bot.register_next_step_handler(message=msg, callback=mts_block_info)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_block_info(message):
    try:
        number = message.text
        check, number = check_number(number)
        if check:
            error, result, text = api_mts.get_block_info(number)
            if error:
                msg_text = text
            elif result:
                msg_text = f"Добровольная блокировка: ACTIVE\nДата активации: {text}"
            else:
                msg_text = "Добровольная блокировка отсутствует"
        else:
            msg_text = "Неверный формат номера"
        bot.send_message(chat_id=message.chat.id, text=msg_text)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_activate_num_choice(message):
    """Запрашивает когда нужно разблокировать номера"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='Сейчас',
                callback_data='mts_activate_num_now'
            ),
            types.InlineKeyboardButton(
                text='Рандом 3-12 ч.',
                callback_data='mts_activate_num_random'
            )
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            chat_id=message.chat.id,
            text='Когда?',
            reply_markup=keyboard)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_request_numbers(message, target_func):
    """Запрашивает список номер на удаление или добавления услуг"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Введи номер или номера в столбик")
        bot.register_next_step_handler(message=msg, callback=mts_add_del_services, target_func=target_func)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_add_del_services(message, target_func):
    """Удаляет и добавляет услуги номеров"""
    try:
        numbers = message.text.split('\n')
        all_time = f'Время обработки запроса: ~{round(len(numbers) * 2)} сек.'
        bot.send_message(message.chat.id, text=all_time)
        successfully_requests = list()
        final_list = list()
        for number_old in numbers:
            check, number = check_number(number_old)
            if not check:
                final_list.append((False, number_old, 'Ошибка - Номер некорректен'))
            else:
                success, response_text = target_func(number)
                if not success:
                    final_list.append((success, number, response_text))
                # else:
                #     successfully_requests.append((success, number, response_text))
                time.sleep(1)

        for success, num, event_id_request in successfully_requests:
            success, response_text = api_mts.check_status_request(event_id_request)
            final_list.append((success, num, response_text))
            time.sleep(1)

        final_list.sort(key=lambda a: a[0])
        text_msg = 'Результат запроса:\n'
        for record in final_list:
            text_msg += f'{record[1]} - {record[2]}\n'

        bot.send_message(message.chat.id, text=text_msg)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_exchange_choice_get_number(message):
    """Запрос на выбор способа получения номера СИМ-карты"""
    try:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                text='Следующий номер в очереди по дате',
                callback_data='mts_exchange_sim_next_number'
            ),
            types.InlineKeyboardButton(
                text='Ввести номер самостоятельно',
                callback_data='mts_exchange_sim_input_number'
            ),
            row_width=1
        )
        bot.send_message(
            chat_id=message.chat.id,
            text='Какой номер сим-карты?',
            reply_markup=keyboard
        )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_exchange_sim_input_number(message):
    """Запрос ввода номера СИМ-карты"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Введи номер для замены')
        bot.register_next_step_handler(message=msg, callback=mts_exchange_sim, number=True)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_exchange_sim(message, number=False):
    """Выводит первый номер для замены МТС или проверяет введённый и спрашивает про ICC ID"""
    try:
        if not number:
            numbers = api_dj.get_numbers_for_change()
            number, num_date = numbers[1]
            text_msg = f'Всего для замены: {len(numbers)} шт.\nСледующий: {number}\nДата: {num_date}'
            bot.send_message(chat_id=message.chat.id, text=text_msg)
        else:
            number = message.text
            check, number = check_number(number)
            if not check:
                bot.send_message(chat_id=message.chat.id, text='Неверный формат номера')
                return
        msg = bot.send_message(chat_id=message.chat.id, text='Введи последние 4е знака ICC ID')
        bot.register_next_step_handler(message=msg, callback=mts_exchange_sim_second, number=number)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_exchange_sim_second(message, number):
    """"""
    try:
        last_icc_id = message.text
        if last_icc_id.isdigit():
            error, result, text = api_mts.get_vacant_sim_card_exchange(number, last_icc_id)
            if result:
                icc_id, imsi = text.split()
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton(
                        text='Да',
                        callback_data=f'mts_yes_exchange_sim {number};{imsi}'
                    )
                )
                bot.send_message(
                    chat_id=message.chat.id,
                    text=f'{number} +> {icc_id}. Меняем?',
                    reply_markup=keyboard
                )
            else:
                bot.send_message(chat_id=message.chat.id, text=f'{text}')
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_yes_exchange_sim(message, call_data):
    """Отправляет номер на замену сим-карты, спрашивает про дальнейшую блокировку"""
    try:
        number, imsi = call_data.split()[1].split(';')
        api_mts.get_exchange_sim_card(number, imsi)
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                text='Да',
                callback_data=f'mts_block_exchange_sim {number}'
            )
        )
        bot.send_message(
            chat_id=message.chat.id,
            text=f'Подключаем Добровольную блокировку?',
            reply_markup=keyboard
        )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_block_exchange_sim(message, call_data):
    """"""
    try:
        number = call_data.split()[1]
        response = api_mts.add_block(number)
        if response[0]:
            msg_text = f'{number}: Номер в блокировке'
        else:
            msg_text = f'{number}: {response[1]} - {response[2]}'
        bot.send_message(chat_id=message.chat.id, text=msg_text)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_get_account_balance():
    """Сравнивает, записывает и отправляет баланс лицевого счёта"""
    try:
        error, result = api_mts.get_balance()
        if error:
            msg_text = f'Ошибка - {result}'
        else:
            with sq.connect(configs.database) as con:
                cur = con.cursor()
                cur.execute("SELECT balance FROM mts_balances ORDER BY id DESC LIMIT 1")
                old_balance = cur.fetchone()[0]
                cur.execute("INSERT INTO mts_balances (balance) VALUES (?)", (result,))
            difference = float(result) - old_balance
            msg_text = f"МТС Баланс: {round(result, 2)} ({round(difference, 2)})"
        bot.send_message(chat_id=configs.telegram_my_id, text=msg_text)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_check_num_balance(critical=False):
    """Проверяет номера МТС на КРИТИЧЕСКИЙ перерасход и отправляет сотрудникам в чат"""
    try:
        records, extra_money = api_mts.get_balance_numbers(critical)
        if records:
            msg_text = 'МТС Перерасход:'
            for record in records:
                number, sim_balance = record
                msg_text += f'\n{number} - {sim_balance}'
            msgs = cut_msg_telegram(msg_text)
            if critical:
                with sq.connect(configs.database) as con:
                    cur = con.cursor()
                    cur.execute('SELECT data FROM contacts WHERE contact_type = 3')
                    result = cur.fetchall()
                    chats = [chat[0] for chat in result]
            else:
                chats = [configs.telegram_my_id, configs.telegram_sister_id]
            for chat in chats:
                for msg in msgs:
                    bot.send_message(chat_id=chat, text=msg)
            bot.send_message(chat_id=configs.telegram_my_id, text=f'Общий перерасход: {extra_money}')

    except Exception as err:
        logging.critical(msg='', exc_info=err)
        bot.send_message(
            chat_id=configs.telegram_my_id,
            text='Ошибка проверки критического баланса МТС'
        )


def check_email(imap_server=configs.imap_server_yandex, email_login=configs.ya_mary_email_login, email_password=configs.ya_mary_email_password, telegram_id=configs.id_telegram_mary):
    try:
        mailbox = imaplib.IMAP4_SSL(imap_server)
        mailbox.login(email_login, email_password)
        mailbox.select()
        unseen_msg = mailbox.uid('search', "UNSEEN", "ALL")
        id_unseen_msgs = unseen_msg[1][0].decode("utf-8").split()
        logging.info(msg=f"{email_login}: {id_unseen_msgs}")
        if id_unseen_msgs:
            bot.send_message(
                telegram_id,
                text=f"На почте {email_login} есть непрочитанные письма, в кол-ве {len(id_unseen_msgs)} шт."
            )
    except Exception as err:
        logging.error(msg='', exc_info=err)


def get_numbers_payer_or_date(message):
    """Спрашивает по дате или по плательщику прислать сим-карты"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='По ID плательщика',
                callback_data='get_numbers_id_payer'),
            types.InlineKeyboardButton(
                text='По дате',
                callback_data='get_numbers_date'),
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text='Выбери',
            reply_markup=keyboard)
    except Exception as err:
        logging.error(msg='', exc_info=err)


def get_number_payer_sim_cards(message):
    """Запрашивает номер плательщика"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Напиши ID плательщика")
        bot.register_next_step_handler(message=msg, callback=get_list_payer_sim_cards)
    except Exception as err:
        logging.error(msg='', exc_info=err)


def get_list_payer_sim_cards(message, payer_id=None):
    """Отправляет сообщение со списком номеров сим-карт по плательщику"""
    try:
        if not payer_id:
            payer_id = message.text
        sim_cards = api_dj.get_payer_sim_cards(payer_id)
        for sim_list in sim_cards:
            bot.send_message(
                chat_id=message.chat.id,
                text='\n'.join(sim_list)
            )
    except Exception as err:
        logging.error(msg='', exc_info=err)


def get_list_date_sim_cards(message):
    """Запрашивает дату"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Напиши дату в формате "2000-12-31"')
        bot.register_next_step_handler(message=msg, callback=get_list_date_sim_cards_handler)
    except Exception as err:
        logging.error(msg='', exc_info=err)


def get_list_date_sim_cards_handler(message):
    """Отправляет сообщение со списком номеров сим-карт по дате"""
    try:
        date = message.text
        sim_cards = api_dj.get_date_sim_cards(date)
        for sim_list in sim_cards:
            text_msg = '\n'.join(sim_list)
            for msg_one in cut_msg_telegram(text_msg):
                bot.send_message(
                    chat_id=message.chat.id,
                    text=msg_one
                )
    except Exception as err:
        logging.error("func get_list_date_sim_cards_handler - error", exc_info=err)


def get_list_vacant_sim_cards(message):
    """Отправляет сообщение со списком 'болванок'"""
    try:
        sim_cards = api_mts.get_vacant_sim_cards()
        for msg in cut_msg_telegram('\n'.join(sim_cards)):
            bot.send_message(
                chat_id=message.chat.id,
                text=msg
            )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_mts_sim_cards(msg_chat_id):
    """Сравнивает сим-карты на проекте и сайте МТС"""
    try:
        mts_id = 2
        prj_mts_sim_cards = [(num[3], num[2]) for num in api_dj.get_list_sim_cards() if num[1] == mts_id]
        site_mts_sim_cards = api_mts.get_list_all_icc()
        another_sim = set(prj_mts_sim_cards) ^ set(site_mts_sim_cards)
        msg_text = f'Разница {len(another_sim)} шт.'
        for num in another_sim:
            msg_text += f'\n{num[0]} {num[1]}'
        for msg in cut_msg_telegram(msg_text):
            bot.send_message(
                chat_id=msg_chat_id,
                text=msg
            )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_active_mts_sim_cards(msg_chat_id=None):
    """Сравнивает активные сим-карты на проекте и на МТС"""
    try:
        id_chats = list()
        if msg_chat_id:
            id_chats.append(msg_chat_id)
            bot.send_message(chat_id=msg_chat_id, text='Проверка запущена. Займёт ~1,5 часа')
        else:
            id_chats.extend((configs.telegram_maks_id, configs.telegram_my_id))
        dj_mts_sim_cards = set(api_dj.get_all_active_sim_cards())
        numbers_in_hands = {num['contact_rec'] for num in api_dj.api_request_human_contacts()}
        site_mts_sim_cards = set(api_mts.get_all_active_sim_cards())
        site_mts_sim_cards -= numbers_in_hands # убираем активные сим-карты на руках и с тарифами
        sim_cards = dj_mts_sim_cards ^ site_mts_sim_cards
        msg_text = 'Разница блокировки СИМ-карт:\n' + '\n'.join(sim_cards)
        for id_chat in id_chats:
            for msg_one in cut_msg_telegram(msg_text):
                bot.send_message(
                    chat_id=id_chat,
                    text=msg_one
                )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_glonasssoft_dj_objects(msg_chat_id):
    """Выдаёт разницу объектов на CLONASSSoft"""
    try:
        date_now = datetime.datetime.today()
        glonasssoft_objs = {obj.get('imei') for obj in api_glonasssoft.request_list_objects(configs.glonasssoft_org_id)}
        user_list_target_serv = {user.get('id') for user in api_dj.api_request_user_list() if user.get('server') == 4}
        project_objs = {
            obj.get('terminal') for obj in api_dj.api_request_object_list()
            if obj.get('wialon_user') in user_list_target_serv
            and datetime.datetime.fromisoformat(obj.get('date_change_status')) >= date_now
        }
        terminals = {term.get('id'): term.get('imei') for term in api_dj.api_request_terminal_list()}
        result = glonasssoft_objs ^ {terminals[obj] for obj in project_objs}
        msg_text = f'Разница трекеров GLONASSSoft: {len(result)}\n' + '\n'.join(result)
        bot.send_message(chat_id=msg_chat_id,  text=msg_text)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_request_data_payer(message):
    """Запрашивает способ определения плательщика"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='По ID',
                callback_data='payment_choice_id'
            ),
            types.InlineKeyboardButton(
                text='По сообщению',
                callback_data='payment_choice_msg'
            )
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text='Выбери способ определения плательщика',
            reply_markup=keyboard)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_request_payer_id(message):
    """Запрашивает ID плательщика"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Напиши ID плательщика')
        bot.register_next_step_handler(message=msg, callback=payment_request_date)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_request_payer_msg(message):
    """Запрашивает сообщение плательщика у которого нужно зарегистрировать платёж в объектах"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Перешли сообщение плательщика')
        bot.register_next_step_handler(message=msg, callback=payment_request_payer_msg_handler)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_request_payer_msg_handler(message):
    """Обрабатывает сообщение плательщика"""
    try:
        try:
            telegram_id_payer = message.forward_from.id
            payer_id = api_dj.get_id_human_for_from_telegram_id(telegram_id_payer)
            if not payer_id:
                bot.send_message(chat_id=message.chat.id, text=f'{telegram_id_payer} - не зарегистрирован')
            else:
                bot.send_message(chat_id=message.chat.id, text=f'Telegram ID: {telegram_id_payer}')
            payment_request_date(message, payer_id)
        except AttributeError as _:
            bot.send_message(chat_id=message.chat.id, text=f'ID пользователя скрыт')
            payment_request_payer_id(message)

    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_request_date(message, payer_id=None):
    """Выбор даты оплаченного периода"""
    try:
        if not payer_id:
            payer_id = message.text
        date_now = datetime.date.today()
        now_month_last_day = calendar.monthrange(date_now.year, date_now.month)[1]
        date_target_now_month = date_now.strftime(f'%Y-%m-{now_month_last_day}')
        date_plus_month = date_now + relativedelta(months=1)
        date_plus_month_last_day = calendar.monthrange(date_plus_month.year, date_plus_month.month)[1]
        date_target_plus_month  = date_plus_month.strftime(f'%Y-%m-{date_plus_month_last_day}')
        inline_keys = [
            types.InlineKeyboardButton(
                text=date_target_now_month,
                callback_data=f'payment_change_date {payer_id} {date_target_now_month}'
            ),
            types.InlineKeyboardButton(
                text=date_target_plus_month,
                callback_data=f'payment_change_date {payer_id} {date_target_plus_month}'
            ),
            types.InlineKeyboardButton(
                text='Произвольная дата',
                callback_data=f'payment_custom_date {payer_id}'
            ),
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys, row_width=2)
        bot.send_message(
            message.from_user.id,
            text='Выбери дату',
            reply_markup=keyboard)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_request_custom_date(message, call_data):
    """Запрашивает произвольную дату"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Введи дату в формате "2000-01-31"')
        bot.register_next_step_handler(message=msg, callback=payment_change_date, call_data=call_data)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_change_date(message, call_data):
    """Регистрирует оплаченную дату в объектах плательщика"""
    try:

        if len(call_data.split()) == 2:
            payer_id = call_data.split()[1]
            date_target = message.text
        else:
            payer_id, date_target = call_data.split()[1:]
        if not check_date(date_target):
            bot.send_message(message.chat.id, text='Неверный формат даты')
        else:
            api_dj.objects_change_date(payer_id, date_target)
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    text='Вывести СИМ-карты плательщика',
                    callback_data=f'payment_get_sim_cards_payers {payer_id}'
                )
            )
            bot.send_message(
                message.chat.id,
                text='Успех',
                reply_markup=keyboard)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def request_upload_mega_exel(message):
    """"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Загрузи МЕГАФОН')
        bot.register_next_step_handler(message=msg, callback=upload_mega_exel)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def upload_mega_exel(message):
    """"""
    try:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        excel_doc = op.load_workbook(filename=BytesIO(downloaded_file), data_only=True)
        sheet_names = excel_doc.sheetnames
        sheet = excel_doc[sheet_names[0]]
        count_row = 2

        while sheet.cell(row=count_row, column=1).value is not None:
            number = sheet.cell(row=count_row, column=1).value
            icc_id = sheet.cell(row=count_row, column=17).value
            print(number, icc_id)
            count_row += 1

        excel_doc.close()
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def request_upload_sim2m_exel(message):
    """"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Загрузи СИМ2М')
        bot.register_next_step_handler(message=msg, callback=upload_sim2m_exel)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def upload_sim2m_exel(message):
    """"""
    try:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        excel_doc = op.open(filename=BytesIO(downloaded_file), data_only=True)
        sheet_names = excel_doc.sheetnames
        sheet = excel_doc[sheet_names[0]]
        count_row = 2

        while sheet.cell(row=count_row, column=1).value is not None:
            number = sheet.cell(row=count_row, column=6).value
            icc_id = sheet.cell(row=count_row, column=7).value
            status = sheet.cell(row=count_row, column=2).value
            print(number, icc_id, status)
            count_row += 1

        excel_doc.close()
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_diff_terminals(msg_chat_id):
    """Возвращает проверку трекеров"""
    try:
        diff_trackers_all_vs_install_and_on_hands, diff_trackers_on_hands_and_obj = api_dj.get_diff_terminals()
        msg_text = 'Трекеры без объектов и не на руках:\n' + '\n'.join(diff_trackers_all_vs_install_and_on_hands)
        for msg_one in cut_msg_telegram(msg_text):
            bot.send_message(
                chat_id=msg_chat_id,
                text=msg_one
            )
        msg_text = 'Трекеры в объектах и на руках:\n' + '\n'.join(diff_trackers_on_hands_and_obj)
        for msg_one in cut_msg_telegram(msg_text):
            bot.send_message(
                chat_id=msg_chat_id,
                text=msg_one
            )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_sim_cards_in_dj(msg_chat_id):
    """Проверка сим-карт внутри проекта"""
    try:
        sim_in_trackers_and_on_hands, sim_not_everywhere = api_dj.check_sim_cards_in_dj()
        msg_text = f'СИМ-карты и на руках и в трекерах: {len(sim_in_trackers_and_on_hands)}\n' + '\n'.join(sim_in_trackers_and_on_hands)
        for msg_one in cut_msg_telegram(msg_text):
            bot.send_message(
                chat_id=msg_chat_id,
                text=msg_one
            )
        msg_text = f'СИМ-карты не на руках и не в трекерах: {len(sim_not_everywhere)}\n' + '\n'.join(sim_not_everywhere)
        for msg_one in cut_msg_telegram(msg_text):
            bot.send_message(
                chat_id=msg_chat_id,
                text=msg_one
            )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def schedule_request_date(message):
    """Запрос даты для вывода человека по графику"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='Сегодня',
                callback_data=f'schedule today'
            ),
            types.InlineKeyboardButton(
                text='Завтра',
                callback_data=f'schedule tomorrow'
            )
            # types.InlineKeyboardButton(
            #     text='Произвольная дата',
            #     callback_data=''
            # )
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys, row_width=2)
        bot.send_message(
            message.chat.id,
            text='Когда?',
            reply_markup=keyboard)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def schedule_get_human(message, call_data):
    """Выводит человека чья дата смены"""
    try:
        if 'tomorrow' in call_data:
            date_target = datetime.datetime.today() + datetime.timedelta(days=1)
            date_target = date_target.date()
        else:
            date_target = datetime.date.today()
        schedule_man = api_dj.get_api_schedule_man(date_target)
        bot.send_message(
            chat_id=message.chat.id,
            text=f'{date_target} дежурит {schedule_man}'
        )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def checks(message):
    """Выдаёт список проверок"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='Проверка СИМ-карт на проекте',
                callback_data='check_sim_cards_in_dj'
            ),
            types.InlineKeyboardButton(
                text='Проверка номеров',
                callback_data='check_numbers'
            ),
            types.InlineKeyboardButton(
                text='Проверка перерасхода СИМ-карт',
                callback_data='check_overspend_sim_cards'
            ),
            types.InlineKeyboardButton(
                text='Проверка блокировок СИМ-карт',
                callback_data='check_active_sim_cards'
            ),
            types.InlineKeyboardButton(
                text='Проверка объектов GLONASSsoft',
                callback_data='check_glonasssoft'
            ),
            types.InlineKeyboardButton(
                text='Потерянные трекеры',
                callback_data='check_lost_trackers'
            ),
            types.InlineKeyboardButton(
                text='Загрузить МЕГАФОН',
                callback_data='check_upload_mega_exel'
            ),
            types.InlineKeyboardButton(
                text='Загрузить СИМ2М',
                callback_data='check_upload_sim2m_exel'
            )
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys, row_width=1)
        msg_text = (
            '"Проверка СИМ-карт на проекте" - проверка наличия сим-карт в трекерах и на руках\n'
            '"Проверка номеров" - разница номеров и ICC ID на проекте и на сайте МТС\n'
            '"Проверка перерасхода СИМ-карт" - сим-карты с расходом более 28 руб.\n'
            '"Проверка блокировок СИМ-карт" - разница активных номеров на проекте и сайте МТС (~1,5 часа)\n'
            '"Проверка объектов GLONASSsoft" - разница активных объектов на проекте и GLONASSSoft\n'
            '"Потерянные трекеры" - трекеры без установок и не на руках'
        )
        bot.send_message(
            chat_id=message.chat.id,
            text=msg_text,
            reply_markup=keyboard
        )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_stock(message):
    """"""
    try:
        telegram_id = message.chat.id
        if telegram_id in install_telegram_id:
            inline_keys = [
                types.InlineKeyboardButton(
                    text='Кол-во',
                    callback_data=f'get_stock {telegram_id}'
                ),
                types.InlineKeyboardButton(
                    text='Детально',
                    callback_data=f'get_stock {telegram_id} details'
                )
            ]
            text_msg = 'Как вывести?'
        else:
            inline_keys = [
                types.InlineKeyboardButton(
                    text='Малашин А.',
                    callback_data=f'get_stock {configs.telegram_malashin_id}'
                ),
                types.InlineKeyboardButton(
                    text='Сумбулов А.',
                    callback_data=f'get_stock {configs.telegram_sumbulov_id}'
                ),
                types.InlineKeyboardButton(
                    text='Мерзляков М.',
                    callback_data=f'get_stock {configs.telegram_maks_id}'
                ),
                types.InlineKeyboardButton(
                    text='Лехтин А.',
                    callback_data=f'get_stock {configs.telegram_my_id}'
                )
            ]
            text_msg = 'Чей запас вывести?'
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys, row_width=2)
        bot.send_message(
            chat_id=telegram_id,
            text=text_msg,
            reply_markup=keyboard
        )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_stock_handler(message, call_data):
    """Выводит кол-во и список оборудования на руках"""
    try:
        target_telegram_id = call_data.split()[1]
        result = api_dj.get_stock(target_telegram_id)
        if 'details' in call_data:
            text_result_list = list()
            for key, value in result.items():
                text_result_list.append(key)
                for imei, serial in value:
                    text_result_list.append(f'{imei} {serial}')
            text_msg='\n'.join(text_result_list)
        else:
            result_len = [f'{key} - {len(value)} шт.' for key, value in result.items()]
            text_msg = '\n'.join(result_len)
        bot.send_message(
            chat_id=message.chat.id,
            text=text_msg
        )
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_price(message):
    """Запрашивает тип прайса для вывода"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='Выезды',
                callback_data='get_price logistics'
            ),
            types.InlineKeyboardButton(
                text='Оборудование',
                callback_data='get_price trackers'
            ),
            types.InlineKeyboardButton(
                text='Услуги',
                callback_data='get_price services'
            )
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text='Выбери',
            reply_markup=keyboard
        )
    except Exception as err:
        logging.error(msg='', exc_info=err)


def get_price_type(message, call_data):
    """Отправляет сообщение с прайсом"""
    try:
        target_price = call_data.split()[1]
        result = str()
        match target_price:
            case 'logistics':
                result = api_dj.get_price_logistic()
            case 'trackers':
                result = api_dj.get_price_trackers()
            case 'services':
                result = api_dj.get_services()
        bot.send_message(
            message.chat.id,
            text='\n'.join(result)
        )
    except Exception as err:
        logging.error(msg='', exc_info=err)


def morning_check():
    """
    Утренний скрипт:
    1. проверка баланса ЛС,
    2. проверка перерасхода номеров,
    3. проверка наличие сим-карт на проекте и МТС,
    4. сравнение активных сим-карт
    """
    try:
        logging.info(msg='Start main:morning_check()')
        mts_get_account_balance()
        check_sim_cards_in_dj(msg_chat_id=configs.telegram_job_id)
        mts_check_num_balance()
        check_mts_sim_cards(msg_chat_id=configs.telegram_job_id)
        check_diff_terminals(msg_chat_id=configs.telegram_job_id)
        check_glonasssoft_dj_objects(msg_chat_id=configs.telegram_job_id)
        check_active_mts_sim_cards()
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def schedule_main():
    try:
        schedule.every().day.at('06:00', timezone(configs.timezone_my)).do(morning_check)
        schedule.every().hour.at(':00').do(mts_check_num_balance, critical=True)
        schedule.every().day.at('09:00', timezone(configs.timezone_my)).do(check_email)
        schedule.every().day.at('15:00', timezone(configs.timezone_my)).do(check_email)
        schedule.every().day.at('21:00', timezone(configs.timezone_my)).do(check_email)

        while True:
            schedule.run_pending()
            time.sleep(1)

    except Exception as err:
        logging.error(msg='', exc_info=err)


@bot.message_handler(content_types=['photo'], func=lambda message: message.chat.type in ['group', 'supergroup'])
def handler_group_photo(message):
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = Image.open(BytesIO(bot.download_file(file_info.file_path)))
    decoded = decode(downloaded_file)
    result = [code.data.decode("utf-8") for code in decoded]
    if result:
        bot.send_message(
            message.chat.id,
            text='\n'.join(result),
            business_connection_id=message.business_connection_id
        )


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
        text = (
            '1. Можно вводить команды, не дожидаясь завершения другой\n'
            '2. Можно вводить номера через 7, 8 или без первой цифры, т.е. 79998887766, 89998887766, 9998887766\n'
            '3. Можно вводить команду с несколькими номерами, '
            'нужно вводить их в столбик, без дополнительных знаков. Например:\n'
            '9998887766\n'
            '79998887766\n'
            '89998887766\n'
            '4. "Разблокировка рандом" разблокирует номера в диапазоне 3-12 часов после отправки команды\n'
        )
        bot.send_message(
            message.chat.id,
            text=text,
            reply_markup=keyboard_main
        )
    elif message.chat.id in install_telegram_id:
        bot.send_message(
            message.chat.id,
            text='Лови клавиатуру',
            reply_markup=keyboard_install
        )
    else:
        bot.send_message(chat_id=message.chat.id, text='В другой раз')


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if 'get_numbers_date' in call.data:
        get_list_date_sim_cards(call.message)
    elif 'get_numbers_id_payer' in call.data:
        get_number_payer_sim_cards(call.message)

    elif 'get_stock' in call.data:
        get_stock_handler(call.message, call.data)

    elif 'check_numbers' in call.data:
        check_mts_sim_cards(call.message.chat.id)
    elif 'check_overspend_sim_cards' in call.data:
        mts_check_num_balance()
    elif 'check_active_sim_cards' in call.data:
        check_active_mts_sim_cards(call.message.chat.id)
    elif 'check_glonasssoft' in call.data:
        check_glonasssoft_dj_objects(call.message.chat.id)
    elif 'check_lost_trackers' in call.data:
        check_diff_terminals(call.message.chat.id)
    elif 'check_sim_cards_in_dj' in call.data:
        check_sim_cards_in_dj(call.message.chat.id)
    elif 'check_upload_mega_exel' in call.data:
        request_upload_mega_exel(call.message)
    elif 'check_upload_sim2m_exel' in call.data:
        request_upload_sim2m_exel(call.message)

    elif 'mts_activate_num_now' in call.data:
        mts_request_numbers(call.message, target_func=api_mts.del_block)
    elif 'mts_activate_num_random' in call.data:
        mts_request_numbers(call.message, target_func=api_mts.del_block_random_hours)

    elif 'mts_exchange_sim_next_number' in call.data:
        mts_exchange_sim(call.message)
    elif 'mts_exchange_sim_input_number' in call.data:
        mts_exchange_sim_input_number(call.message)
    elif 'mts_yes_exchange_sim' in call.data:
        mts_yes_exchange_sim(call.message, call.data)
    elif 'mts_block_exchange_sim' in call.data:
        mts_block_exchange_sim(call.message, call.data)

    elif 'payment_choice_id' in call.data:
        payment_request_payer_id(call.message)
    elif 'payment_choice_msg' in call.data:
        payment_request_payer_msg(call.message)
    elif 'payment_change_date' in call.data:
        payment_change_date(call.message, call.data)
    elif 'payment_custom_date' in call.data:
        payment_request_custom_date(call.message, call.data)
    elif 'payment_get_sim_cards_payers' in call.data:
        get_list_payer_sim_cards(call.message, payer_id=call.data.split()[1])

    elif 'get_price' in call.data:
        get_price_type(call.message, call.data)

    elif 'schedule' in call.data:
        schedule_get_human(call.message, call.data)


@bot.message_handler(content_types=['text'])
def take_text(message):
    if check_user(message) or message.chat.id in install_telegram_id:
        if message.text.lower() == commands[0].lower():
            mts_request_number(message)
        elif message.text.lower() == commands[1].lower():
            mts_activate_num_choice(message)
        elif message.text.lower() == commands[2].lower():
            mts_request_numbers(message, target_func=api_mts.add_block)
        elif message.text.lower() == commands[3].lower():
            mts_exchange_choice_get_number(message)
        elif message.text.lower() == commands[4].lower():
            get_list_vacant_sim_cards(message)
        elif message.text.lower() == commands[5].lower():
            get_numbers_payer_or_date(message)
        elif message.text.lower() == commands[6].lower():
            payment_request_data_payer(message)
        elif message.text.lower() == commands[7].lower():
            checks(message)
        elif message.text.lower() == commands[8].lower():
            schedule_request_date(message)
        elif message.text.lower() == commands[9].lower():
            get_stock(message)
        elif message.text.lower() == commands[10].lower():
            get_price(message)
        else:
            logging.warning(f'func take_text: not understand question: {message.text}')
            bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')


if __name__ == '__main__':
    threading.Thread(target=schedule_main).start()
    bot.infinity_polling()

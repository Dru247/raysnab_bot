import api_dj
import api_glonasssoft
import api_mts
import datetime
import calendar
import configs
import imaplib
import logging
import schedule
import sqlite3 as sq
import time
import threading

from dateutil.relativedelta import relativedelta
# from io import BytesIO
from pytz import timezone
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
    'Замена сим-карты',
    'Список болванок МТС',
    'Список СИМ-карт',
    'Оплата',
    'Проверки'
]
keyboard_main = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
keyboard_main.add(*[types.KeyboardButton(comm) for comm in commands])


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
    except Exception:
        logging.critical(msg="func check_user - error", exc_info=True)


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
    except Exception:
        logging.critical(msg="func check_number - error", exc_info=True)


def check_date(date_target):
    """Проверяет дату"""
    try:
        date_target = datetime.datetime.strptime(date_target, '%Y-%m-%d')
        return isinstance(date_target, datetime.date)
    except Exception:
        logging.critical(msg="func check_date - error", exc_info=True)


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
    except Exception:
        logging.critical(msg="func cut_msg_telegram - error", exc_info=True)


def mts_request_number(message):
    """Запрашивает номер симки"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Введи номер сим-карты")
        bot.register_next_step_handler(message=msg, callback=mts_block_info)
    except Exception:
        logging.critical(msg="func mts_request_number - error", exc_info=True)


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
                msg_text = "Добровольная блокировка отсутвует"
        else:
            msg_text = "Неверный формат номера"
        bot.send_message(chat_id=message.chat.id, text=msg_text)
    except Exception:
        logging.critical(msg="func mts_block_info - error", exc_info=True)


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
    except Exception:
        logging.critical(msg="func mts_request_numbers - error", exc_info=True)


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
                final_list.append((False, number_old, 'Ошибка - Номер некорректен"'))
            else:
                success, response_text = target_func(number)
                if success:
                    successfully_requests.append((success, number, response_text))
                else:
                    final_list.append((success, number, response_text))
                time.sleep(1)

        for success, num, event_id_request in successfully_requests:
            success, response_text = api_mts.check_status_request(event_id_request)
            final_list.append((success, num, response_text))

        final_list.sort(key=lambda a: a[0])
        text_msg = 'Результат запроса:\n'
        for record in final_list:
            text_msg += f'{record[1]} - {record[2]}\n'

        bot.send_message(message.chat.id, text=text_msg)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def mts_exchange_sim(message):
    """Выводит первый номер для замены МТС и спрашивает про ICC ID"""
    try:
        number, num_date = api_dj.get_first_number_for_change()
        bot.send_message(chat_id=message.chat.id, text=f'Номер: {number}\nДата: {num_date}')
        msg = bot.send_message(chat_id=message.chat.id, text="Введи последние 4е знака ICC ID")
        bot.register_next_step_handler(message=msg, callback=mts_exchange_sim_second, number=number)
    except Exception as err:
        logging.critical(msg="func mts_exchange_sim - error", exc_info=err)


def mts_exchange_sim_second(message, number):
    try:
        last_iccid = message.text
        if last_iccid.isdigit():
            error, result, text = api_mts.get_vacant_sim_card_exchange(number, last_iccid)
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
        _, result, _ = api_mts.get_block_info(number)
        if result:
            api_mts.del_block(number)
        result, text = api_mts.get_exchange_sim_card(number, imsi)
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
        response = api_mts.add_block(number)
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
    except Exception:
        logging.critical(msg="func mts_get_account_balance - error", exc_info=True)


def mts_check_num_balance(msg_chat_id=None, critical=False):
    """Проверяет номера МТС на КРИТИЧЕСКИЙ перерасход и отправляет сотрудникам в чат"""
    try:
        if critical:
            balance = configs.critical_balance
        else:
            balance = configs.warning_balance
        records = api_mts.get_balance_numbers(balance)
        if records:
            records.sort(key=lambda a: a[1], reverse=True)
            msg_text = 'МТС Перерасход:'
            overspending = 0
            for record in records:
                number, sim_balance = record
                msg_text += f'\n{number} - {sim_balance}'
                overspending += sim_balance - balance
            msgs = cut_msg_telegram(msg_text)
            if critical:
                with sq.connect(configs.database) as con:
                    cur = con.cursor()
                    cur.execute('SELECT data FROM contacts WHERE contact_type = 3')
                    result = cur.fetchall()
                    chats = [chat[0] for chat in result]
                for chat in chats:
                    for msg in msgs:
                        bot.send_message(chat_id=chat, text=msg)
            else:
                for msg in msgs:
                    bot.send_message(chat_id=msg_chat_id, text=msg)
                bot.send_message(chat_id=msg_chat_id, text=f'Общий перерасход: {overspending}')


    except Exception as err:
        logging.critical(msg='', exc_info=err)
        bot.send_message(
            chat_id=configs.telegram_my_id,
            text='Ошибка проверки критического баланса МТС'
        )


def check_email(imap_server=configs.imap_server_yandex, email_login=configs.ya_mary_email_login, email_password=configs.ya_mary_email_password, teleg_id=configs.id_telegram_mary):
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
    except Exception:
        logging.error("func get_numbers_payer_or_date - error", exc_info=True)


def get_number_payer_sim_cards(message):
    """Запрашивает номер плательщика"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text="Напиши ID плательщика")
        bot.register_next_step_handler(message=msg, callback=get_list_payer_sim_cards)
    except Exception:
        logging.error("func get_payer_sim_cards - error", exc_info=True)


def get_list_payer_sim_cards(message):
    """Отправляет сообщение со списком номеров сим-карт по плательщику"""
    try:
        id_payer = int(message.text)
        sim_cards = api_dj.get_payer_sim_cards(id_payer)
        for sim_list in sim_cards:
            bot.send_message(
                chat_id=message.chat.id,
                text='\n'.join(sim_list)
            )
    except Exception:
        logging.error("func get_list_payer_sim_cards - error", exc_info=True)


def get_list_date_sim_cards(message):
    """Запрашивает дату"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Напиши дату в формате "2000-12-31"')
        bot.register_next_step_handler(message=msg, callback=get_list_date_sim_cards_handler)
    except Exception:
        logging.error("func get_list_date_sim_cards - error", exc_info=True)


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
    except Exception:
        logging.critical(msg="func get_list_vacant_sim_cards - error", exc_info=True)


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
    except Exception:
        logging.critical(msg="func check_mts_sim_cards - error", exc_info=True)


def check_active_mts_sim_cards(msg_chat_id, morning=False):
    """Сравнивает активные сим-карты на проекте и на МТС"""
    try:
        if not morning:
            bot.send_message(chat_id=msg_chat_id, text='Проверка запущена. Займёт ~1,5 часа')
        dj_mts_sim_cards = set(api_dj.get_all_active_sim_cards())
        numbers_in_hands = {num['contact_rec'] for num in api_dj.api_request_human_contacts()}
        site_mts_sim_cards = set(api_mts.get_all_active_sim_cards())
        site_mts_sim_cards -= numbers_in_hands # убираем активные сим-карты на руках и с тарифами
        sim_cards = dj_mts_sim_cards ^ site_mts_sim_cards
        msg_text = 'Разница блокировки СИМ-карт:\n' + '\n'.join(sim_cards)
        for msg_one in cut_msg_telegram(msg_text):
            bot.send_message(
                chat_id=msg_chat_id,
                text=msg_one
            )
    except Exception as err:
        logging.critical(msg='func check_active_mts_sim_cards - error', exc_info=err)


def check_glonasssoft_dj_objects(msg_chat_id):
    """Выдаёт разницу объектов на CLONASSSoft"""
    try:
        glonasssoft_objs = [obj.get('imei') for obj in api_glonasssoft.request_list_objects(configs.glonasssoft_org_id)]
        user_list_target_serv = [user.get('id') for user in api_dj.api_request_user_list() if user.get('server') == 4]
        project_objs = [obj.get('terminal') for obj in api_dj.api_request_object_list() if obj.get('wialon_user') in user_list_target_serv and obj.get('active')]
        terminals = {term.get('id'): term.get('imei') for term in api_dj.api_request_terminal_list()}
        result = set(glonasssoft_objs) ^ set([terminals[obj] for obj in project_objs])
        msg_text = 'Разница трекеров GLONASSSoft:\n' + '\n'.join(result)
        bot.send_message(chat_id=msg_chat_id,  text=msg_text)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def payment_request_data_payer(message):
    """Запрашивает способ определения плательщика"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='По ID',
                callback_data=f'payment_choice_id'
            ),
            types.InlineKeyboardButton(
                text='По сообщению',
                callback_data=f'payment_choice_msg'
            ),
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text='Выбери способ определения плательщика',
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func payment_request_data_payer - error", exc_info=True)


def payment_request_payer(message, call_data):
    """Запрашивает ID плательщика у которого нужно зарегистрировать платёж в объектах"""
    try:
        if call_data == 'payment_choice_msg':
            msg_text = 'Перешли сообщение плательщика'
            msg_payer = 1
        else:
            msg_payer = 0
            msg_text = 'Напиши ID плательщика'
        msg = bot.send_message(chat_id=message.chat.id, text=msg_text)
        bot.register_next_step_handler(message=msg, callback=payment_request_date, msg_payer=msg_payer)
    except Exception:
        logging.critical(msg="func payment_request_payer - error", exc_info=True)


def payment_request_date(message, msg_payer):
    """Выбор даты оплаченного периода"""
    try:
        if msg_payer:
            tele_id_payer = message.forward_from.id
            payer_id = api_dj.get_human_for_from_teleg_id(tele_id_payer)
            if not payer_id:
                bot.send_message(chat_id=message.chat.id, text=f'{tele_id_payer} - не зарегистрирован')
                return
            else:
                bot.send_message(chat_id=message.chat.id, text=f'Telegram ID: {tele_id_payer}')
        else:
            payer_id = message.text
        date_target = datetime.date.today() + relativedelta(months=+1)
        last_day = calendar.monthrange(date_target.year, date_target.month)[1]
        date_target = date_target.strftime(f'%Y-%m-{last_day}')
        inline_keys = [
            types.InlineKeyboardButton(
                text=date_target,
                callback_data=f'payment_change_date {payer_id} {date_target}'
            ),
            types.InlineKeyboardButton(
                text='Произвольная дата',
                callback_data=f'payment_custom_date {payer_id}'
            ),
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys)
        bot.send_message(
            message.from_user.id,
            text='Выбери дату',
            reply_markup=keyboard)
    except Exception:
        logging.critical(msg="func payment_request_date - error", exc_info=True)


def payment_request_custom_date(message, call_data):
    """Запрашивает произвольную дату"""
    try:
        msg = bot.send_message(chat_id=message.chat.id, text='Введи дату в формате "2000-01-31"')
        bot.register_next_step_handler(message=msg, callback=payment_change_date, call_data=call_data)
    except Exception:
        logging.critical(msg="func payment_request_custom_date - error", exc_info=True)


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
            bot.send_message(message.chat.id, text='Успех')
    except Exception as err:
        logging.critical(msg="func payment_change_date - error", exc_info=err)


def check_diff_terminals(msg_chat_id):
    """Возвращает список потерянных терминалов"""
    try:

        diff_trackers_all_vs_install_and_on_hands, diff_trackers_on_hands_and_obj = api_dj.get_diff_terminals()
        msg_text = 'Потерянные трекеры:\n' + '\n'.join(diff_trackers_all_vs_install_and_on_hands)
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


def checks(message):
    """Выдаёт список проверок"""
    try:
        inline_keys = [
            types.InlineKeyboardButton(
                text='Проверка номеров',
                callback_data=f'check_numbers'
            ),
            types.InlineKeyboardButton(
                text='Проверка перерасхода СИМ-карт',
                callback_data=f'check_overspend_sim_cards'
            ),
            types.InlineKeyboardButton(
                text='Проверка блокировок СИМ-карт',
                callback_data=f'check_active_sim_cards'
            ),
            types.InlineKeyboardButton(
                text='Проверка объектов GLONASSsoft',
                callback_data=f'check_glonasssoft'
            ),
            types.InlineKeyboardButton(
                text='Потерянные трекеры',
                callback_data=f'check_lost_trackers'
            )
        ]
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(*inline_keys, row_width=1)
        msg_text = (
            '"Проверка номеров" - разница номеров и ICC ID на проекте и на сайте МТС\n'
            '"Проверка перерасхода СИМ-карт" - сим-карты с расходом более 28 руб.\n'
            '"Проверка блокировок СИМ-карт" - разница активных номеров на проекте и сайте МТС (~1,5 часа)\n'
            '"Проверка объектов GLONASSsoft" - разница активных объектов на проекте и GLONASSSoft\n'
            '"Потерянные трекеры" - трекеры без установок и не на руках'
        )
        bot.send_message(
            chat_id=message.chat.id,
            text=msg_text,
            reply_markup=keyboard)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def morning_check():
    """
    Утренний скрипт:
    1. проверка баланса ЛС,
    2. проверка перерасхода номеров,
    3. проверка наличие сим-карт на проекте и МТС,
    4. сравнение активных сим-карт
    """
    try:
        mts_get_account_balance()
        mts_check_num_balance(msg_chat_id=configs.telegram_my_id)
        check_mts_sim_cards(msg_chat_id=configs.telegram_job_id)
        check_diff_terminals(msg_chat_id=configs.telegram_job_id)
        check_glonasssoft_dj_objects(msg_chat_id=configs.telegram_job_id)
        check_active_mts_sim_cards(msg_chat_id=configs.telegram_job_id, morning=True)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def schedule_main():
    try:
        schedule.every().day.at("06:00", timezone(configs.timezone_my)).do(morning_check)
        schedule.every().hour.at(":00").do(mts_check_num_balance, crirtical=True)
        schedule.every().day.at("09:00", timezone(configs.timezone_my)).do(check_email)
        schedule.every().day.at("15:00", timezone(configs.timezone_my)).do(check_email)
        schedule.every().day.at("21:00", timezone(configs.timezone_my)).do(check_email)

        while True:
            schedule.run_pending()
            time.sleep(1)

    except Exception as err:
        logging.error(msg='', exc_info=err)


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
    else:
        bot.send_message(chat_id=message.chat.id, text='В другой раз')


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if 'get_numbers_date' in call.data:
        get_list_date_sim_cards(call.message)
    elif 'get_numbers_id_payer' in call.data:
        get_number_payer_sim_cards(call.message)

    elif 'check_numbers' in call.data:
        check_mts_sim_cards(call.message.chat.id)
    elif 'check_overspend_sim_cards' in call.data:
        mts_check_num_balance(msg_chat_id=call.message.chat.id)
    elif 'check_active_sim_cards' in call.data:
        check_active_mts_sim_cards(call.message.chat.id)
    elif 'check_glonasssoft' in call.data:
        check_glonasssoft_dj_objects(call.message.chat.id)
    elif 'check_lost_trackers' in call.data:
        check_diff_terminals(call.message.chat.id)

    elif 'mts_activate_num_now' in call.data:
        mts_request_numbers(call.message, target_func=api_mts.del_block)
    elif 'mts_activate_num_random' in call.data:
        mts_request_numbers(call.message, target_func=api_mts.del_block_random_hours)

    elif 'mts_yes_exchange_sim' in call.data:
        mts_yes_exchange_sim(call.message, call.data)
    elif 'mts_no_exchange_sim' in call.data:
        mts_exchange_no(call.message)
    elif 'mts_block_exchange_sim' in call.data:
        mts_block_exchange_sim(call.message, call.data)
    elif 'mts_noblock_exchange_sim' in call.data:
        mts_exchange_no(call.message)

    elif 'payment_change_date' in call.data:
        payment_change_date(call.message, call.data)
    elif 'payment_choice' in call.data:
        payment_request_payer(call.message, call.data)
    elif 'payment_custom_date' in call.data:
        payment_request_custom_date(call.message, call.data)


@bot.message_handler(content_types=['text'])
def take_text(message):
    if check_user(message):
        if message.text.lower() == commands[0].lower():
            mts_request_number(message)
        elif message.text.lower() == commands[1].lower():
            mts_activate_num_choice(message)
        elif message.text.lower() == commands[2].lower():
            mts_request_numbers(message, target_func=api_mts.add_block)
        elif message.text.lower() == commands[3].lower():
            mts_exchange_sim(message)
        elif message.text.lower() == commands[4].lower():
             get_list_vacant_sim_cards(message)
        elif message.text.lower() == commands[5].lower():
            get_numbers_payer_or_date(message)
        elif message.text.lower() == commands[6].lower():
             payment_request_data_payer(message)
        elif message.text.lower() == commands[7].lower():
             checks(message)
        else:
            logging.warning(f'func take_text: not understand question: {message.text}')
            bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')
    else:
        bot.send_message(chat_id=message.chat.id, text="В другой раз")


if __name__ == '__main__':
    threading.Thread(target=schedule_main).start()
    bot.infinity_polling()

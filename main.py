import config
import imaplib
import logging
import schedule
import sqlite3 as sq
import telebot
import threading
import time

from pytz import timezone


logging.basicConfig(
    level=logging.INFO,
    filename="logs.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s")
schedule_logger = logging.getLogger('schedule')
schedule_logger.setLevel(level=logging.DEBUG)

bot = telebot.TeleBot(config.telegram_token)


def check_email(imap_server, email_login, email_password):
    try:
        mailbox = imaplib.IMAP4_SSL(imap_server)
        mailbox.login(email_login, email_password)
        mailbox.select()
        unseen_msg = mailbox.uid('search', "UNSEEN", "ALL")
        id_unseen_msgs = unseen_msg[1][0].decode("utf-8").split()
        logging.info(msg=f"{email_login}: {id_unseen_msgs}")
        with sq.connect(config.database) as con:
            cur = con.cursor()
            cur.execute(f"UPDATE emails SET unseen_status = {len(id_unseen_msgs)} WHERE email = '{email_login}'")
    except Exception:
        logging.error("func check email - error", exc_info=True)


def schedule_main():
    schedule.every().day.at(
        "09:00",
        timezone(config.timezone_my)
        ).do(check_email)
    schedule.every().day.at(
        "15:00",
        timezone(config.timezone_my)
        ).do(check_email)
    schedule.every().day.at(
        "20:00",
        timezone(config.timezone_my)
        ).do(check_email)

    while True:
        schedule.run_pending()
        time.sleep(1)


@bot.message_handler(content_types=['text'])
def take_text(message):
    logging.warning(
       f"func take_text: not understend question: {message.text}")
    bot.send_message(message.chat.id, 'Я не понимаю, к сожалению')


if __name__ == "__main__":
    threading.Thread(target=schedule_main).start()
    bot.infinity_polling()

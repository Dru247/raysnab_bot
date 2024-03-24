import os

from dotenv import load_dotenv


load_dotenv()

telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_my_id = os.getenv("TELEGRAM_MY_ID")
mts_login = os.getenv("MTS_LOGIN")
mts_password = os.getenv("MTS_PASSWORD")
database = "raysnab.db"
timezone_my = "Europe/Moscow"

imap_yandex = "imap.yandex.ru"
email_passwords = [
    os.getenv("PASSWORD_EMAIL_ALEHTIN")
]

import os

from dotenv import load_dotenv


load_dotenv()

telegram_token = os.getenv("TELEGRAM_TOKEN")
telegram_my_id = os.getenv("TELEGRAM_MY_ID")
mts_login = os.getenv("MTS_LOGIN")
mts_password = os.getenv("MTS_PASSWORD")
mts_number = os.getenv("MTS_NUMBER")
database = "raysnab.db"
timezone_my = "Europe/Moscow"

imap_yandex = "imap.yandex.ru"
email_passwords = [
    os.getenv("PASSWORD_EMAIL_ALEHTIN")
]
warning_balance = 100
critical_balance = 1000
imap_server_yandex = "imap.yandex.ru"
ya_mary_email_login = os.getenv("YA_EMAIL_MARY_LOGIN")
ya_mary_email_password = os.getenv("YA_EMAIL_MARY_PASSWORD")
id_teleg_mary = os.getenv("TELEG_ID_MARY")

import os

from dotenv import load_dotenv


load_dotenv()

telegram_token = os.getenv('TELEGRAM_TOKEN')
database = "raysnab.db"
timezone_my = "Europe/Moscow"
imap_yandex = "imap.yandex.ru"
email_passwords = [
    os.getenv("PASSWORD_EMAIL_ALEHTIN")
]

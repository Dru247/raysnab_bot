import os

from dotenv import load_dotenv


load_dotenv()

telegram_token = os.getenv('TELEGRAM_TOKEN')
telegram_my_id = os.getenv('TELEGRAM_MY_ID')
telegram_maks_id = os.getenv('TELEGRAM_MAKS_ID')
telegram_sister_id = os.getenv('TELEGRAM_SISTER_ID')
telegram_job_id = os.getenv('TELEGRAM_JOB_ID')
telegram_malashin_id = os.getenv('TELEGRAM_MALASHIN_ID')
telegram_sumbulov_id = os.getenv('TELEGRAM_SUMBULOV_ID')
telegram_my_930_id = os.getenv('TELEGRAM_MY_930_ID')
id_telegram_mary = os.getenv('TELEGRAM_ID_MARY')

MTS_API_REQUEST_TIMEOUT = 10
MTS_ACCOUNT = os.getenv('MTS_ACCOUNT')
MTS_LOGIN = os.getenv('MTS_LOGIN')
MTS_PASSWORD = os.getenv('MTS_PASSWORD')
MTS_MAIN_NUMBER = os.getenv('MTS_MAIN_NUMBER')
MTS_TIME_LIVE_TOKEN = os.getenv('MTS_TIME_LIVE_TOKEN')
MTS_URL_API = 'https://api.mts.ru/'

DB = 'raysnab.db'
timezone_my = 'Europe/Moscow'

imap_yandex = 'imap.yandex.ru'
email_passwords = [
    os.getenv('PASSWORD_EMAIL_ALEHTIN')
]
imap_server_yandex = 'imap.yandex.ru'
ya_mary_email_login = os.getenv('YA_EMAIL_MARY_LOGIN')
ya_mary_email_password = os.getenv('YA_EMAIL_MARY_PASSWORD')
token_drf = os.getenv('TOKEN_DRF')
glonasssoft_login = os.getenv('GLONASSSOFT_LOGIN')
glonasssoft_password = os.getenv('GLONASSSOFT_PASSWORD')
glonasssoft_org_id = os.getenv('GLONASSSOFT_ORG_ID')
glonasssoft_user_id= os.getenv('GLONASSSOFT_USER_ID')
bus_id= os.getenv('XSmRY3imyEiKDgAAppxR1B0kTGs')

import configs
import time
from distutils.command.config import config

import requests


gl_token = ''

def get_token():
    """Запрос нового токена"""
    time.sleep(1)
    url = 'https://hosting.glonasssoft.ru/api/v3/auth/login'
    js_data = {
        "login": configs.glonasssoft_login,
        "password": configs.glonasssoft_password
    }
    response = requests.post(
        url=url,
        json=js_data
    ).json()
    time.sleep(1)
    return response.get('AuthId')


def check_auth():
    """Проверка статуса авторизации"""
    time.sleep(1)
    url = 'https://hosting.glonasssoft.ru/api/v3/auth/check'
    global gl_token
    headers = {
        "X-Auth": gl_token
    }
    response = requests.get(
        url=url,
        headers=headers
    )
    if response.status_code != requests.codes.ok:
        time.sleep(1)
        gl_token = get_token()
    time.sleep(1)
    return gl_token


def request_list_objects(id_organization):
    """Запрос на список объектов"""
    time.sleep(1)
    token = check_auth()
    url = 'https://hosting.glonasssoft.ru/api/v3/vehicles/find'
    headers = {
        "X-Auth": token
    }
    js_data = {
        "parentId": id_organization
    }
    response = requests.post(
        url=url,
        headers=headers,
        json=js_data
    ).json()
    time.sleep(1)
    return response

"""MTS API."""
import datetime
import logging
import random
import sqlite3 as sq
import time
from collections import namedtuple
from math import ceil as math_ceil

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from classes import ApiMtsResponse, Number, SimCard
from configs import (DB, MTS_ACCOUNT, MTS_API_REQUEST_TIMEOUT, MTS_LOGIN,
                     MTS_PASSWORD, MTS_MAIN_NUMBER, MTS_TIME_LIVE_TOKEN,
                     MTS_URL_API)

BLOCK_SERVICE_NUMBER = 'BL0005'
FIRST_BLOCK_SERVICE_NUMBER = 'BL0008'


def timer_sleep(func):
    """Таймер сна между запросами к API."""
    def wrapper(*args, **kwargs):
        time.sleep(1.1)
        return func(*args, **kwargs)

    return wrapper


def exception_handler(func):
    """Обработчик исключений."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as err:
            logging.critical('Error', exc_info=err)
            return None

    return wrapper


@exception_handler
@timer_sleep
def request_new_token(session):
    """Запрашивает новый Токен, удаляет старый из БД."""
    url = MTS_URL_API + 'token'
    response = session.post(url=url, timeout=MTS_API_REQUEST_TIMEOUT)
    return response.json().get('access_token')


@exception_handler
def get_token():
    """Проверяет действующий Токен на актуальность по дате."""
    with sq.connect(DB) as con:
        cur = con.cursor()
        cur.execute(
            '''
            SELECT token FROM tokens
            WHERE datetime_creation > datetime('now', '-1 day')
            '''
        )
        result = cur.fetchone()
    if result:
        return result[0]
    with requests.Session() as session:
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        session.auth = MTS_LOGIN, MTS_PASSWORD
        session.params = {
            'grant_type': 'client_credentials',
            'validity_period': MTS_TIME_LIVE_TOKEN
        }
        token = request_new_token(session=session)

    with sq.connect(DB) as con:
        cur = con.cursor()
        cur.execute('DELETE FROM tokens')
        cur.execute(
            'INSERT INTO tokens (token) VALUES (?)',
            (token,)
        )
    return token


@exception_handler
def get_balance():
    """Возвращает баланс аккаунта. API запрос."""
    url = (f'{MTS_URL_API}b2b/v1/Bills/CheckBalanceByAccount?'
           f'fields=MOAF&accountNo={MTS_ACCOUNT}')
    token = get_token()
    with requests.Session() as session:
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        response = session.get(
            url=url,
            timeout=MTS_API_REQUEST_TIMEOUT
        )
    return (response.json()[0].get('customerAccountBalance')[0]
            .get('remainedAmount').get('amount'))


@exception_handler
@timer_sleep
def get_status_request(session, event_id):
    """Запрос на статус прошедшей операции."""
    url = MTS_URL_API + 'b2b/v1/Product/CheckRequestStatusByUUID'
    js_data = {
        "relatedParty": [
            {"characteristic": []},
            {"id": event_id}
        ],
        "validFor": {}
    }
    response = session.post(
        url=url,
        json=js_data,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.json()


@exception_handler
def check_status_request(session, number):
    """Проверка статуса выполнения API запроса."""
    event_id = number.api_response.text
    statuses = ['Faulted', 'Completed', 'InProgress']
    check_status = statuses[2]
    check_text = str()
    check_attempt = 60
    count_attempts = 0

    while check_status == statuses[2] and count_attempts <= check_attempt:
        result = get_status_request(session, event_id)
        check_status = result.get('relatedParty')[0].get('status')
        check_text = (result.get('relatedParty')[0]
                      .get('characteristic')[-1].get('value'))
        count_attempts += 1

    if count_attempts > check_attempt:
        number.api_response.success = False
        number.api_response.text = 'Превышен лимит проверок статуса обращения'
    elif check_status == statuses[0]:
        number.api_response.success = False
        number.api_response.text = check_text
    elif check_status == statuses[1]:
        number.api_response.success = True
        number.api_response.text = 'Положительный ответ от сервера'
    else:
        number.api_response.success = False
        number.api_response.text = 'Неизвестная ошибка'
        logging.warning(
            f'check_status_request: {event_id};{check_status};'
            f'{check_text};{count_attempts}'
        )


@timer_sleep
@exception_handler
def change_service_request(session, number, service_id, action):
    """API Запрос на изменение сервиса в номере."""
    url = f'{MTS_URL_API}b2b/v1/Product/ModifyProduct?msisdn={number}'
    js_data = {
        "characteristic": [{"name": "MobileConnectivity"}],
        "item": [{
            "action": action,
            "product": {
                "externalID": service_id,
                "productCharacteristic": [{
                    "name": "ResourceServiceRequestItemType",
                    "value": "ResourceServiceRequestItem"
                }]
            }
        }]
    }
    response = session.post(
        url=url,
        json=js_data,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.json()


@exception_handler
def change_service_handler(session, number, service_id, action):
    """Обработчик запроса на изменение сервиса в номере."""
    result = change_service_request(session, number.number, service_id, action)
    if 'fault' in result:
        logging.info(f'change_service error - response: {result}')
        return ApiMtsResponse(success=False, text='Неверный запрос')
    return ApiMtsResponse(success=True, text=result.get('eventID'))


@exception_handler
def turn_service_numbers(numbers: list | Number, add_service, service_id=None):
    """Алгоритм обработки нескольких номеров на изменение сервиса."""
    if service_id is None:
        service_id = BLOCK_SERVICE_NUMBER
    if not isinstance(numbers, list):
        numbers = [numbers]

    token = get_token()
    with requests.Session() as session:
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        for number in numbers:
            if add_service:
                action = 'create'
            else:
                action = 'delete'

            number.api_response = change_service_handler(
                session, number, service_id, action
            )

        session.headers.update({'Content-Type': 'application/json'})

        for number in numbers:  # Проверяет EventID у успешных запросов
            if number.api_response.success:
                check_status_request(session, number)


@timer_sleep
@exception_handler
def change_service_later_request(
        session,
        number,
        service_id,
        action,
        dt_action
):
    """API Запрос на изменение сервиса в номере с отсрочкой."""
    url = f'{MTS_URL_API}b2b/v1/Product/ModifyProduct?msisdn={number}'
    js_data = {
        "characteristic": [{"name": "MobileConnectivity"}],
        "item": [{
            "action": action,
            "actionDate": dt_action,
            "product": {
                "externalID": service_id,
                "productCharacteristic": [{
                    "name": "ResourceServiceRequestItemType",
                    "value": "DelayedResourceServiceRequestItem"
                }]
            }
        }]
    }
    response = session.post(
        url=url,
        json=js_data,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.json()


@exception_handler
def change_service_later_handler(
        session, number, service_id, action, dt_action
):
    """Обработчик запроса на изменение сервиса в номере с отсрочкой."""
    result = change_service_later_request(
        session, number.number, service_id, action, dt_action
    )
    response = ApiMtsResponse(
        success=None,
        text=None
    )
    if 'fault' in result:
        logging.info(
            f'change_service_later error: {number.number} result: {result}'
        )
        response.success = False
        response.text = 'Неверный запрос'
    else:

        response.success = True
        response.text = result.get('eventID')

    number.api_response = response


@exception_handler
def turn_service_numbers_later(
        numbers, add_service, service_id=None, dt_action=None
):
    """Алгоритм обработки нескольких номеров на изменение сервиса по дате."""
    if not isinstance(numbers, list):
        numbers = [numbers]

    if service_id is None:
        service_id = BLOCK_SERVICE_NUMBER

    token = get_token()
    with requests.Session() as session:
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        for number in numbers:
            if dt_action is None:
                dt_action = datetime.datetime.now() + datetime.timedelta(
                    hours=random.randint(3, 12)
                )
                dt_action = dt_action.isoformat()

            if add_service:
                action = 'create'
            else:
                action = 'delete'

            change_service_later_handler(
                session, number, service_id, action, dt_action
            )


@exception_handler
@timer_sleep
def request_list_numbers(session, page_num):
    """API запрос списка ICC + Number."""
    page_size = 1000
    url = (MTS_URL_API + 'b2b/v1/Service/HierarchyStructure'
           f'?account={MTS_ACCOUNT}&pageNum={page_num}&pageSize={page_size}')
    response = session.get(
        url=url,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.json()


@exception_handler
def get_list_numbers_class() -> list:
    """Возвращает полный список Номеров с СИМ-картами."""
    token = get_token()
    pagination = True
    numbers = list()
    page_num = 1

    with requests.Session() as session:
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        while pagination:
            response = request_list_numbers(
                session=session,
                page_num=page_num
            )
            try:
                pagination = (response[0].get('partyRole')[0]
                              .get('customerAccount')[0].get('href'))
            except Exception as err:
                logging.critical(
                    f'Pagination error. Response :{response}',
                    exc_info=err
                )
            js_nums = (response[0].get('partyRole')[0]
                       .get('customerAccount')[0].get('productRelationship'))
            for number in js_nums:
                numbers.append(
                    Number(
                        number=(number.get('product')
                                .get('productSerialNumber')),
                        sim_card=SimCard(
                            icc=(number.get('product')
                                 .get('productCharacteristic')[1].get('value'))
                        )
                    )
                )
            page_num += 1

        return numbers


@exception_handler
@timer_sleep
def request_vacant_sim_cards(icc_id=''):
    """API запрос списка сим-карт без номера (болванка)."""
    token = get_token()
    url = MTS_URL_API + 'b2b/v1/Resources/GetAvailableSIM'
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': '*/*'
    }
    js_data = {"Msisdn": MTS_MAIN_NUMBER, "SearchPattern": f"%{icc_id}"}
    response = requests.post(
        url=url,
        headers=headers,
        json=js_data,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.json()


@exception_handler
def get_vacant_sim_cards():
    """Выдаёт обработанный список сим-карт."""
    return [
        SimCard(icc=sim_card.get('iccId')) for sim_card
        in request_vacant_sim_cards().get('simList')
    ]


@exception_handler
def get_list_all_mts_sim_cards():
    """Возвращает полный список СИМ-карт (+болванки)."""
    return get_list_numbers_class() + get_vacant_sim_cards()


@exception_handler
def get_vacant_sim_card_exchange(icc_id):
    """Обработчик поиска пустой СИМ-карты."""
    response = request_vacant_sim_cards(icc_id)
    vacant_sim_response = namedtuple(
        'vacant_sim_response',
        ['success', 'text', 'icc', 'imsi']
    )
    if 'fault' in response:
        return vacant_sim_response(
            success=False,
            text='Неверный запрос',
            icc=None,
            imsi=None
        )
    sim_card = response.get('simList')
    if not sim_card:
        return vacant_sim_response(
            success=False,
            text='Нет доступной сим-карты',
            icc=None,
            imsi=None
        )
    return vacant_sim_response(
        success=True,
        text=None,
        icc=sim_card[0].get('iccId'),
        imsi=sim_card[0].get('imsi')
    )


@timer_sleep
@exception_handler
def request_exchange_sim_card(number: str, imsi: str):
    """API запрос на перезапись номера на новую СИМ-карту."""
    token = get_token()
    url = MTS_URL_API + 'b2b/v1/Resources/ChangeSIMCard'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'accept': 'text/plain'
    }
    js_data = {"Msisdn": number, "newSimImsi": imsi}
    response = requests.post(
        url=url,
        headers=headers,
        json=js_data,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.text


@exception_handler
def get_exchange_sim_card(number: Number, imsi: str):
    """Проверяет наличие блокировки, заменять сим-карту на номере."""
    get_block_info(number)
    logging.info(msg=f'exchange_result_check_block: {number.block}')
    if number.block:
        turn_service_numbers(numbers=number, add_service=False)
        logging.info(
            msg=(f'result_del_block: {number.api_response.success} '
                 f'{number.api_response.text}')
        )
    response = request_exchange_sim_card(number.number, imsi)
    logging.info(msg=f'request_exchange_sim_card: {response}')


@timer_sleep
@exception_handler
def api_request_number_services(session, number: int):
    """Возвращает список услуг номера."""
    url = (
        MTS_URL_API + 'b2b/v1/Product/ProductInfo'
        '?category.name=MobileConnectivity'
        '&marketSegment.characteristic.name='
        f'MSISDN&marketSegment.characteristic.value={number}'
        '&productOffering.actionAllowed=none'
        '&productOffering.productSpecification.productSpecificationType.name='
        'block&applyTimeZone=true'
    )
    response = session.get(
        url=url,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.json()


@exception_handler
def get_block_info(numbers: Number | list):
    """Установка информацию о наличии, дате блокировки на номере/номерах."""
    token = get_token()
    services_id = BLOCK_SERVICE_NUMBER, FIRST_BLOCK_SERVICE_NUMBER

    if not isinstance(numbers, list):
        numbers = [numbers]

    with (requests.Session() as session):
        retries = Retry(total=3, backoff_factor=1)
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        len_nums = len(numbers)
        for i, number in enumerate(numbers, start=1):
            if i == 1 or i % 1000 == 0 or i == len_nums:
                logging.info(f'{i} number')
            result = api_request_number_services(
                session=session,
                number=number.number
            )
            if result:
                if 'fault' in result:
                    logging.warning(
                        msg=f'number:{number.number}, response:{result}'
                    )
                else:
                    for service in result:
                        if service.get('externalID') in services_id:
                            date_block = (service.get('validFor')
                                          .get('startDateTime'))
                            number.block = True
                            number.block_date = (datetime.datetime
                                                 .fromisoformat(date_block))
            else:
                number.block = False


@timer_sleep
@exception_handler
def request_balance_numbers(session, numbers):
    """API запрос на баланс номеров."""
    url = MTS_URL_API + 'b2b/v1/Bills/CheckCharges?isBulk=true'
    js_data = [{'id': number} for number in numbers]
    response = session.post(
        url=url,
        json=js_data,
        timeout=MTS_API_REQUEST_TIMEOUT
    )
    return response.json()



@exception_handler
def set_balance_numbers() -> list:
    """Возвращает список Номеров с балансом."""
    numbers = get_list_numbers_class()
    token = get_token()
    result_numbers = list()
    with requests.Session() as session:
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json'
        }

        max_numbers_in_request = 1000
        for i in range(math_ceil(len(numbers) / max_numbers_in_request)):
            modul_left = i * max_numbers_in_request
            modul_right = modul_left + max_numbers_in_request
            response = request_balance_numbers(
                session,
                [number.number for number in numbers[modul_left:modul_right]]
            )
            for record in response:
                if record.get('remainedAmount') is not None:
                    balance = record.get('remainedAmount').get('amount')
                    if balance > 0:
                        result_numbers.append(
                            Number(number=record.get('id'), balance=balance)
                        )

    return result_numbers

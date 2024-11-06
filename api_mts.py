from time import sleep

import configs
import datetime
import logging
import random
import requests
import sqlite3 as sq
import time


def request_new_token():
    try:
        login = configs.mts_login
        password = configs.mts_password
        time_live_token = 86400
        url = "https://api.mts.ru/token"
        params = {
            "grant_type": "client_credentials",
            "validity_period": time_live_token
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        response = requests.post(
            url=url,
            auth=(login, password),
            headers=headers,
            params=params
            )
        token = response.json()["access_token"]
        with sq.connect(configs.database) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM tokens")
            cur.execute(
                "INSERT INTO tokens (token) VALUES (?)",
                (token,)
            )
        return token
    except Exception:
        logging.critical(msg="func request_new_token - error", exc_info=True)


def get_token():
    try:
        with sq.connect(configs.database) as con:
            cur = con.cursor()
            cur.execute("SELECT token FROM tokens WHERE datetime_creation > datetime('now', '-1 day')")
            result = cur.fetchone()
        if result:
            return result[0]
        else:
            return request_new_token()
    except Exception:
        logging.critical(msg="func get_token - error", exc_info=True)


def get_status_request(event_id):
    try:
        token = get_token()
        url = "https://api.mts.ru/b2b/v1/Product/CheckRequestStatusByUUID"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        js_data = {
            "relatedParty": [
                {"characteristic": []},
                {"id": event_id}
            ],
            "validFor": {}
        }
        response = requests.post(
            url=url,
            headers=headers,
            json=js_data
        )
        response = response.json()
        return response
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_status_request(event_id):
    """Проверка статуса выполнения API запроса"""
    try:
        statuses = ["Faulted", "Completed", "InProgress"]
        check_status = statuses[2]
        check_text = str()
        check_attempt = 60
        count_attempts = 0

        while check_status == statuses[2] and count_attempts <= check_attempt:
            response = get_status_request(event_id)
            check_status = response.get("relatedParty")[0].get("status")
            check_text = response.get("relatedParty")[0].get("characteristic")[-1].get("value")
            count_attempts += 1
            time.sleep(1)

        if count_attempts > check_attempt:
            success = False
            text = "Превышен лимит проверок статуса обращения"
        elif check_status == statuses[0]:
            success = False
            text = check_text
        elif check_status == statuses[1]:
            success = True
            text = "Положительный ответ от сервера"
        else:
            success = False
            text = "Неизвестная ошибка"
            logging.warning(
                f"check_status_request: {event_id};{check_status};"
                f"{check_text};{count_attempts}"
            )
        return success, text
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def request_balance(account):
    try:
        token = get_token()
        url = f"https://api.mts.ru/b2b/v1/Bills/CheckBalanceByAccount?fields=MOAF&accountNo={account}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        response = requests.get(
            url=url,
            headers=headers
        )
        response = response.json()
        logging.info(f"request_balance - response: {response}")
        return response
    except Exception:
        logging.critical(msg="func request_balance - error", exc_info=True)


def get_balance():
    try:
        account = "277702602686"
        response = request_balance(account)
        if "fault" in response:
            error, result = 1, "Неверный запрос"
        else:
            balance = response[0]["customerAccountBalance"][0]["remainedAmount"]["amount"]
            error, result = 0, balance
        return error, result
    except Exception:
        logging.critical(msg="func get_balance - error", exc_info=True)


def change_service_request(number, service_id, action):
    """API Запрос на изменение сервиса в номере"""
    try:
        token = get_token()
        url = f"https://api.mts.ru/b2b/v1/Product/ModifyProduct?msisdn={number}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
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
        response = requests.post(
            url=url,
            headers=headers,
            json=js_data
        )
        response = response.json()
        return response
    except Exception:
        logging.critical(msg="func change_service_request - error", exc_info=True)


def change_service_handler(number, service_id, action):
    """Обработчик запроса на изменение сервиса в номере"""
    try:
        response = change_service_request(number, service_id, action)
        if "fault" in response:
            logging.info(f"change_service error - response: {response}")
            success = False
            text = "Неверный запрос"
        else:
            text = response.get("eventID")
            success = True
        return success, text
    except Exception:
        logging.critical(msg="func change_service_handler - error", exc_info=True)


def add_block(number):
    """Добавление блокировке на номере"""
    try:
        service_id = "BL0005"
        action = "create"
        success, result_text = change_service_handler(number, service_id, action)
        return success, result_text
    except Exception:
        logging.critical(msg="func add_block - error", exc_info=True)


def del_block(number):
    """Удаление блокировки на номере"""
    try:
        service_id = 'BL0005'
        action = 'delete'
        success, result_text = change_service_handler(number, service_id, action)
        return success, result_text
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def change_service_later_request(number, service_id, action, dt_action):
    try:
        token = get_token()
        url = f"https://api.mts.ru/b2b/v1/Product/ModifyProduct?msisdn={number}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
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
        response = requests.post(
            url=url,
            headers=headers,
            json=js_data
        )
        response = response.json()
        logging.info(f"change_service_later_request - response: {response}")
        return response
    except Exception:
        logging.critical(msg="func change_service_later_request - error", exc_info=True)


def change_service_later_handler(number, service_id, action, dt_action):
    """Обработчик запроса на изменение сервиса в номере с отсрочкой"""
    try:
        response = change_service_later_request(number, service_id, action, dt_action)
        if "fault" in response:
            logging.info(f"change_service_later error - response: {response}")
            success = False
            text = "Неверный запрос"
        else:
            text = response.get("eventID")
            success = True
        return success, text
    except Exception:
        logging.critical(msg="func change_service_later - error", exc_info=True)


def del_block_random_hours(number):
    """Удаляет блокировку на номере рандом от 3-х до 12 часов"""
    try:
        service_id = 'BL0005'
        action = 'delete'
        dt_action = datetime.datetime.now() + datetime.timedelta(hours=random.randint(3, 12))
        dt_action = dt_action.isoformat()
        success, result_text = change_service_later_handler(number, service_id, action, dt_action)
        return success, result_text
    except Exception as err:
        logging.critical(msg='', exc_info=err)



def request_vacant_sim_cards(number='79162905452', last_icc_id=''):
    """API запрос списка 'болванок'"""
    try:
        token = get_token()
        url = 'https://api.mts.ru/b2b/v1/Resources/GetAvailableSIM'
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "*/*"
        }
        js_data = {"Msisdn": number, "SearchPattern": f"%{last_icc_id}"}
        response = requests.post(
            url=url,
            headers=headers,
            json=js_data
        )
        response = response.json()
        return response
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_vacant_sim_cards():
    """Выдаёт обработанный список ICC 'болванок'"""
    try:
        request_list = request_vacant_sim_cards()
        return [simcard.get('iccId') for simcard in request_list.get('simList')]
    except Exception:
        logging.critical(msg="func get_vacant_sim_cards - error", exc_info=True)


def request_list_numbers(page_num, account="277702602686", page_size=1000):
    """API запрос списка ICC + Number"""
    try:
        token = get_token()
        url = ("https://api.mts.ru/b2b/v1/Service/HierarchyStructure"
               f"?account={account}&pageNum={page_num}&pageSize={page_size}")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        response = requests.get(
            url=url,
            headers=headers
        )
        response = response.json()
        return response
    except Exception:
        logging.critical(msg="func request_list_numbers - error", exc_info=True)


def api_request_number_services(number):
    """Возвращает список услуг у номера"""
    try:
        token = get_token()
        url = ("https://api.mts.ru/b2b/v1/Product/ProductInfo?category.name=MobileConnectivity"
               f"&marketSegment.characteristic.name=MSISDN&marketSegment.characteristic.value={number}"
               "&productOffering.actionAllowed=none"
               "&productOffering.productSpecification.productSpecificationType.name=block&applyTimeZone=true")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        response = requests.get(
            url=url,
            headers=headers
        )
        response = response.json()
        return response
    except Exception:
        logging.critical(msg="func api_request_number_services - error", exc_info=True)


def get_list_numbers():
    """Возвращает обработанный список ICC + Number"""
    try:
        pagination = True
        numbers = list()
        page_num = 1

        while pagination:
            response = request_list_numbers(page_num)
            try:
                pagination = response[0]["partyRole"][0]["customerAccount"][0].get("href")
                [numbers.append((number["product"]["productCharacteristic"][1]["value"], number["product"]["productSerialNumber"])) for number in response[0]["partyRole"][0]["customerAccount"][0]["productRelationship"]]
                page_num += 1
                time.sleep(1)
            except Exception as err:
                logging.critical(
                    msg=f'response = {response}',
                    exc_info=err
                )

        return numbers
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_list_all_icc():
    """Возвращает полный список ICC ((ICC + Numbers) + 'болванки')"""
    try:
        list_icc_numbers = get_list_numbers()
        list_icc_numbers.extend([(icc, None) for icc in get_vacant_sim_cards()])
        return list_icc_numbers
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_vacant_sim_card_exchange(number, last_icc_id):
    try:
        response = request_vacant_sim_cards(number, last_icc_id)
        if 'fault' in response:
            error, result, text = 1, 0, 'Неверный запрос'
        else:
            sim_card = response.get("simList")
            if not sim_card:
                error, result, text = 0, 0, 'Нет доступной сим-карты'
            elif len(sim_card) > 1:
                error, result, text = 0, 0, 'Сим-карт больше 1'
            else:
                error, result, text = 0, 1, f'{sim_card[0].get("iccId")} {sim_card[0].get("imsi")}'
        return result, result, text
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def request_exchange_sim_card(number, imsi):
    try:
        token = get_token()
        url = 'https://api.mts.ru/b2b/v1/Resources/ChangeSIMCard'
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accept": "text/plain"
        }
        js_data = {"Msisdn": number, "newSimImsi": imsi}
        response = requests.post(
            url=url,
            headers=headers,
            json=js_data
        )
        return response.text
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_exchange_sim_card(number, imsi):
    """Проверяет наличие блокировки, заменять сим-карту на номере"""
    try:

        result_check_block = get_block_info(number)
        time,sleep(1)
        logging.info(msg=f'result_check_block:{result_check_block}')
        _, result, _ = result_check_block
        if result:
            response = del_block(number)
            time.sleep(60)
            logging.info(msg=f'result_del_block:{response}')
        response = request_exchange_sim_card(number, imsi)
        logging.info(msg=f'request_exchange_sim_card: {response}')
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_block_info(number):
    """"""
    try:
        service_id = 'BL0005'
        error, result, text = False, False, str()
        response = api_request_number_services(number)
        if response:
            if 'fault' in response:
                error, text = True, 'Неверный запрос'
                logging.warning(msg=f'number:{number}, response:{response}')
            else:
                for service in response:
                    if service.get("externalID") == service_id:
                        date_block = service.get("validFor").get("startDateTime")[:10]
                        result, text = True, date_block
                        break
        else:
            logging.warning(msg=f'number:{number}, response:{response}')
        return error, result, text
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def request_balance_numbers(numbers):
    try:
        token = get_token()
        url = "https://api.mts.ru/b2b/v1/Bills/CheckCharges?isBulk=true"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        js_data = [{"id": number} for number in numbers]
        response = requests.post(
            url=url,
            headers=headers,
            json=js_data
        )
        response = response.json()
        return response
    except Exception:
        logging.critical(msg="func request_balance_numbers - error", exc_info=True)


def get_balance_numbers(crit_balance=0):
    """Возвращает список (Номер, баланс) с возможности отфильтровки"""
    try:
        icc_numbers = get_list_numbers()
        num_balances = list()

        while len(icc_numbers) > 1000:
            response_result = request_balance_numbers([num[1] for num in icc_numbers[:1000]])
            for record in response_result:
                if record.get("remainedAmount"):
                    if record["remainedAmount"]["amount"] > crit_balance:
                        num_balances.append((record["id"], record["remainedAmount"]["amount"]))
            icc_numbers = icc_numbers[1000:]
            time.sleep(1)

        return num_balances
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_all_active_sim_cards():
    """Возвращает список активных номеров"""
    try:
        numbers = get_list_numbers()
        id_services = 'BL0005', 'BL0008'
        active_numbers = list()
        len_num = len(numbers)
        for num, number in enumerate(numbers):
            print(len_num - num)
            time.sleep(1)
            number = number[1]
            response = api_request_number_services(number)
            if 'fault' in response:
                logging.warning(f'get_all_active_sim_cards - {number} response: {response}')
                active_numbers.append(number)
            else:
                for service in response:
                    if service.get('externalID') in id_services:
                        break
                else:
                    active_numbers.append(number)

        return active_numbers
    except Exception as err:
        logging.critical(msg='func get_all_active_sim_cards - error', exc_info=err)

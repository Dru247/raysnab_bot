import config
import calendar
import datetime
import logging
import random
import requests
import sqlite3 as sq
import time


def check_number(number):
    try:
        number = number.strip()
        if number.isdigit():
            len_number = len(number)
            if len_number == 10:
                number = "7" + number
                return 1, number
            elif len_number == 11:
                number = "7" + number[1:]
                return 1, number
            else:
                logging.info(msg=f"func check_number: {number}")
                return 0, number
        else:
            logging.info(msg=f"func check_number: {number}")
            return 0, number
    except Exception:
        logging.critical(msg="func check_number - error", exc_info=True)


def request_new_token():
    try:
        login = config.mts_login
        password = config.mts_password
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
        with sq.connect(config.database) as con:
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
        with sq.connect(config.database) as con:
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
        logging.info(f"get_status_request - response: {response}")
        return response
    except Exception:
        logging.critical(msg="func get_status_request - error", exc_info=True)


def check_status_request(event_id):
    try:
        statuses = ["Faulted", "Completed", "InProgress"]
        check_status = statuses[2]
        check_text = str()
        check_attempt = 10
        count_attempts = 0
        time_step = 5

        while check_status == statuses[2] and count_attempts <= check_attempt:
            time.sleep(time_step)
            response = get_status_request(event_id)
            check_status = response["relatedParty"][0].get("status")
            check_text = response["relatedParty"][0]["characteristic"][-1].get("value")
            count_attempts += 1
            time_step += 10

        if count_attempts > check_attempt:
            success = 0
            text = "Превышен лимит проверок статуса обращения"
        elif check_status == statuses[0]:
            success = 0
            text = check_text
        elif check_status == statuses[1]:
            success = 1
            text = "Положительный ответ от сервера"
        else:
            success = 0
            text = "Неизвестная ошибка"
            logging.warning(
                f"check_status_request: {event_id};{check_status};"
                f"{check_text};{count_attempts};{time_step}"
            )
        return success, text
    except Exception:
        logging.critical(msg="func check_status_request - error", exc_info=True)


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
        logging.info(f"change_service - response: {response}")
        return response
    except Exception:
        logging.critical(msg="func change_service - error", exc_info=True)


def change_service(number, service_id, action):
    try:
        result_var = ["Ошибка", "Успех"]
        response = change_service_request(number, service_id, action)
        if "fault" in response:
            result = 0
            text = "Неверный запрос"
        else:
            event_id = response.get("eventID")
            result, text = check_status_request(event_id)
        return result, result_var[result], text
    except Exception:
        logging.critical(msg="func change_service - error", exc_info=True)


def add_block(number):
    try:
        service_id = "BL0005"
        action = "create"
        result, result_text, text_description = change_service(number, service_id, action)
        return result, result_text, text_description
    except Exception:
        logging.critical(msg="func add_block - error", exc_info=True)


def del_block(number):
    try:
        service_id = "BL0005"
        action = "delete"
        result, result_text, text_description = change_service(number, service_id, action)
        return result, result_text, text_description
    except Exception:
        logging.critical(msg="func del_block - error", exc_info=True)


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


def change_service_later(number, service_id, action, dt_action):
    try:
        result_var = ["Ошибка", "Успех"]
        response = change_service_later_request(number, service_id, action, dt_action)
        if "fault" in response:
            result = 0
            text = "Неверный запрос"
        else:
            event_id = response.get("eventID")
            result, text = check_status_request(event_id)
        return result, result_var[result], text
    except Exception:
        logging.critical(msg="func change_service_later - error", exc_info=True)


def del_block_random_hours(number):
    try:
        service_id = "BL0005"
        action = "delete"
        dt_action = datetime.datetime.now() + datetime.timedelta(hours=random.randint(3, 12))
        dt_action = dt_action.isoformat()
        result, result_text, text_description = change_service_later(number, service_id, action, dt_action)
        return result, result_text, text_description, dt_action
    except Exception:
        logging.critical(msg="func add_block_random_hours - error", exc_info=True)


def add_block_last_day(number):
    try:
        service_id = "BL0005"
        action = "create"
        year = datetime.date.today().year
        month = datetime.date.today().month
        last_day = calendar.monthrange(year, month)[1]
        dt_action = datetime.datetime(
            year=year,
            month=month,
            day=last_day,
            hour=23,
            minute=random.randint(50, 58),
            second=random.randint(0, 59),
        ).isoformat()
        result, result_text, text_description = change_service_later(number, service_id, action, dt_action)
        return result, result_text, text_description, dt_action
    except Exception:
        logging.critical(msg="func add_block_last_day - error", exc_info=True)


def request_vacant_sim_cards(number="79162905452", last_iccid=""):
    """API запрос списка 'болванок'"""
    try:
        token = get_token()
        url = "https://api.mts.ru/b2b/v1/Resources/GetAvailableSIM"
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "*/*"
        }
        js_data = {"Msisdn": number, "SearchPattern": f"%{last_iccid}"}
        response = requests.post(
            url=url,
            headers=headers,
            json=js_data
        )
        response = response.json()
        return response
    except Exception:
        logging.critical(msg="func request_vacant_sim_cards - error", exc_info=True)


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


def get_list_numbers():
    """Возвращает обработанный список ICC + Number"""
    try:
        pagination = True
        numbers = list()
        page_num = 1

        while pagination:
            response = request_list_numbers(page_num)
            pagination = response[0]["partyRole"][0]["customerAccount"][0].get("href")
            [numbers.append((number["product"]["productCharacteristic"][1]["value"], number["product"]["productSerialNumber"])) for number in response[0]["partyRole"][0]["customerAccount"][0]["productRelationship"]]
            page_num += 1
            time.sleep(1)

        return numbers
    except Exception:
        logging.critical(msg="func get_list_numbers - error", exc_info=True)


def get_list_all_icc():
    """Возвращает полный список ICC ((ICC + Numbers) + 'болванки')"""
    try:
        list_icc_numbers = get_list_numbers()
        [list_icc_numbers.append((icc,)) for icc in get_vacant_sim_cards()]
        return list_icc_numbers
    except Exception:
        logging.critical(msg="func get_list_all_icc - error", exc_info=True)



def get_vacant_sim_card_exchange(number, last_iccid):
    try:
        response = request_vacant_sim_cards(number, last_iccid)
        if "fault" in response:
            error, result, text = 1, 0, "Неверный запрос"
        else:
            sim_card = response.get("simList")
            if not sim_card:
                error, result, text = 0, 0, "Нет доступной сим-карты"
            elif len(sim_card) > 1:
                error, result, text = 0, 0, "Сим-карт больше 1"
            else:
                error, result, text = 0, 1, f'{sim_card[0].get("iccId")} {sim_card[0].get("imsi")}'
        return result, result, text
    except Exception:
        logging.critical(msg="func get_vacant_sim_card_exchange - error", exc_info=True)


def request_exchange_sim_card(number, imsi):
    try:
        token = get_token()
        url = "https://api.mts.ru/b2b/v1/Resources/ChangeSIMCard"
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
        response = response.text
        logging.info(f"request_exchange_sim_card - response: {response}")
        return response
    except Exception:
        logging.critical(msg="func request_exchange_sim_card - error", exc_info=True)


def get_exchange_sim_card(number, imsi):
    try:
        result_var = ["Ошибка", "Успех"]
        event_id = request_exchange_sim_card(number, imsi)
        logging.info(msg=f"func get_exchange_sim_card - event_id: {event_id}, {type(event_id)}")
        # result, text = check_status_request(event_id)
        result, text = result_var[1], "OK"
        return result, text
    except Exception:
        logging.critical(msg="func get_exchange_sim_card - error", exc_info=True)


def request_block_info(number):
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
        logging.critical(msg="func request_block_info - error", exc_info=True)


def get_block_info(number):
    try:
        service_id = "BL0005"
        error, result, text = 0, 0, str()
        response = request_block_info(number)
        if response:
            if "fault" in response:
                error, text = 1, "Неверный запрос"
            else:
                for service in response:
                    if service.get("externalID") == service_id:
                        date_block = service["validFor"].get("startDateTime")[:10]
                        result, text = 1, date_block
                        break
        return error, result, text
    except Exception:
        logging.critical(msg="func get_block_info - error", exc_info=True)


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
        iccs_numbers = get_list_numbers()
        num_balances = list()

        while len(iccs_numbers) > 1000:
            response_result = request_balance_numbers([num[1] for num in iccs_numbers[:1000]])
            for record in response_result:
                if record.get("remainedAmount"):
                    if record["remainedAmount"]["amount"] > crit_balance:
                        num_balances.append((record["id"], record["remainedAmount"]["amount"]))
            iccs_numbers = iccs_numbers[1000:]
            time.sleep(1)

        return num_balances
    except Exception:
        logging.critical(msg="func get_balance_numbers - error", exc_info=True)

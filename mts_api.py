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


def get_status_request(event_id, date_start, date_end):
    try:
        token = get_token()
        url = "https://api.mts.ru/b2b/v1/Product/CheckRequestStatusByUUID"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        js_data = {
            "relatedParty": [
                {"characteristic": []},
                {"id": event_id}
            ],
            "validFor": {
                "startDateTime": date_start,
                "endDateTime": date_end}
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


def check_status_request(response):
    try:
        event_id = response.get("eventID")
        event_time = response.get("eventTime")
        time_start_first = datetime.datetime.fromisoformat(event_time[:-9])
        time_end_first = time_start_first + datetime.timedelta(days=1)
        time_start = time_start_first.isoformat()
        time_end = time_end_first.isoformat()
        statuses = ["Faulted", "Completed", "InProgress"]
        check_status = statuses[2]
        check_text = str()
        check_attempt = 10
        count_attempts = 0
        time_step = 5

        while check_status == statuses[2] and count_attempts <= check_attempt:
            time.sleep(time_step)
            response = get_status_request(event_id, time_start, time_end)
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
                f"check_status_request: {event_id};{event_time};{time_start};{time_end};{check_status};"
                f"{check_text};{count_attempts};{time_step}"
            )
        return success, text
    except Exception:
        logging.critical(msg="func check_status_request - error", exc_info=True)


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
            result, text = check_status_request(response)
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
        logging.info(f"change_service - response: {response}")
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
            result, text = check_status_request(response)
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

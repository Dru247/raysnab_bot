from datetime import datetime

import configs
import logging
import requests


drf_token = configs.token_drf


def api_request_human_term_list():
    """Запрос списка терминалов на руках"""
    try:
        url = 'http://89.169.136.83/api/v1/human-terminals/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception as err:
        logging.critical(msg="func dj_api.api_request_human_term_list - error", exc_info=err)


def api_request_installations_list():
    """Запрос списка установок"""
    try:
        url = 'http://89.169.136.83/api/v1/installations/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception as err:
        logging.critical(msg='func dj_api.api_request_installations_list - error', exc_info=err)


def api_request_object_list():
    """Запрос списка пользователей на серверах"""
    try:
        url = 'http://89.169.136.83/api/v1/objects/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception:
        logging.critical(msg="func dj_api.api_request_object_list - error", exc_info=True)


def api_request_object_change_date(obj_id, date_target):
    """Меняет оплаченную дату у объекта по ID"""
    try:
        url = f'http://89.169.136.83/api/v1/object/{obj_id}/'
        headers = {"Authorization": f"Token {drf_token}"}
        js_data = {
            "date_change_status": date_target
        }
        response = requests.patch(
            url=url,
            headers=headers,
            json=js_data
        ).json()
        return response
    except Exception:
        logging.critical(msg="func api_dj.api_request_object_change_date - error", exc_info=True)


def api_request_sim_list():
    """Главный API запрос"""
    try:
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url='http://89.169.136.83/api/v1/simlist/',
            headers=headers
        ).json()
        return response
    except Exception:
        logging.critical(msg="func dj_api.api_request_sim_list - error", exc_info=True)


def api_request_terminal_list():
    """Запрос списка терминалов"""
    try:
        url = 'http://89.169.136.83/api/v1/termlist/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception:
        logging.critical(msg="func dj_api.api_request_terminal_list - error", exc_info=True)


def api_request_user_list():
    """Запрос списка пользователей на серверах"""
    try:
        url = 'http://89.169.136.83/api/v1/userlist/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception:
        logging.critical(msg="func dj_api.api_request_user_list - error", exc_info=True)


def get_list_sim_cards():
    """Возвращает список ICC и номеров"""
    try:
        return [(row['id'], row['operator'], row['number'], row['icc'], row['terminal']) for row in api_request_sim_list()]
    except Exception:
        logging.critical(msg="func dj_api.get_list_sim_cards - error", exc_info=True)


def get_payer_sim_cards(payer):
    try:
        id_terminals = [
            row['terminal'] for row in api_request_object_list()
            if row['payer'] == payer
            and row['terminal']
            and row['active']
        ]
        result = [(row['operator'], row['number'], row['icc']) for row in api_request_sim_list() if row['terminal'] in id_terminals]
        mts = ['МТС:']
        mega = ['МЕГА:']
        sim2m = ['СИМ2М:']
        for sim in result:
            if sim[0] == 1:
                mega.append(sim[1])
            elif sim[0] == 2:
                mts.append(sim[1])
            else:
                sim2m.append(sim[1])
        return mts, mega, sim2m
    except Exception:
        logging.critical(msg="func dj_api.get_payer_sim_cards - error", exc_info=True)


def get_date_terminals(date):
    """API запрос на списк терминалов по дате"""
    try:
        return [row['terminal'] for row in api_request_object_list() if row['date_change_status'] == date and row['terminal']]
    except Exception:
        logging.critical(msg="func dj_api.get_date_terminals - error", exc_info=True)


def get_date_sim_cards(date):
    try:
        terminals_id = get_date_terminals(date)
        sim_cards = api_request_sim_list()
        result = [(row['operator'], row['number'], row['icc']) for row in sim_cards if row['terminal'] in terminals_id]
        mts = ['МТС:']
        mega = ['МЕГА:']
        sim2m = ['СИМ2М:']
        for sim in result:
            if sim[0] == 1:
                mega.append(sim[1])
            elif sim[0] == 2:
                mts.append(sim[1])
            else:
                sim2m.append(sim[1])
        return mts, mega, sim2m
    except Exception:
        logging.critical(msg="func dj_api.get_date_sim_cards - error", exc_info=True)


def get_status_sim_cards():
    """API запрос на списк активных\неактивных терминалов """
    try:
        mts_id = 2
        status_terms = {row['terminal']: row['active'] for row in api_request_object_list() if row['terminal']}
        # "Возникает ошибка если сим-карта стоит в терминале, который на руках у кого-то (ид терминала не находит среди объектов)"
        print(status_terms[4813])
        status_sims = {sim[2]: status_terms[sim[4]] for sim in get_list_sim_cards() if sim[4] and sim[1] == mts_id and sim[2]}
        return status_sims
    except Exception:
        logging.critical(msg="func dj_api.get_status_sim_cards - error", exc_info=True)


def objects_change_date(payer_id, date_target):
    """Проходится по ID объектов у клиента и меняет дату"""
    try:
        objs_id = [row['id'] for row in api_request_object_list() if row['active'] and row['payer'] == int(payer_id)]
        for obj_id in objs_id:
            api_request_object_change_date(obj_id, date_target)
    except Exception:
        logging.critical(msg="func api_dj.objects_change_date - error", exc_info=True)


def api_request_human_contacts():
    """Запрос списка контактов людей"""
    try:
        url = 'http://89.169.136.83/api/v1/human-contacts/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception:
        logging.critical(msg="func api_dj.api_request_human_contacts - error", exc_info=True)


def get_human_for_from_teleg_id(teleg_id):
    """Поиск ID человека по ID Telegram"""
    try:
        for contacts in api_request_human_contacts():
            if contacts['contact_rec'] == str(teleg_id):
                return contacts['human']
    except Exception:
        logging.critical(msg="func api_dj.objects_change_date - error", exc_info=True)


def get_all_active_sim_cards():
    """Возвращает все активные сим-карты МТС"""
    try:
        date_now = datetime.today()
        id_terminals = [
            row['terminal'] for row in api_request_object_list()
            if datetime.fromisoformat(row['date_change_status']) > date_now
            and row['terminal']
        ]
        mts_id = 2
        mts_sim_cards = [
            row['number'] for row in api_request_sim_list()
            if row['operator'] == mts_id
            and row['terminal'] in id_terminals
            and row['number']
        ]
        return mts_sim_cards
    except Exception as err:
        logging.critical(msg="func api_dj.objects_change_date - error", exc_info=err)


def get_first_number_for_change():
    """Возвращает номер МТС для замены"""
    try:
        date_now = datetime.today()
        id_terminals_and_dates = {
            row['terminal']: row['date_change_status']
            for row in api_request_object_list()
            if datetime.fromisoformat(row['date_change_status']) < date_now
            and row['terminal']
            and not row['active']
        }
        mts_id = 2
        mts_sim_cards = [
            (row['number'], id_terminals_and_dates[row['terminal']])
            for row in api_request_sim_list()
            if row['operator'] == mts_id
            and row['terminal'] in id_terminals_and_dates
            and row['number']
        ]
        mts_sim_cards.sort(key=lambda a: a[1], reverse=False)
        return mts_sim_cards[0]
    except Exception as err:
        logging.critical(msg="func api_dj.get_first_number_for_change - error", exc_info=err)


def get_diff_terminals():
    """Возвращает разницу терминалов"""
    try:
        id_term_install = {term['terminal'] for term in api_request_installations_list()}
        id_term_in_hands = {term['terminal'] for term in api_request_human_term_list()}
        id_term_all = {
            term['imei'] for term in api_request_terminal_list()
            if term['id'] not in id_term_install
            and term['id'] not in id_term_in_hands
        }
        return id_term_all
    except Exception as err:
        logging.critical(msg="func api_dj.get_diff_terminals - error", exc_info=err)

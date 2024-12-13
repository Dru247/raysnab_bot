import configs
import datetime
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
        logging.critical(msg='', exc_info=err)


def api_request_human_sim_list():
    """Запрос списка сим-карт на руках"""
    try:
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url='http://89.169.136.83/api/v1/human-sim-cards/',
            headers=headers
        ).json()
        return response
    except Exception as err:
        logging.critical(msg='', exc_info=err)


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
    except Exception as err:
        logging.critical(msg='', exc_info=err)


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
    """Запрос списка сим-карт"""
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
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_payer_sim_cards(payer):
    try:
        id_terminals = {
            row['terminal'] for row in api_request_object_list()
            if row['payer'] == int(payer)
            and row['terminal']
            and row['active']
        }
        result = {
            (row['operator'], row['number'], row['icc']) for row in api_request_sim_list()
            if row['terminal'] in id_terminals
        }
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
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_date_terminals(date):
    """API запрос на список терминалов по дате"""
    try:
        return [row['terminal'] for row in api_request_object_list() if row['date_change_status'] == date and row['terminal']]
    except Exception as err:
        logging.critical(msg='', exc_info=err)


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
    except Exception as err:
        logging.critical(msg='', exc_info=err)


# def get_status_sim_cards():
#     """API запрос на список активных\неактивных терминалов"""
#     try:
#         mts_id = 2
#         status_terms = {row['terminal']: row['active'] for row in api_request_object_list() if row['terminal']}
#         status_sims = {sim[2]: status_terms[sim[4]] for sim in get_list_sim_cards() if sim[4] and sim[1] == mts_id and sim[2]}
#         return status_sims
#     except Exception:
#         logging.critical(msg="func dj_api.get_status_sim_cards - error", exc_info=True)


def objects_change_date(payer_id, date_target):
    """Проходится по ID объектов у клиента и меняет дату"""
    try:
        objs_id = [row['id'] for row in api_request_object_list() if row['active'] and row['payer'] == int(payer_id)]
        for obj_id in objs_id:
            api_request_object_change_date(obj_id, date_target)
    except Exception as err:
        logging.critical(msg='', exc_info=err)


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
        date_now = datetime.datetime.today()
        id_terminals = [
            row['terminal'] for row in api_request_object_list()
            if datetime.datetime.fromisoformat(row['date_change_status']) > date_now
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
        date_now = datetime.datetime.today()
        id_terminals_and_dates = {
            row['terminal']: row['date_change_status']
            for row in api_request_object_list()
            if datetime.datetime.fromisoformat(row['date_change_status']) < date_now
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
        id_term_on_hands = {term['terminal'] for term in api_request_human_term_list()}
        id_term_in_install = {term['terminal'] for term in api_request_installations_list()}
        union_trackers = id_term_on_hands | id_term_in_install
        diff_trackers_all_vs_install_and_on_hands = {
            term['imei'] for term in api_request_terminal_list()
            if term['id'] not in union_trackers
        }
        id_trackers_in_obj = {obj['terminal'] for obj in api_request_object_list()}
        intersection_trackers = id_term_on_hands & id_trackers_in_obj
        diff_trackers_on_hands_and_obj = {
            term['imei'] for term in api_request_terminal_list()
            if term['id'] in intersection_trackers
        }
        return diff_trackers_all_vs_install_and_on_hands, diff_trackers_on_hands_and_obj
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def check_sim_cards_in_dj():
    """Проверка сим-карт внутри проекта"""
    try:
        request_all_sim_cards = api_request_sim_list()
        id_sim_in_trackers = {sim['id'] for sim in request_all_sim_cards if sim['terminal']}
        id_sim_on_hands = {sim['simcard'] for sim in api_request_human_sim_list()}
        id_sim_in_trackers_and_on_hands = id_sim_in_trackers & id_sim_on_hands
        sim_in_trackers_and_on_hands = {
            sim['icc'] for sim in request_all_sim_cards if sim['id'] in id_sim_in_trackers_and_on_hands
        }
        id_sim_everywhere = id_sim_in_trackers | id_sim_on_hands
        sim_not_everywhere = {
            sim['icc'] for sim in request_all_sim_cards if sim['id'] not in id_sim_everywhere
        }
        return sim_in_trackers_and_on_hands, sim_not_everywhere
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def api_request_schedule():
    """Запрос графика"""
    try:
        url = 'http://89.169.136.83/api/v1/schedule/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception as err:
        logging.critical(msg='', exc_info=err)


def get_api_schedule_man():
    try:
        maks = 673
        date_now = datetime.date.today()
        for schedule_date in api_request_schedule():
            if datetime.date.fromisoformat(schedule_date.get('date')) == date_now:
                if schedule_date.get('human') == maks:
                    return 'Макс'
                return 'Аня'
    except Exception as err:
        logging.critical(msg='', exc_info=err)

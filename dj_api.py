import configs
import logging
import requests


url_1 = 'http://89.169.136.83/api/v1/simlist/'
url_2 = 'http://89.169.136.83/api/v1/termlist/'
url_3 = 'http://89.169.136.83/api/v1/objects/'
drf_token = configs.token_drf

# def get_sim(terminal_imei, url_term=url_2, url_sim=url_1):
#     try:
#         id_term = int()
#         for term in requests.get(url=url_term).json():
#             if term.get('imei') == terminal_imei:
#                 id_term = term.get('id')
#                 break
#         sim_cards = list()
#         for sim in requests.get(url=url_sim).json():
#             if sim.get('terminal') == id_term:
#                 sim_cards.append((sim.get('icc'), sim.get('number')))
#         return sim_cards
#     except Exception:
#         logging.critical(msg="dj_api: get_sim - error", exc_info=True)


def main_request(url, token):
    """Главный API запрос"""
    try:
        headers = {"Authorization": f"Token {token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception:
        logging.critical(msg="func dj_api.main_request - error", exc_info=True)


def get_list_sim_cards():
    """Возвращает список ICC и номеров"""
    try:
        response = main_request(url_1, drf_token)
        sim_list = [(row['id'], row['operator'], row['number'], row['icc'], row['terminal']) for row in response]
        return sim_list
    except Exception:
        logging.critical(msg="func dj_api.get_list_sim_cards - error", exc_info=True)


def get_payer_terminals(payer):
    """API запрос на списк терминалов по плательщику"""
    try:
        response = main_request(url_3, drf_token)
        terminals_id = [row['terminal'] for row in response if row['payer'] == payer and row['terminal'] and row['active']]
        return terminals_id
    except Exception:
        logging.critical(msg="func dj_api.get_payer_terminals - error", exc_info=True)


def get_payer_sim_cards(payer):
    try:
        terminals_id = get_payer_terminals(payer)
        sim_cards = main_request(url_1, drf_token)
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
        logging.critical(msg="func dj_api.get_payer_sim_cards - error", exc_info=True)


def get_status_sim_cards():
    """API запрос на списк активных\неактивных терминалов """
    try:
        mts_id = 2
        response = main_request(url_3, drf_token)
        status_terms = {row['terminal']: row['active'] for row in response if row['terminal']}
        # "Возникает ошибка если сим-карта стоит в терминале, который на руках у кого-то (ид терминала не находит среди объектов)"
        print(status_terms[4813])
        status_sims = {sim[2]: status_terms[sim[4]] for sim in get_list_sim_cards() if sim[4] and sim[1] == mts_id and sim[2]}
        return status_sims
    except Exception:
        logging.critical(msg="func dj_api.get_status_sim_cards - error", exc_info=True)


def request_user_list():
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
        logging.critical(msg="func dj_api.request_user_list - error", exc_info=True)


def request_object_list():
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
        logging.critical(msg="func dj_api.request_object_list - error", exc_info=True)


def request_terminal_list():
    """Запрос списка пользователей на серверах"""
    try:
        url = 'http://89.169.136.83/api/v1/termlist/'
        headers = {"Authorization": f"Token {drf_token}"}
        response = requests.get(
            url=url,
            headers=headers
        ).json()
        return response
    except Exception:
        logging.critical(msg="func dj_api.request_terminal_list - error", exc_info=True)

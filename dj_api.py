import config
import logging
import requests


url_1 = 'http://89.169.136.83/api/v1/simlist/'
url_2 = 'http://89.169.136.83/api/v1/termlist/'
url_3 = 'http://89.169.136.83/api/v1/objects/'
drf_token = config.token_drf

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
    headers = {"Authorization": f"Token {token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


def get_payer_terminals(payer):
    response = main_request(url_3, drf_token)
    terminals_id = [row['terminal'] for row in response if row['payer'] == payer]
    return terminals_id


def get_payer_sim_cards(payer):
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

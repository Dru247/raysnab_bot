import logging
import requests


url_1 = 'http://89.169.129.80:8000/api/v1/simlist/'
url_2 = 'http://89.169.129.80:8000/api/v1/termlist/'

def get_sim(terminal_imei, url_term=url_2, url_sim=url_1):
    try:
        id_term = int()
        for term in requests.get(url=url_term).json():
            if term.get('imei') == terminal_imei:
                id_term = term.get('id')
                break
        sim_cards = list()
        for sim in requests.get(url=url_sim).json():
            if sim.get('terminal') == id_term:
                sim_cards.append((sim.get('icc'), sim.get('number')))
        return sim_cards
    except Exception:
        logging.critical(msg="dj_api: get_sim - error", exc_info=True)

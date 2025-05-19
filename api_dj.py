import calendar

from dateutil.relativedelta import relativedelta

import configs
import datetime
import logging
import requests


URL_API = 'http://89.169.136.83/api/v1/'
drf_token = configs.token_drf


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
def api_request_humans():
    """Запрос списка людей."""
    url = URL_API + 'humans/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_human_contacts():
    """Запрос списка контактов людей."""
    url = 'http://89.169.136.83/api/v1/human-contacts/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_human_names():
    """Запрос списка имён людей."""
    url = 'http://89.169.136.83/api/v1/human-names/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_human_tracker_list():
    """Запрос списка трекеров на руках."""
    url = 'http://89.169.136.83/api/v1/human-terminals/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_human_sim_list():
    """Запрос списка сим-карт на руках."""
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url='http://89.169.136.83/api/v1/human-sim-cards/',
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_installations_list():
    """Запрос списка установок."""
    url = 'http://89.169.136.83/api/v1/installations/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_object_list():
    """Запрос списка объектов."""
    url = 'http://89.169.136.83/api/v1/objects/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_all_active_mts_numbers():
    """Запрос всех активных номеров МТС."""
    url = URL_API + 'sim/all-active-mts/'
    headers = {'Authorization': f'Token {drf_token}'}
    response = requests.get(url=url, headers=headers)
    return response.json()


@exception_handler
def api_request_object_change_date(obj_id, date_target):
    """Меняет оплаченную дату у объекта по ID."""
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


@exception_handler
def api_request_price_logistic():
    """Запрос прайса на выезды."""
    url = f'http://89.169.136.83/api/v1/price-logistics/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_price_trackers():
    """Запрос прайса на оборудование."""
    url = f'http://89.169.136.83/api/v1/price-trackers/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_schedule():
    """Запрос графика."""
    url = 'http://89.169.136.83/api/v1/schedule/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_price_services():
    """Запрос списка услуг."""
    url = f'http://89.169.136.83/api/v1/services/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_tracker_models():
    """Запрос списка моделей трекеров."""
    url = 'http://89.169.136.83/api/v1/tracker-models/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_sim_list():
    """Запрос списка сим-карт."""
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url='http://89.169.136.83/api/v1/simlist/',
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_terminal_list():
    """Запрос списка терминалов."""
    url = 'http://89.169.136.83/api/v1/termlist/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def api_request_user_list():
    """Запрос списка пользователей на серверах."""
    url = 'http://89.169.136.83/api/v1/userlist/'
    headers = {"Authorization": f"Token {drf_token}"}
    response = requests.get(
        url=url,
        headers=headers
    ).json()
    return response


@exception_handler
def get_list_sim_cards():
    """Возвращает список ICC и номеров."""
    return [(row['id'], row['operator'], row['number'], row['icc'], row['terminal']) for row in api_request_sim_list()]


@exception_handler
def get_payer_sim_cards(payer):
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


@exception_handler
def get_date_terminals(date):
    """API запрос на список терминалов по дате."""
    return [row['terminal'] for row in api_request_object_list() if row['date_change_status'] == date and row['terminal']]


@exception_handler
def get_date_sim_cards(date):
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


# def get_status_sim_cards():
#     """API запрос на список активных\неактивных терминалов"""
#     try:
#         mts_id = 2
#         status_terms = {row['terminal']: row['active'] for row in api_request_object_list() if row['terminal']}
#         status_sims = {sim[2]: status_terms[sim[4]] for sim in get_list_sim_cards() if sim[4] and sim[1] == mts_id and sim[2]}
#         return status_sims
#     except Exception:
#         logging.critical(msg="func dj_api.get_status_sim_cards - error", exc_info=True)


@exception_handler
def objects_change_date(payer_id, date_target):
    """Проходится по ID объектов у клиента и меняет дату."""
    date_now = datetime.date.today()
    date_plus_month = date_now + relativedelta(months=1)
    date_plus_month_last_day = calendar.monthrange(date_plus_month.year, date_plus_month.month)[1]
    last_day_next_month  = datetime.date.fromisoformat(date_plus_month.strftime(f'%Y-%m-{date_plus_month_last_day}'))
    # есть касяк, при оплате объектов, когда у клиента уже есть с оплаченным сроком на конец текущего месяца, он тоже измениться,
    # и если оплатят больше чем на 1 месяц, объект с оплатой тоже увеличится
    objs_id = [
        row['id'] for row in api_request_object_list()
        if row['active']
           and row['payer'] == int(payer_id)
           and datetime.date.fromisoformat(row['date_change_status']) < last_day_next_month # проверяет на объекты с оплатой наперёд
    ]
    for obj_id in objs_id:
        api_request_object_change_date(obj_id, date_target)


@exception_handler
def get_id_human_for_from_telegram_id(telegram_id):
    """Поиск ID человека по ID Telegram."""
    for contacts in api_request_human_contacts():
        if contacts['contact_rec'] == str(telegram_id):
            return contacts['human']
    return None


# @exception_handler
# def get_all_active_sim_cards():
#     """Возвращает все активные сим-карты МТС."""
#     date_now = datetime.datetime.today()
#     id_terminals = [
#         row['terminal'] for row in api_request_object_list()
#         if datetime.datetime.fromisoformat(row['date_change_status']) > date_now
#         and row['terminal']
#     ]
#     mts_id = 2
#     mts_sim_cards = [
#         row['number'] for row in api_request_sim_list()
#         if row['operator'] == mts_id
#         and row['terminal'] in id_terminals
#         and row['number']
#     ]
#     return mts_sim_cards


@exception_handler
def get_numbers_for_change():
    """Возвращает номер МТС для замены."""
    mts_id = 2
    mts_limit_days = 180 - 1
    date_limit = datetime.datetime.today() - datetime.timedelta(days=mts_limit_days)
    date_limit = date_limit.timestamp()
    all_sim_mts = [
        sim for sim in api_request_sim_list()
        if sim.get('operator') == mts_id
        and sim.get('number')
    ]
    # сим-карты в объектах с истёкшим сроком
    id_terminals_and_dates = {
        row['terminal']: row['date_change_status']
        for row in api_request_object_list()
        if datetime.datetime.fromisoformat(row['date_change_status']).timestamp() < date_limit
        and row['terminal']
        and not row['active']
    }
    mts_sim_cards = [
        (sim['number'], id_terminals_and_dates[sim['terminal']])
        for sim in all_sim_mts
        if sim['terminal'] in id_terminals_and_dates
    ]
    # список потерянных МТС
    _, sim_not_everywhere = check_sim_cards_in_dj()
    [
        mts_sim_cards.append((sim['number'], sim.get('time_create')))
        for sim in all_sim_mts
        if sim.get('icc') in sim_not_everywhere
        and sim.get('operator') == mts_id
    ]
    # сим-карты в трекерах на руках с истёкшим сроком
    tracker_in_hands = [
        tracker.get('terminal') for tracker in api_request_human_tracker_list()
        if datetime.datetime.fromisoformat(tracker.get('time_create')).timestamp() < date_limit
    ]
    [
        mts_sim_cards.append((sim.get('number'), sim.get('time_create')))
        for sim in all_sim_mts
        if sim.get('terminal') in tracker_in_hands
    ]
    mts_sim_cards.sort(key=lambda a: a[1], reverse=False)
    return mts_sim_cards


@exception_handler
def get_diff_terminals():
    """Возвращает разницу терминалов."""
    all_trackers = api_request_terminal_list()
    id_trackers_on_hands = {term['terminal'] for term in api_request_human_tracker_list()}
    id_trackers_in_obj = {obj['terminal'] for obj in api_request_object_list()}
    union_trackers = id_trackers_on_hands | id_trackers_in_obj
    diff_trackers_all_vs_install_and_on_hands = {
        tracker['imei'] for tracker in all_trackers
        if tracker['id'] not in union_trackers and tracker['active']
    }
    intersection_trackers = id_trackers_on_hands & id_trackers_in_obj
    diff_trackers_on_hands_and_in_obj = {
        tracker['imei'] for tracker in all_trackers
        if tracker['id'] in intersection_trackers
    }
    return diff_trackers_all_vs_install_and_on_hands, diff_trackers_on_hands_and_in_obj


@exception_handler
def check_sim_cards_in_dj():
    """Проверка сим-карт внутри проекта."""
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


@exception_handler
def get_api_schedule_man(date_target):
    """Возвращает имя и фамилию человека, чья смена по дате в графике."""
    human_id = int()
    for schedule_date in api_request_schedule():
        if datetime.date.fromisoformat(schedule_date.get('date')) == date_target:
            human_id = schedule_date.get('human')
            break
    if not human_id:
        return 'Дежурный не назначен'
    humans = api_request_humans()
    name_id = int()
    last_name = str()
    for human in humans:
        if human.get('id') == human_id:
            last_name = human.get('last_name')
            name_id = human.get('name_id')
            break
    names = api_request_human_names()
    name = str()
    for name in names:
        if name.get('id') == name_id:
            name = name.get('name')
            break
    return f'{name} {last_name}'


@exception_handler
def get_stock(telegram_id):
    """Возвращает словарь моделей со списком трекеров."""
    human_id = get_id_human_for_from_telegram_id(telegram_id)
    tracker_id_list = [row.get('terminal') for row in api_request_human_tracker_list() if row.get('human') == human_id]
    trackers = dict()
    tracker_models = {row.get('id'): row.get('model') for row in api_request_tracker_models()}
    for row in api_request_terminal_list():
        if row.get('id') in tracker_id_list:
            trackers.setdefault(tracker_models.get(row.get('model')),[]).append((row.get('imei'), row.get('serial_number')))
    return trackers


@exception_handler
def get_price_logistic():
    """Возвращает прайс выездов."""
    return (f'{row.get("city")} - {row.get("cost")}' for row in api_request_price_logistic())


@exception_handler
def get_price_trackers():
    """Возвращает прайс оборудования."""
    return (f'{row.get("tracker_model")} - {row.get("cost")}' for row in api_request_price_trackers())


@exception_handler
def get_services():
    """Возвращает услуги."""
    return (f'{row.get("service")} - {row.get("cost")}' for row in api_request_price_services())

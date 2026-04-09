"""
FinTrack — Flask backend
Проксі до SalesDrive API + збереження налаштувань
"""
from flask import Flask, jsonify, request, send_from_directory
import requests
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='.')

# Файл для збереження конфігурації (у реальному проекті — БД)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# ══════════════════════════════════════════
#  СТАТИЧНІ ФАЙЛИ
# ══════════════════════════════════════════
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# ══════════════════════════════════════════
#  SALESDRIVE PROXY
# ══════════════════════════════════════════

@app.route('/api/salesdrive/test', methods=['POST'])
def salesdrive_test():
    """Перевірка підключення до SalesDrive"""
    body = request.get_json()
    domain = body.get('domain', '').strip().rstrip('/')
    api_key = body.get('api_key', '').strip()

    if not domain or not api_key:
        return jsonify({'ok': False, 'error': 'Вкажіть домен та API ключ'}), 400

    # Якщо домен без схеми — додаємо
    if not domain.startswith('http'):
        url = f'https://{domain}.salesdrive.me/api/order/list/'
    else:
        url = f'{domain}/api/order/list/'

    try:
        resp = requests.get(
            url,
            headers={'Form-Api-Key': api_key},
            params={'page': 1, 'limit': 1},
            timeout=10
        )
        if resp.status_code == 200:
            return jsonify({'ok': True, 'message': 'Підключення успішне'})
        elif resp.status_code == 401:
            return jsonify({'ok': False, 'error': 'Невірний API ключ'}), 200
        else:
            return jsonify({'ok': False, 'error': f'Помилка {resp.status_code}: {resp.text[:200]}'}), 200
    except requests.exceptions.ConnectionError:
        return jsonify({'ok': False, 'error': f'Не вдалось підключитись до {domain}. Перевірте домен.'}), 200
    except requests.exceptions.Timeout:
        return jsonify({'ok': False, 'error': 'Timeout — сервер не відповідає'}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 200


@app.route('/api/salesdrive/orders', methods=['GET'])
def salesdrive_orders():
    """Вивантаження замовлень із SalesDrive"""
    config = load_config()
    sd = config.get('salesdrive', {})

    if not sd.get('api_key') or not sd.get('domain'):
        return jsonify({'ok': False, 'error': 'SalesDrive не налаштований. Перейдіть у Налаштування.'}), 400

    domain = sd['domain'].strip().rstrip('/')
    api_key = sd['api_key'].strip()

    if not domain.startswith('http'):
        base_url = f'https://{domain}.salesdrive.me'
    else:
        base_url = domain

    # Параметри фільтрації
    date_from = request.args.get('from')
    date_to   = request.args.get('to')
    page      = int(request.args.get('page', 1))
    limit     = int(request.args.get('limit', 100))

    params = {'page': page, 'limit': limit}
    if date_from:
        params['filter[orderTime][from]'] = date_from
    if date_to:
        params['filter[orderTime][to]'] = date_to

    try:
        resp = requests.get(
            f'{base_url}/api/order/list/',
            headers={'Form-Api-Key': api_key},
            params=params,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        # Нормалізуємо відповідь
        orders = data if isinstance(data, list) else data.get('data', data.get('items', []))
        total  = len(orders) if isinstance(data, list) else data.get('total', len(orders))

        # Перетворюємо в уніфікований формат для фронтенду
        normalized = [normalize_order(o) for o in orders]

        return jsonify({
            'ok': True,
            'orders': normalized,
            'total': total,
            'page': page,
        })

    except requests.exceptions.HTTPError as e:
        return jsonify({'ok': False, 'error': f'HTTP {e.response.status_code}: {e.response.text[:300]}'}), 200
    except requests.exceptions.ConnectionError:
        return jsonify({'ok': False, 'error': 'Не вдалось підключитись до SalesDrive'}), 200
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 200


def normalize_order(o):
    """Приводить замовлення SalesDrive до єдиного формату"""
    # Сума замовлення
    amount = float(o.get('totalPrice') or o.get('amount') or o.get('price') or 0)

    # Список товарів
    products = o.get('products') or o.get('items') or []
    product_names = ', '.join([
        p.get('name') or p.get('productName') or '—'
        for p in (products if isinstance(products, list) else [])
    ]) or o.get('description') or '—'

    # Дата
    raw_date = o.get('orderTime') or o.get('createdAt') or o.get('date') or ''
    try:
        dt = datetime.fromisoformat(str(raw_date).replace('Z', '+00:00'))
        date_str = dt.strftime('%d.%m.%Y')
    except Exception:
        date_str = str(raw_date)[:10] if raw_date else '—'

    # Канал / джерело
    source = (
        o.get('source') or
        o.get('channelName') or
        o.get('utmSource') or
        o.get('channel') or
        'SalesDrive'
    )

    # Статус
    status_map = {
        1: 'pending', 2: 'pending', 3: 'paid', 4: 'paid',
        5: 'refund', 6: 'refund', 7: 'paid',
    }
    status_id = o.get('statusId') or o.get('status') or 0
    status = status_map.get(int(status_id) if str(status_id).isdigit() else 0, 'pending')

    return {
        'id':       o.get('id') or o.get('orderId') or '—',
        'date':     date_str,
        'source':   source,
        'products': product_names,
        'amount':   amount,
        'qty':      sum(int(p.get('amount') or p.get('quantity') or 1) for p in (products if isinstance(products, list) else [])) or 1,
        'status':   status,
        'raw':      o,  # повний об'єкт для дебагу
    }


# ══════════════════════════════════════════
#  КОНФІГУРАЦІЯ
# ══════════════════════════════════════════

@app.route('/api/config/salesdrive', methods=['GET'])
def get_salesdrive_config():
    config = load_config()
    sd = config.get('salesdrive', {})
    # Не повертаємо API ключ повністю — тільки маску
    masked = {}
    if sd.get('domain'):
        masked['domain'] = sd['domain']
    if sd.get('api_key'):
        key = sd['api_key']
        masked['api_key_masked'] = key[:4] + '****' + key[-4:] if len(key) > 8 else '****'
        masked['connected'] = True
    return jsonify(masked)


@app.route('/api/config/salesdrive', methods=['POST'])
def save_salesdrive_config():
    body = request.get_json()
    domain  = body.get('domain', '').strip().rstrip('/')
    api_key = body.get('api_key', '').strip()

    if not domain or not api_key:
        return jsonify({'ok': False, 'error': 'Заповніть всі поля'}), 400

    config = load_config()
    config['salesdrive'] = {'domain': domain, 'api_key': api_key}
    save_config(config)
    return jsonify({'ok': True, 'message': 'Збережено'})


@app.route('/api/config/salesdrive', methods=['DELETE'])
def delete_salesdrive_config():
    config = load_config()
    config.pop('salesdrive', None)
    save_config(config)
    return jsonify({'ok': True})


# ══════════════════════════════════════════
#  АНАЛІТИКА З РЕАЛЬНИХ ДАНИХ
# ══════════════════════════════════════════

@app.route('/api/analytics/summary', methods=['GET'])
def analytics_summary():
    """Агрегує замовлення SalesDrive у фінансову зведення"""
    config = load_config()
    sd = config.get('salesdrive', {})

    if not sd.get('api_key') or not sd.get('domain'):
        return jsonify({'ok': False, 'error': 'SalesDrive не налаштований'}), 400

    domain = sd['domain'].strip().rstrip('/')
    api_key = sd['api_key'].strip()
    base_url = f'https://{domain}.salesdrive.me' if not domain.startswith('http') else domain

    # Визначаємо період
    period = request.args.get('period', 'month')
    now = datetime.now()
    if period == 'month':
        date_from = now.replace(day=1).strftime('%Y-%m-%d')
    elif period == 'quarter':
        month = ((now.month - 1) // 3) * 3 + 1
        date_from = now.replace(month=month, day=1).strftime('%Y-%m-%d')
    else:  # year
        date_from = now.replace(month=1, day=1).strftime('%Y-%m-%d')
    date_to = now.strftime('%Y-%m-%d')

    # Завантажуємо всі сторінки
    all_orders = []
    page = 1
    while True:
        try:
            resp = requests.get(
                f'{base_url}/api/order/list/',
                headers={'Form-Api-Key': api_key},
                params={
                    'page': page, 'limit': 100,
                    'filter[orderTime][from]': date_from,
                    'filter[orderTime][to]': date_to,
                },
                timeout=30
            )
            data = resp.json()
            orders = data if isinstance(data, list) else data.get('data', data.get('items', []))
            if not orders:
                break
            all_orders.extend(orders)
            if isinstance(data, list) or len(orders) < 100:
                break
            page += 1
        except Exception:
            break

    # Агрегація
    total_revenue = 0
    by_source = {}
    by_month = {}
    order_count = 0

    for o in all_orders:
        n = normalize_order(o)
        if n['status'] == 'refund':
            continue
        amount = n['amount']
        total_revenue += amount
        order_count += 1

        src = n['source']
        by_source[src] = by_source.get(src, 0) + amount

        # Місяць
        month_key = str(n['date'])[:7] if len(str(n['date'])) >= 7 else 'Невідомо'
        by_month[month_key] = by_month.get(month_key, 0) + amount

    return jsonify({
        'ok': True,
        'period': {'from': date_from, 'to': date_to},
        'total_revenue': total_revenue,
        'order_count': order_count,
        'avg_order': total_revenue / order_count if order_count else 0,
        'by_source': by_source,
        'by_month': dict(sorted(by_month.items())),
    })


if __name__ == '__main__':
    print('=' * 50)
    print('  FinTrack сервер запущено')
    print('  Відкрийте: http://localhost:5000')
    print('=' * 50)
    app.run(debug=True, port=5000)

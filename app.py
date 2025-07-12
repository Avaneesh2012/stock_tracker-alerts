from flask import Flask, render_template, request, jsonify, redirect, url_for
import yfinance as yf
import json
import threading
import time
import traceback
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)

ALERT_FILE = 'alerts.json'

# 🔐 Email settings — fill in your info here
EMAIL_ADDRESS = "avaneesh.lakkamraju@gmail.com"         # your Gmail address
EMAIL_PASSWORD = "mmhd lymt nrnp tovt"      # 16-char Gmail app password
ALERT_RECIPIENT = "avaneesh.lakkamraju@gmail.com"       # where alerts will be sent


# ----------------------------
# Alert System Functions
# ----------------------------

def load_alerts():
    try:
        with open(ALERT_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_alert(alert):
    alerts = load_alerts()
    alerts.append(alert)
    with open(ALERT_FILE, 'w') as f:
        json.dump(alerts, f)

def send_email_alert(subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = ALERT_RECIPIENT

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
        print(f"[EMAIL] Sent: {subject}")
    except Exception as e:
        print("[EMAIL ERROR]", e)

def check_alerts():
    while True:
        alerts = load_alerts()
        triggered = []

        for alert in alerts:
            try:
                symbol = alert['symbol']
                stock = yf.Ticker(symbol)
                hist = stock.history(period='2d')
                if hist.empty:
                    continue
                price = float(hist['Close'].iloc[-1])
                condition = alert['type']
                target = alert['price']

                if (condition == 'above' and price >= target) or (condition == 'below' and price <= target):
                    print(f"[ALERT] {symbol}: Current price ${price:.2f} is {condition} ${target:.2f}")
                    send_email_alert(
                        f"🔔 Price Alert for {symbol}",
                        f"{symbol} has hit ${price:.2f}, which is {condition} your target of ${target:.2f}."
                    )
                    triggered.append(alert)

            except Exception as e:
                print(f"[ERROR] checking alert for {alert.get('symbol')}: {e}")
                traceback.print_exc()

        # Remove triggered alerts
        if triggered:
            alerts = [a for a in alerts if a not in triggered]
            with open(ALERT_FILE, 'w') as f:
                json.dump(alerts, f)

        time.sleep(60)

# Start background alert checker
threading.Thread(target=check_alerts, daemon=True).start()

# ----------------------------
# Flask Routes
# ----------------------------

@app.route('/', methods=['GET', 'POST'])
def index():
    query = 'AAPL'
    period = '1mo'
    stocks_data = []
    chart_data = {}

    if request.method == 'POST':
        query = request.form.get('query', 'AAPL').strip()
        range_choice = request.form.get('range', '1mo')
        period = {
            '7d': '7d',
            '1mo': '1mo',
            '6mo': '6mo',
            '1y': '1y'
        }.get(range_choice, '1mo')

        queries = [x.strip().upper() for x in query.split(',') if x.strip()]

        for ticker in queries:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period=period)

                stocks_data.append({
                    'symbol': ticker,
                    'name': info.get('shortName', ticker),
                    'price': round(info.get('regularMarketPrice', 0), 2),
                    'currency': info.get('currency', 'USD')
                })

                chart_data[ticker] = {
                    'labels': [d.strftime('%Y-%m-%d') for d in hist.index],
                    'prices': [round(p, 2) for p in hist['Close']]
                }

            except Exception as e:
                print(f"[ERROR] loading {ticker}: {e}")
                traceback.print_exc()

    alerts = load_alerts()

    return render_template('index.html', stocks=stocks_data, chart_data=chart_data,
                           current_query=query, selected_period=period,
                           alerts=alerts)

@app.route('/add_alert', methods=['POST'])
def add_alert():
    symbol = request.form.get('alert_symbol', '').upper()
    alert_type = request.form.get('alert_type')
    alert_price = float(request.form.get('alert_price'))

    save_alert({
        'symbol': symbol,
        'type': alert_type,
        'price': alert_price
    })

    return redirect(url_for('index'))

@app.route('/delete_alert', methods=['POST'])
def delete_alert():
    symbol = request.form.get('symbol')
    alert_type = request.form.get('type')
    price = float(request.form.get('price'))

    alerts = load_alerts()
    updated_alerts = [a for a in alerts if not (
        a['symbol'] == symbol and a['type'] == alert_type and a['price'] == price
    )]

    with open(ALERT_FILE, 'w') as f:
        json.dump(updated_alerts, f)

    return redirect(url_for('index'))

@app.route('/realtime')
def realtime():
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({'error': 'Missing ticker parameter'}), 400
    ticker = ticker.upper()
    print(f"[REALTIME] Request: {ticker}")
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='2d')
        if hist.empty:
            raise Exception("No data")
        price = float(hist['Close'].iloc[-1])
        prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
        return jsonify({
            'symbol': ticker,
            'price': round(price, 2),
            'previousClose': round(prev, 2),
            'change': round(price - prev, 2),
            'currency': stock.fast_info.get('currency', 'USD')
        })
    except Exception as e:
        print(f"[ERROR] realtime {ticker}: {e}")
        traceback.print_exc()
        return jsonify({'error': 'Unable to fetch stock info'})


if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=8000)

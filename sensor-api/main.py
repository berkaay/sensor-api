from flask import Flask, request, jsonify
import requests, re, os
from datetime import datetime, timedelta

app = Flask(__name__)
API_KEY = os.getenv("API_KEY")


def extract_app_id_and_platform(url):
    if 'play.google.com' in url:
        match = re.search(r'id=([a-zA-Z0-9._]+)', url)
        return match.group(1), 'android' if match else (None, None)
    elif 'apps.apple.com' in url or 'itunes.apple.com' in url:
        match = re.search(r'id(\d+)', url)
        return match.group(1), 'ios' if match else (None, None)
    return None, None


def previous_quarter_range():
    now = datetime.utcnow()
    q = (now.month - 1) // 3  # current quarter index
    start_month = (q - 1) * 3 + 1 if q > 0 else 10
    year = now.year if q > 0 else now.year - 1
    start = datetime(year, start_month, 1)
    end = datetime(year, start_month + 3, 1) - timedelta(days=1)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


@app.route("/")
def home():
    return "✅ SensorTower Summary API is live."


@app.route("/summary")
def summary():
    url = request.args.get("url", "")
    country = request.args.get("country", "US").upper()

    app_id, platform = extract_app_id_and_platform(url)
    if not app_id or not platform:
        return jsonify({"error": "Invalid or unsupported URL"}), 400

    headers = {"Authorization": f"Bearer {API_KEY}"}

    # 1. Fetch last 30 days downloads & revenue
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    date_range = {
        "start_date": start_date.strftime('%Y-%m-%d'),
        "end_date": end_date.strftime('%Y-%m-%d'),
    }

    sales_url = f"https://api.sensortower.com/v1/{platform}/sales_report_estimates"
    sales_params = {
        "app_ids": app_id,
        "countries": country,
        "date_granularity": "daily",
        **date_range,
    }

    try:
        sales = requests.get(sales_url, headers=headers, params=sales_params).json()
        downloads = sum(day.get("au", 0) for day in sales if day.get("cc") == country)
        revenue_cents = sum(day.get("ar", 0) for day in sales if day.get("cc") == country)
        revenue = revenue_cents / 100
    except:
        downloads = revenue = 0

    # 2. Fetch RPD from comparison endpoint
    rpd_url = f"https://api.sensortower.com/v1/{platform}/sales_report_estimates_comparison_attributes"
    rpd_params = {"app_ids": app_id}
    try:
        rpd_resp = requests.get(rpd_url, headers=headers, params=rpd_params).json()
        rpd = float(rpd_resp.get("aggregate_tags", {}).get("Revenue Per Download", 0))
    except:
        rpd = 0.0

    # 3. Fetch retention from previous full quarter
    start_q, end_q = previous_quarter_range()
    retention_url = f"https://api.sensortower.com/v1/{platform}/usage/retention"
    retention_params = {
        "app_ids": app_id,
        "country": country,
        "start_date": start_q,
        "end_date": end_q,
        "date_granularity": "quarterly"
    }

    try:
        retention_resp = requests.get(retention_url, headers=headers, params=retention_params).json()
        corrected = retention_resp["app_data"][0]["corrected_retention"]
        retention = {
            "D1": f"{round(corrected[0]*100, 1)}%",
            "D7": f"{round(corrected[6]*100, 1)}%",
            "D30": f"{round(corrected[29]*100, 1)}%"
        }
    except:
        retention = {"D1": None, "D7": None, "D30": None}

    return jsonify({
        "platform": platform,
        "app_id": app_id,
        "country": country,
        "downloads_last_30_days": downloads,
        "revenue_last_30_days_usd": round(revenue, 2),
        "rpd_usd": round(rpd, 4),
        "retention_previous_quarter": retention
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
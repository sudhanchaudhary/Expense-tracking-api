import requests
from decimal import Decimal
from datetime import datetime
from django.conf import settings


def get_exchange_rate(from_currency: str, to_currency: str) -> dict:
    if from_currency == to_currency:
        return {
            "rate": Decimal("1.00"),
            "date": datetime.now().date().isoformat(),
            "from": from_currency,
            "to": to_currency
        }
    
    try:
        api_url = getattr(settings, 'EXCHANGE_RATE_API_URL', 'https://open.er-api.com/v6/latest')
        api_key = getattr(settings, 'EXCHANGE_RATE_API_KEY', '')
        params = {
            "base": from_currency,
            "symbols": to_currency
        }
        if api_key:
            params["apikey"] = api_key
        response = requests.get(api_url, params=params, timeout=5)
        response.raise_for_status()  
        data = response.json()
        if "rates" not in data:
            raise Exception(f"API error: {data}")
        
        if to_currency not in data.get("rates", {}):
            raise Exception(f"Currency {to_currency} not found")
        rate = Decimal(str(data["rates"][to_currency]))  
        date = data.get("date", datetime.now().date().isoformat())
        return {
            "rate": rate,
            "date": date,
            "from": from_currency,
            "to": to_currency
        }
    except Exception as e:
        raise Exception(f"Failed to fetch exchange rate: {str(e)}")


def convert_amount(amount: Decimal, from_currency: str, to_currency: str) -> dict:
    exchange_info = get_exchange_rate(from_currency, to_currency)
    converted = amount * exchange_info["rate"]
    return {
        "original_amount": str(amount),
        "original_currency": from_currency,
        "converted_amount": str(round(converted, 2)),
        "converted_currency": to_currency,
        "rate": str(exchange_info["rate"]),
        "date": exchange_info["date"]
    }
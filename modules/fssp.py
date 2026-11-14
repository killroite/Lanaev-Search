import os
import os
import requests

def check_fssp(fio: str, bdate: str, region: str = "") -> dict:
    token = os.getenv("DADATA_TOKEN")
    secret = os.getenv("DADATA_SECRET")
    
    if not token or not secret:
        return {"error": "Ключи DaData не настроены."}

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {token}",
        "X-Secret": secret
    }

    # Делаем запрос напрямую к ФССП (без чистки ФИО)
    url = "https://api.dadata.ru/v2/find"
    payload = {
        "query": {
            "fio": fio,
            "birthdate": bdate
        },
        "type": "fssp"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        
        # Если DaData вернул ошибку (например, нет тарифа)
        if response.status_code != 200:
            return {"error": f"Отказ DaData: {response.text[:100]}"}

        data = response.json()
        
        if not data or "data" not in data:
            return {"info": "Нет данных."}
            
        items = data["data"].get("items", [])
        if not items:
            return {"info": "Долгов не найдено."}

        results = []
        for item in items:
            results.append({
                "Сумма": item.get("sum") or "0",
                "Номер ИП": item.get("number") or "—",
            })
        return {"total": len(results), "results": results}

    except Exception as e:
        return {"error": "DaData временно недоступен."}

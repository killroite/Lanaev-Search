import os
import requests

def check_fssp(fio: str, bdate: str, region: str = "") -> dict:
    """
    Поиск через официальный API DaData (ФССП).
    """
    token = os.getenv("DADATA_TOKEN")
    secret = os.getenv("DADATA_SECRET")
    
    if not token or not secret:
        return {"error": "Ключи DaData не настроены в Environment."}

    url = "https://cleaner.dadata.ru/api/v1/clean/name"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {token}",
        "X-Secret": secret
    }

    # DaData ждет запрос в формате JSON
    payload = [{
        "query": fio,
        "count": 1
    }]

    try:
        # Сначала чистим ФИО (чтобы DaData разбил его на Фамилию, Имя, Отчество)
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data or not data[0].get("result"):
            return {"info": "Не удалось распознать ФИО."}

        name_data = data[0]["result"]
        
        # Формируем запрос к ФССП
        fssp_url = "https://api.dadata.ru/v2/fssp/find"
        fssp_payload = {
            "query": {
                "fio": name_data.get("name"), # Полное ФИО
                "birthdate": bdate,
                "region": region
            }
        }
        
        fssp_response = requests.post(fssp_url, json=fssp_payload, headers=headers, timeout=15)
        fssp_response.raise_for_status()
        fssp_data = fssp_response.json()

        if not fssp_data.get("items"):
            return {"info": "Исполнительных производств не найдено."}

        results = []
        for item in fssp_data["items"]:
            results.append({
                "ФИО": item.get("name"),
                "Дата рождения": item.get("birthdate"),
                "Номер ИП": item.get("number"),
                "Сумма долга": item.get("sum"),
                "Отделение": item.get("department")
            })

        return {"total": len(results), "results": results}

    except Exception as e:
        return {"error": f"Ошибка DaData: {str(e)}"}

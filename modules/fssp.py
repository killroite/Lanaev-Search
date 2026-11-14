import os
import requests

def check_fssp(fio: str, bdate: str, region: str = "") -> dict:
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

    # 1. Отправляем ФИО на чистку
    payload = [fio]
    
    try:
        # Чистим ФИО
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status() # Если ошибка 400, код перейдет в блок except HTTPError
        data = response.json()
        
        # Безопасная проверка ответа
        if not isinstance(data, list) or not data or not isinstance(data[0], dict) or not data[0].get("result"):
            return {"info": "Не удалось распознать ФИО."}

        name_data = data[0]["result"]
        
        # 2. Ищем в базе ФССП
        fssp_url = "https://api.dadata.ru/v2/find"
        fssp_payload = {
            "query": {
                "fio": name_data.get("name"),
                "birthdate": bdate,
                "region": region
            },
            "type": "fssp"
        }
        
        fssp_response = requests.post(fssp_url, json=fssp_payload, headers=headers, timeout=15)
        
        # Если DaData вернул ошибку (например, нет тарифа ФССП), выводим понятный текст
        if fssp_response.status_code != 200:
            return {"error": f"DaData отказал: {fssp_response.text}"}

        fssp_data = fssp_response.json()

        # Проверяем, есть ли результаты
        if not isinstance(fssp_data, dict) or not fssp_data.get("data") or not fssp_data["data"].get("items"):
            return {"info": "Исполнительных производств не найдено."}

        results = []
        for item in fssp_data["data"]["items"]:
            results.append({
                "Сумма долга": item.get("sum") or "0",
                "Номер ИП": item.get("number") or "—",
                "Отделение": item.get("department") or "—",
                "Тема": item.get("subject") or "—"
            })

        return {"total": len(results), "results": results}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            return {"error": "DaData отклонил запрос. Проверьте правильность ФИО и даты (формат 1990-01-01)."}
        return {"error": f"Ошибка HTTP: {str(e)}"}
    except Exception as e:
        return {"error": f"Ошибка DaData: {str(e)}"}

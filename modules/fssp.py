import os
import requests

def check_fssp(fio: str, bdate: str, region: str = "") -> dict:
    """
    Поиск через официальный API DaData (ФССП) по единому эндпоинту.
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

    # 1. Сначала чистим ФИО, чтобы получить правильные части (Фамилия, Имя, Отчество)
    payload = [fio]
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data or not data[0].get("result"):
            return {"info": "Не удалось распознать ФИО."}

        name_data = data[0]["result"]
        
        # 2. Формируем запрос к базе ФССП
        fssp_url = "https://api.dadata.ru/v2/find"
        fssp_payload = {
            "query": {
                "fio": name_data.get("name"),
                "birthdate": bdate,
                "region": region
            },
            "type": "fssp" # Указываем, что ищем в базе ФССП
        }
        
        fssp_response = requests.post(fssp_url, json=fssp_payload, headers=headers, timeout=15)
        fssp_response.raise_for_status()
        fssp_data = fssp_response.json()

        # Обрабатываем результат
        if not fssp_data.get("data") or not fssp_data["data"].get("items"):
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
            return {"error": "DaData отклонил запрос. Проверьте правильность ФИО и даты (формат ГГГГ-ММ-ДД или ДД.ММ.ГГГГ)."}
        return {"error": f"Ошибка HTTP: {str(e)}"}
    except Exception as e:
        return {"error": f"Ошибка DaData: {str(e)}"}

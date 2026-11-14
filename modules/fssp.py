import requests
from bs4 import BeautifulSoup

def check_fssp(fio: str, bdate: str, region: str = "") -> dict:
    url = "https://fssp.gov.ru/iss/ip"
    
    payload = {
        "is[ext_sys]": "0",
        "is[rt]": "0",
        "is[ip_type]": "1",
        "is[last_name]": fio.split()[0] if len(fio.split()) > 0 else "",
        "is[first_name]": fio.split()[1] if len(fio.split()) > 1 else "",
        "is[patronymic]": fio.split()[2] if len(fio.split()) > 2 else "",
        "is[bdate]": bdate,
        "is[region]": region,
        "token": "gmpb"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.post(url, data=payload, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", class_="table")
        
        if not table:
            return {"info": "Исполнительных производств не найдено."}
        
        results = []
        rows = table.find_all("tr")[1:]
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 6:
                results.append({
                    "ФИО": cols[0].get_text(strip=True),
                    "Дата рождения": cols[1].get_text(strip=True),
                    "Номер ИП": cols[2].get_text(strip=True),
                    "Сумма долга": cols[4].get_text(strip=True),
                    "Отделение": cols[5].get_text(strip=True)
                })
        
        if not results:
            return {"info": "Исполнительных производств не найдено."}
        
        return {"total": len(results), "results": results}

    except Exception as e:
        return {"error": f"Ошибка ФССП: {str(e)}"}

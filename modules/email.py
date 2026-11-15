import aiohttp

async def check_email(email: str) -> dict:
    url = f"https://emailrep.io/{email}"
    headers = {"User-Agent": "SWILL-OSINT-BOT"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    return {"info": "Email не найден в базах."}
                data = await resp.json()
                
        return {
            "Email": data.get("email"),
            "Репутация": data.get("reputation"),
            "Подозрительный": "Да" if data.get("suspicious") else "Нет",
            "Утечки": data.get("details", {}).get("breaches", "Нет данных")
        }
    except Exception as e:
        return {"error": f"Ошибка API: {str(e)}"}

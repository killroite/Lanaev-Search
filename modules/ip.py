import aiohttp

async def check_ip(ip: str) -> dict:
    url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,isp,org,as,query"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                
        if data.get("status") == "fail":
            return {"error": data.get("message", "Неверный IP")}
            
        return {
            "IP": data.get("query"),
            "Страна": data.get("country"),
            "Регион": data.get("regionName"),
            "Город": data.get("city"),
            "Провайдер": data.get("isp"),
            "Организация": data.get("org")
        }
    except Exception as e:
        return {"error": f"Ошибка API: {str(e)}"}

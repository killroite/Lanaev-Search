import aiohttp

async def get_avito_link(phone: str) -> str:
    clean = phone.replace("+", "").replace(" ", "")
    return f"https://www.avito.ru/all?q={clean}"

async def get_youla_link(phone: str) -> str:
    clean = phone.replace("+", "").replace(" ", "")
    return f"https://youla.ru/search?q={clean}"

async def check_numverify(phone: str) -> dict:
    """
    Проверка через публичный API (в будущем можно заменить на ключ).
    Сейчас возвращает базовую инфу, чтобы не падало.
    """
    return {"info": "Для получения имени из GetContact требуется платная подписка."}

import aiohttp
import re

async def check_messengers(phone: str) -> dict:
    result = {"telegram": "Неизвестно", "whatsapp": "Неизвестно", "viber": "Неизвестно", "vk": "Неизвестно"}
    
    clean_phone = re.sub(r"[^\d]", "", phone)
    if clean_phone.startswith("8"):
        clean_phone = "7" + clean_phone[1:]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession() as session:
        # 1. WhatsApp
        try:
            async with session.get(f"https://wa.me/{clean_phone}", headers=headers, allow_redirects=True) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if "WhatsApp" in text and "phone" in text:
                        result["whatsapp"] = "✅ Зарегистрирован"
                    else:
                        result["whatsapp"] = "❌ Не найден"
                else:
                    result["whatsapp"] = "⚠️ Ошибка проверки"
        except:
            result["whatsapp"] = "⚠️ Ошибка сети"

        # 2. Viber
        try:
            async with session.get(f"https://chats.viber.com/{clean_phone}", headers=headers) as resp:
                if resp.status == 200:
                    result["viber"] = "✅ Зарегистрирован"
                else:
                    result["viber"] = "❌ Не найден"
        except:
            result["viber"] = "⚠️ Ошибка сети"

        # 3. VK
        try:
            vk_url = f"https://m.vk.com/search?c[q]=%2B{clean_phone}&c[section]=people"
            async with session.get(vk_url, headers=headers) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    if "Ничего не найдено" in html or "ничего не найдено" in html:
                        result["vk"] = "❌ Не найден"
                    else:
                        result["vk"] = "✅ Найден (возможно)"
                else:
                    result["vk"] = "⚠️ Ошибка (ВК блокирует)"
        except:
            result["vk"] = "⚠️ Ошибка сети"

    return result

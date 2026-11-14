import asyncio, sqlite3, os, re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiohttp import web

from config import BOT_TOKEN, DB_PATH

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("""CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, query TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.commit()

PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")

def detect_type(q: str) -> str:
    q = q.strip()
    if q.startswith("@"): return "tg_username"
    if "vk.com/" in q: return "vk_link"
    if "ok.ru/" in q: return "ok_link"
    if PHONE_RE.match(q): return "phone"
    return "text"

def analyze_phone(raw: str) -> dict:
    try:
        import phonenumbers
        from phonenumbers import geocoder, carrier
        num = phonenumbers.parse(raw, None)
        if not phonenumbers.is_valid_number(num):
            return {"valid": False}
        return {
            "valid": True,
            "e164": phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164),
            "national": phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.NATIONAL),
            "region": geocoder.description_for_number(num, "ru") or "—",
            "carrier": carrier.name_for_number(num, "ru") or "—",
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}

@dp.message(Command("start"))
async def start(m: Message):
    await m.answer(
        "SWILL OSINT BOT\n\n"
        "Отправь:\n"
        "• номер (+7..., +375..., +380...)\n"
        "• @username (Telegram)\n"
        "• ссылку vk.com/... или ok.ru/...\n"
        "• любой текст"
    )

@dp.message(F.text)
async def handle(m: Message):
    q = m.text.strip()
    conn.execute("INSERT INTO logs(user_id, query) VALUES(?,?)", (m.from_user.id, q))
    conn.commit()

    t = detect_type(q)
    report = [f"SWILL // запрос: {q}", f"тип: {t}", ""]

    if t == "phone":
        p = analyze_phone(q)
        if p.get("valid"):
            report += [
                f"E.164: {p['e164']}",
                f"Национальный: {p['national']}",
                f"Регион: {p['region']}",
                f"Оператор: {p['carrier']}",
            ]
        else:
            report.append("Номер невалиден для РФ/BY/UA.")

    if t == "tg_username":
        try:
            chat = await bot.get_chat(q)
            report.append(f"Telegram: id={chat.id}, name={chat.title or chat.full_name}, username={chat.username}")
        except Exception as e:
            report.append(f"Telegram: ошибка {e}")

    report.append("\nЛимит открытых данных. Для расширения — подключай API.")
    await m.answer("\n".join(report)[:4000])

async def health(request):
    return web.Response(text="ok")

async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    await site.start()

async def main():
    await start_web()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())

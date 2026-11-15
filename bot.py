import asyncio, sqlite3, os, re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiohttp import web
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, DB_PATH
from modules.phone import analyze_phone
from modules.fssp import check_fssp
from modules.ip import check_ip
from modules.email import check_email

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("""CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.execute("""CREATE TABLE IF NOT EXISTS tg_history(id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER, username TEXT, old_name TEXT, new_name TEXT, old_username TEXT, new_username TEXT, changed_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.commit()

def detect_type(q: str) -> str:
    q = q.strip()
    if q.startswith("@"): return "tg_username"
    if re.match(r"^\+?[\d\s\-()]{7,20}$", q): return "phone"
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", q): return "ip"
    if "@" in q and "." in q: return "email"
    parts = q.split()
    if len(parts) >= 3 and any(char.isdigit() for char in parts[-1]): return "fssp"
    return "text"

@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Номер", callback_data="menu_phone"), InlineKeyboardButton(text="🕵️ @username", callback_data="menu_tg")],
        [InlineKeyboardButton(text="🌐 IP-адрес", callback_data="menu_ip"), InlineKeyboardButton(text="📧 Email", callback_data="menu_email")],
        [InlineKeyboardButton(text="⚖️ Долги ФССП", callback_data="menu_fssp")]
    ])
    await m.answer("🛡 <b>SWILL OSINT BOT</b>\n\nВыбери действие ниже:", reply_markup=kb)

@dp.callback_query()
async def cb_handler(cb: CallbackQuery):
    await cb.answer()
    texts = {
        "menu_phone": "Введи номер (+7...)",
        "menu_tg": "Введи @username",
        "menu_ip": "Введи IP-адрес (например, 8.8.8.8)",
        "menu_email": "Введи email (например, test@gmail.com)",
        "menu_fssp": "Введи ФИО и дату (Иванов Иван 01.01.1990)"
    }
    await cb.message.answer(texts.get(cb.data, "Неизвестная команда"))

@dp.message(F.text)
async def handle(m: Message):
    q = m.text.strip()
    t = detect_type(q)

    if t == "tg_username":
        clean_user = q.lstrip("@")
        try:
            chat = await bot.get_chat(f"@{clean_user}")
            text = f"🕵️ <b>Профиль:</b> {chat.title or chat.full_name}\n🆔 ID: <code>{chat.id}</code>\n🔗 @{chat.username}"
            await m.answer(text)
        except Exception:
            await m.answer("❌ Пользователь не найден.")
        return

    if t == "ip":
        await m.answer(f"⏳ Ищу данные по IP <b>{q}</b>...")
        res = await check_ip(q)
        if "error" in res:
            await m.answer(f"❌ {res['error']}")
        else:
            text = f"🌐 <b>IP:</b> {res['IP']}\n🇺🇳 <b>Страна:</b> {res['Страна']}\n🏙 <b>Город:</b> {res['Город']}\n📡 <b>Провайдер:</b> {res['Провайдер']}\n🏢 <b>Орг:</b> {res['Организация']}"
            await m.answer(text)
        return

    if t == "email":
        await m.answer(f"⏳ Проверяю email <b>{q}</b>...")
        res = await check_email(q)
        if "error" in res:
            await m.answer(f"❌ {res['error']}")
        elif "info" in res:
            await m.answer(f"ℹ️ {res['info']}")
        else:
            text = f"📧 <b>Email:</b> {res.get('Email')}\n⭐ <b>Репутация:</b> {res.get('Репутация')}\n⚠️ <b>Подозрительный:</b> {res.get('Подозрительный')}\n💧 <b>Утечки:</b> {res.get('Утечки')}"
            await m.answer(text)
        return

    if t == "fssp":
        parts = q.split()
        res = check_fssp(" ".join(parts[:-1]), parts[-1])
        await m.answer(f"⚖️ Результат: {res.get('error') or res.get('info') or 'Найдено'}")
        return

    if t == "phone":
        p = analyze_phone(q)
        if p.get("valid"):
            await m.answer(f"📱 <b>{p['e164']}</b>\nРегион: {p['region']}\nОператор: {p['carrier']}")
        else:
            await m.answer("❌ Невалидный номер.")
        return

    await m.answer("🤷‍♂️ Неизвестный запрос. Проверь формат.")

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
    asyncio.create_task(start_web())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

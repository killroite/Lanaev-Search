import asyncio
import sqlite3
import os
import re

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
from modules.messengers import check_messengers

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("""CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.commit()

def detect_type(q: str) -> str:
    q = q.strip()
    if q.startswith("@"): return "tg_username"
    if re.match(r"^\+?[\d\s\-()]{7,20}$", q): return "phone"
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", q): return "ip"
    if "@" in q and "." in q: return "email"
    return "text"

@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    text = (
        "🛡 <b>SWILL OSINT BOT</b>\n\n"
        "Ваш надежный инструмент для поиска открытой информации.\n"
        "Выберите категорию ниже:"
    )
    await m.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_tools")
async def menu_tools(cb: CallbackQuery):
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Номер (Мессенджеры)", callback_data="menu_phone")],
        [InlineKeyboardButton(text="🌐 IP-адрес", callback_data="menu_ip"), InlineKeyboardButton(text="📧 Email", callback_data="menu_email")],
        [InlineKeyboardButton(text="⚖️ Долги ФССП", callback_data="menu_fssp")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]
    ])
    await cb.message.edit_text("🔍 <b>Инструменты поиска</b>\n\nВыберите нужный инструмент:", reply_markup=kb)

@dp.callback_query(F.data == "menu_devs")
async def menu_devs(cb: CallbackQuery):
    await cb.answer()
    text = (
        "👨‍💻 <b>Разработчики и ресурсы</b>\n\n"
        "Бот создан командой <b>Swill Way</b>.\n\n"
        "📂 <b>Наш GitHub:</b> <a href='https://github.com/killroite/Lanaev-Search'>Lanaev-Search</a>\n"
        "🔗 <b>Связь:</b> @ваш_контакт\n\n"
        "💡 <b>В планах:</b> добавление баз утечек и парсинг соцсетей."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_back")
async def menu_back(cb: CallbackQuery):
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    await cb.message.edit_text("🛡 <b>SWILL OSINT BOT</b>\n\nВыберите категорию ниже:", reply_markup=kb)

@dp.callback_query()
async def cb_handler(cb: CallbackQuery):
    await cb.answer()
    texts = {
        "menu_phone": "Введи номер (+7...)",
        "menu_ip": "Введи IP-адрес",
        "menu_email": "Введи email",
        "menu_fssp": "Введи ФИО и дату"
    }
    await cb.message.answer(texts.get(cb.data, "Неизвестная команда"))

@dp.message(F.text)
async def handle(m: Message):
    q = m.text.strip()
    t = detect_type(q)

    if t == "phone":
        p = analyze_phone(q)
        if not p.get("valid"):
            await m.answer("❌ Невалидный номер.")
            return
        
        text = (
            f"📱 <b>Анализ номера</b>\n"
            f"├ <b>Номер:</b> <code>{p['e164']}</code>\n"
            f"├ <b>Регион:</b> {p['region']}\n"
            f"└ <b>Оператор:</b> {p['carrier']}\n\n"
            f"⏳ <i>Проверяю мессенджеры...</i>"
        )
        await m.answer(text)
        
        mess = await check_messengers(p['e164'])
        
        text = "<b>📊 Наличие аккаунтов:</b>\n"
        text += f"├ Telegram: {mess.get('telegram', '❓')}\n"
        text += f"├ WhatsApp: {mess.get('whatsapp', '❓')}\n"
        text += f"├ Viber: {mess.get('viber', '❓')}\n"
        text += f"└ VK: {mess.get('vk', '❓')}"
        await m.answer(text)
        return

    if t == "ip":
        await m.answer(f"⏳ <i>Ищу данные по IP <b>{q}</b>...</i>")
        res = await check_ip(q)
        if "error" in res:
            await m.answer(f"❌ {res['error']}")
        else:
            text = (
                f"🌐 <b>IP-информация</b>\n"
                f"├ <b>IP:</b> <code>{res['IP']}</code>\n"
                f"├ <b>Страна:</b> {res['Страна']}\n"
                f"├ <b>Город:</b> {res['Город']}\n"
                f"└ <b>Провайдер:</b> {res['Провайдер']}"
            )
            await m.answer(text)
        return

    if t == "email":
        await m.answer(f"⏳ <i>Проверяю email <b>{q}</b>...</i>")
        res = await check_email(q)
        if "error" in res:
            await m.answer(f"❌ {res['error']}")
        elif "info" in res:
            await m.answer(f"ℹ️ {res['info']}")
        else:
            text = (
                f"📧 <b>Email-информация</b>\n"
                f"├ <b>Email:</b> <code>{res.get('Email')}</code>\n"
                f"├ <b>Репутация:</b> {res.get('Репутация')}\n"
                f"└ <b>Утечки:</b> {res.get('Утечки')}"
            )
            await m.answer(text)
        return

    if t == "fssp":
        parts = q.split()
        await m.answer(f"⏳ <i>Ищу долги для <b>{' '.join(parts[:-1])}</b>...</i>")
        res = check_fssp(" ".join(parts[:-1]), parts[-1])
        result = res.get('error') or res.get('info') or '✅ Данные найдены.'
        await m.answer(f"⚖️ <b>ФССП:</b> {result}")
        return

    await m.answer("🤷‍♂️ Неизвестный запрос. Воспользуйтесь меню /start")

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

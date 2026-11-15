import asyncio
import sqlite3
import os
import re
import uuid

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
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
from modules.sherlock import run_sherlock
from modules.pdf_gen import generate_pdf_report
from modules.extra_osint import (
    get_avito_link, get_youla_link, 
    get_vk_search_link, get_ok_search_link,
    get_google_search_link, get_yandex_search_link
)

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("""CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.commit()

def is_allowed(user_id: int) -> bool:
    return True # Доступ открыт для всех

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
        [InlineKeyboardButton(text="🚨 Центр Жалоб", callback_data="menu_report")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    await m.answer("🛡 <b>SWILL OSINT BOT</b>\n\nВыберите категорию:", reply_markup=kb)

@dp.callback_query(F.data == "menu_report")
async def menu_report(cb: CallbackQuery):
    await cb.answer()
    text = (
        "🚨 <b>Центр Жалоб</b>\n\n"
        "Отправь мне @username нарушителя, и я соберу по нему досье "
        "и сгенерирую PDF-отчет для поддержки Telegram."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]])
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_tools")
async def menu_tools(cb: CallbackQuery):
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Номер", callback_data="menu_phone"), InlineKeyboardButton(text="🌐 IP", callback_data="menu_ip")],
        [InlineKeyboardButton(text="📧 Email", callback_data="menu_email"), InlineKeyboardButton(text="⚖️ ФССП", callback_data="menu_fssp")],
        [InlineKeyboardButton(text="🕵️ Поиск по юзернейму", callback_data="menu_tg")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]
    ])
    await cb.message.edit_text("🔍 <b>Инструменты поиска</b>:", reply_markup=kb)

@dp.callback_query(F.data == "menu_back")
async def menu_back(cb: CallbackQuery):
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(text="🚨 Центр Жалоб", callback_data="menu_report")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    await cb.message.edit_text("🛡 <b>SWILL OSINT BOT</b>\n\nВыберите категорию:", reply_markup=kb)

@dp.callback_query(F.data == "menu_devs")
async def menu_devs(cb: CallbackQuery):
    await cb.answer()
    text = (
        "👨‍💻 <b>Разработчики</b>\n\n"
        "Бот создан командой <b>Swill Way</b>.\n"
        "🔗 <b>Связь:</b> @ceokvist"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]])
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query()
async def cb_handler(cb: CallbackQuery):
    await cb.answer()
    texts = {
        "menu_phone": "Введи номер (+7...)",
        "menu_ip": "Введи IP-адрес",
        "menu_email": "Введи email",
        "menu_fssp": "Введи ФИО и дату (Иванов Иван 01.01.1990)",
        "menu_tg": "Введи @username"
    }
    await cb.message.answer(texts.get(cb.data, "Неизвестная команда"))

# --- ФУНКЦИЯ ПОИСКА ПО БАЗЕ ---
async def search_in_base(query: str) -> str:
    file_url = os.getenv("BASE_TXT_URL")
    if not file_url:
        return "❌ Ссылка на базу не настроена."
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                if resp.status != 200:
                    return "❌ Не удалось скачать базу."
                text = await resp.text()
        
        # Ищем в тексте (без учета регистра)
        search_q = query.lower().strip()
        records = text.split("ФИО:")
        
        found = []
        for rec in records:
            if search_q in rec.lower():
                found.append("ФИО:" + rec.strip())
        
        if not found:
            return "🔍 Ничего не найдено в базе."
        
        result_text = f"<b>📁 Найдено {len(found)} совпадений:</b>\n\n"
        for item in found[:3]: # Показываем первые 3
            result_text += f"├ {item[:400]}...\n\n" # Обрезаем длинные строки
        return result_text
        
    except Exception as e:
        return f"❌ Ошибка поиска: {str(e)}"

@dp.message(F.text)
async def handle(m: Message):
    q = m.text.strip()
    t = detect_type(q)

    # --- ПОИСК ПО БАЗЕ (если запрос не похож на телефон/юзернейм) ---
    if t == "text":
        # Исключаем запросы ФССП (где есть дата)
        parts = q.split()
        if len(parts) >= 3 and any(char.isdigit() for char in parts[-1]):
            # Это похоже на ФССП, обрабатываем ниже
            pass
        else:
            await m.answer("⏳ <i>Ищу в базе (это займет пару секунд)...</i>")
            res = await search_in_base(q)
            await m.answer(res)
            return

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
        mess_text = (
            "<b>📊 Наличие аккаунтов:</b>\n"
            f"├ Telegram: {mess.get('telegram', '❓')}\n"
            f"├ WhatsApp: {mess.get('whatsapp', '❓')}\n"
            f"├ Viber: {mess.get('viber', '❓')}\n"
            f"└ VK: {mess.get('vk', '❓')}"
        )
        await m.answer(mess_text)

        avito = await get_avito_link(p['e164'])
        youla = await get_youla_link(p['e164'])
        vk = await get_vk_search_link(p['e164'])
        ok = await get_ok_search_link(p['e164'])
        google = await get_google_search_link(p['e164'])
        yandex = await get_yandex_search_link(p['e164'])
        
        links_text = (
            "<b>🔗 Готовые ссылки для поиска:</b>\n"
            f"├ <a href='{avito}'>Avito</a>\n"
            f"├ <a href='{youla}'>Youla</a>\n"
            f"├ <a href='{vk}'>ВКонтакте</a>\n"
            f"├ <a href='{ok}'>Одноклассники</a>\n"
            f"├ <a href='{yandex}'>Яндекс</a>\n"
            f"└ <a href='{google}'>Google</a>"
        )
        await m.answer(links_text)
        return

    if t == "ip":
        await m.answer(f"⏳ <i>Ищу данные по IP <b>{q}</b>...</i>")
        res = await check_ip(q)
        if "error" in res: await m.answer(f"❌ {res['error']}")
        else:
            text = f"🌐 <b>IP-информация</b>\n├ <b>IP:</b> <code>{res['IP']}</code>\n├ <b>Страна:</b> {res['Страна']}\n├ <b>Город:</b> {res['Город']}\n└ <b>Провайдер:</b> {res['Провайдер']}"
            await m.answer(text)
        return

    if t == "email":
        await m.answer(f"⏳ <i>Проверяю email <b>{q}</b>...</i>")
        res = await check_email(q)
        if "error" in res: await m.answer(f"❌ {res['error']}")
        elif "info" in res: await m.answer(f"ℹ️ {res['info']}")
        else:
            text = f"📧 <b>Email-информация</b>\n├ <b>Email:</b> <code>{res.get('Email')}</code>\n├ <b>Репутация:</b> {res.get('Репутация')}\n└ <b>Утечки:</b> {res.get('Утечки')}"
            await m.answer(text)
        return

    if t == "tg_username":
        clean_user = q.lstrip("@")
        await m.answer(f"⏳ <i>Собираю досье на @{clean_user}...</i>")
        
        tg_data = {}
        try:
            chat = await bot.get_chat(f"@{clean_user}")
            tg_data = {
                "ID": chat.id,
                "Имя": chat.title or chat.full_name,
                "Юзернейм": f"@{chat.username}" if chat.username else "Скрыт",
                "Описание": chat.description[:100] + "..." if chat.description else "Нет",
                "Тип": chat.type
            }
        except Exception:
            tg_data = {"Ошибка": "Профиль не найден или удален"}

        await m.answer("🔎 <i>Проверяю наличие аккаунта на других платформах (Sherlock)...</i>")
        sherlock_res = await run_sherlock(clean_user)
        
        sherlock_text = "Не найден на других сайтах."
        if "results" in sherlock_res:
            sites = [item['site'] for item in sherlock_res['results'][:5]]
            sherlock_text = f"Найден на {sherlock_res['total']} сайтах: {', '.join(sites)}."

        report_data = {
            "Объект": clean_user,
            "Telegram ID": tg_data.get("ID", "—"),
            "Имя/Название": tg_data.get("Имя", "—"),
            "Описание": tg_data.get("Описание", "—"),
            "Следы в сети (Sherlock)": sherlock_text,
            "Ссылка на профиль": f"https://t.me/{clean_user}",
            "Рекомендация": "Отправить жалобу в поддержку Telegram, приложив этот отчет."
        }
        
        filepath = generate_pdf_report(clean_user, report_data)
        caption = f"📄 <b>Досье на @{clean_user} готово!</b>\nДля жалобы перейди: https://telegram.org/support"
        await m.answer_document(FSInputFile(filepath), caption=caption)
        
        if os.path.exists(filepath):
            os.remove(filepath)
        return

    if t == "fssp":
        parts = q.split()
        await m.answer(f"⏳ <i>Ищу долги для <b>{' '.join(parts[:-1])}</b>...</i>")
        res = check_fssp(" ".join(parts[:-1]), parts[-1])
        await m.answer(f"⚖️ <b>ФССП:</b> {res.get('error') or res.get('info') or 'Данные найдены.'}")
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


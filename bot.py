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
    return True

def detect_type(q: str) -> str:
    q = q.strip()
    if q.startswith("@"): return "tg_username"
    if re.match(r"^\+?[\d\s\-()]{7,20}$", q): return "phone"
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", q): return "ip"
    if "@" in q and "." in q: return "email"
    return "text"

LINE = "━━━━━━━━━━━━━━━"

@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(text="🚨 Центр Жалоб", callback_data="menu_report")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    text = (
        f"🛡 <b>SWILL OSINT BOT</b>\n"
        f"{LINE}\n"
        f"👋 Привет, <b>{m.from_user.first_name}</b>!\n\n"
        f"Я — профессиональный инструмент для поиска открытой информации.\n\n"
        f"🔹 <b>Инструменты:</b> Поиск по номеру, IP, Email, ФИО.\n"
        f"🔹 <b>Жалобы:</b> Сбор доказательств.\n"
        f"🔹 <b>Разработчики:</b> Связь и обновления.\n"
        f"{LINE}\n"
        f"<i>Выбери действие ниже:</i>"
    )
    await m.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_report")
async def menu_report(cb: CallbackQuery):
    await cb.answer()
    text = (
        f"🚨 <b>ЦЕНТР ЖАЛОБ</b>\n"
        f"{LINE}\n"
        f"Этот раздел помогает собрать доказательства на скамеров.\n\n"
        f"Отправь @username нарушителя, и я соберу досье и сгенерирую PDF."
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
    text = (
        f"🔍 <b>ИНСТРУМЕНТЫ ПОИСКА</b>\n"
        f"{LINE}\n"
        f"📱 <b>Номер</b> — оператор и мессенджеры.\n"
        f"🌐 <b>IP</b> — провайдер и геолокация.\n"
        f"📧 <b>Email</b> — репутация и утечки.\n"
        f"⚖️ <b>ФССП</b> — проверка долгов.\n"
        f"🕵️ <b>Юзернейм</b> — досье и Sherlock.\n"
        f"🔎 <b>Текст</b> — поиск по базе (просто отправь ФИО)."
    )
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_back")
async def menu_back(cb: CallbackQuery):
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(text="🚨 Центр Жалоб", callback_data="menu_report")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    text = (
        f"🛡 <b>SWILL OSINT BOT</b>\n"
        f"{LINE}\n"
        f"Выбери категорию:"
    )
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_devs")
async def menu_devs(cb: CallbackQuery):
    await cb.answer()
    text = (
        f"👨‍💻 <b>РАЗРАБОТЧИКИ</b>\n"
        f"{LINE}\n"
        f"Бот создан командой <b>Swill Way</b>.\n\n"
        f"🔗 <b>Связь:</b> @ceokvist\n"
        f"📂 <b>GitHub:</b> <a href='https://github.com/killroite/Lanaev-Search'>Lanaev-Search</a>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]])
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query()
async def cb_handler(cb: CallbackQuery):
    await cb.answer()
    texts = {
        "menu_phone": "📱 Введи номер в формате <code>+7...</code>",
        "menu_ip": "🌐 Введи IP-адрес (например, <code>8.8.8.8</code>)",
        "menu_email": "📧 Введи email",
        "menu_fssp": "⚖️ Введи ФИО и дату",
        "menu_tg": "🕵️ Введи <code>@username</code>"
    }
    await cb.message.answer(texts.get(cb.data, "Неизвестная команда"))

# --- ФУНКЦИЯ ПОИСКА ПО БАЗАМ ---
async def search_in_base(query: str) -> str:
    urls = [
        os.getenv("BASE_TXT_URL"),   
        os.getenv("BASE_TXT_URL_2")  
    ]
    
    search_q = query.lower().strip()
    all_found = []
    
    await asyncio.sleep(0)

    for url in urls:
        if not url:
            continue
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
            
            records = text.split("ФИО:")
            
            for rec in records:
                if search_q in rec.lower():
                    all_found.append("ФИО:" + rec.strip())
                    
        except Exception:
            continue
    
    if not all_found:
        return "🔍 Ничего не найдено в базах."
    
    unique_found = list(set(all_found))
    
    result_text = f"<b>📁 Найдено {len(unique_found)} совпадений:</b>\n{LINE}\n\n"
    for item in unique_found[:3]:
        result_text += f"├ {item[:400]}...\n\n"
    return result_text

@dp.message(F.text)
async def handle(m: Message):
    q = m.text.strip()
    t = detect_type(q)

    # Поиск по базе
    if t == "text":
        parts = q.split()
        if not (len(parts) >= 3 and any(char.isdigit() for char in parts[-1])):
            msg = await m.answer("⏳ <i>Ищу в базах...</i>")
            res = await search_in_base(q)
            await msg.edit_text(res)
            return

    if t == "phone":
        p = analyze_phone(q)
        if not p.get("valid"):
            await m.answer("❌ Невалидный номер.")
            return
        
        msg = await m.answer(f"📱 <b>АНАЛИЗ НОМЕРА</b>\n{LINE}\n⏳ <i>Собираю данные...</i>")
        
        mess = await check_messengers(p['e164'])
        
        tg_icon = "🟢" if mess.get('telegram') == "Зарегистрирован" else "🔴"
        wa_icon = "🟢" if mess.get('whatsapp') == "Зарегистрирован" else "🔴"
        vb_icon = "🟢" if mess.get('viber') == "Зарегистрирован" else "🔴"
        vk_icon = "🟢" if "Найден" in mess.get('vk', "") else "🟡"

        avito = await get_avito_link(p['e164'])
        youla = await get_youla_link(p['e164'])
        vk = await get_vk_search_link(p['e164'])
        yandex = await get_yandex_search_link(p['e164'])
        
        text = (
            f"📱 <b>АНАЛИЗ НОМЕРА</b>\n"
            f"{LINE}\n"
            f"📞 <b>Номер:</b> <code>{p['e164']}</code>\n"
            f"🌍 <b>Регион:</b> {p['region']}\n"
            f"📡 <b>Оператор:</b> {p['carrier']}\n"
            f"{LINE}\n"
            f"💬 <b>Мессенджеры:</b>\n"
            f"{tg_icon} Telegram: {mess.get('telegram')}\n"
            f"{wa_icon} WhatsApp: {mess.get('whatsapp')}\n"
            f"{vb_icon} Viber: {mess.get('viber')}\n"
            f"{vk_icon} VK: {mess.get('vk')}\n"
            f"{LINE}\n"
            f"🔗 <b>Поиск:</b>\n"
            f"├ <a href='{avito}'>Avito</a>\n"
            f"├ <a href='{youla}'>Youla</a>\n"
            f"├ <a href='{vk}'>ВКонтакте</a>\n"
            f"└ <a href='{yandex}'>Яндекс</a>"
        )
        await msg.edit_text(text)
        return

    if t == "ip":
        msg = await m.answer("⏳ <i>Ищу данные по IP...</i>")
        res = await check_ip(q)
        if "error" in res: 
            await msg.edit_text(f"❌ {res['error']}")
        else:
            text = (
                f"🌐 <b>IP-ИНФОРМАЦИЯ</b>\n"
                f"{LINE}\n"
                f"├ <b>IP:</b> <code>{res['IP']}</code>\n"
                f"├ <b>Страна:</b> {res['Страна']}\n"
                f"├ <b>Город:</b> {res['Город']}\n"
                f"└ <b>Провайдер:</b> {res['Провайдер']}"
            )
            await msg.edit_text(text)
        return

    if t == "email":
        msg = await m.answer("⏳ <i>Проверяю email...</i>")
        res = await check_email(q)
        if "error" in res: 
            await msg.edit_text(f"❌ {res['error']}")
        elif "info" in res: 
            await msg.edit_text(f"ℹ️ {res['info']}")
        else:
            text = (
                f"📧 <b>EMAIL-ИНФОРМАЦИЯ</b>\n"
                f"{LINE}\n"
                f"├ <b>Email:</b> <code>{res.get('Email')}</code>\n"
                f"├ <b>Репутация:</b> {res.get('Репутация')}\n"
                f"└ <b>Утечки:</b> {res.get('Утечки')}"
            )
            await msg.edit_text(text)
        return

    if t == "tg_username":
        clean_user = q.lstrip("@")
        msg = await m.answer(f"🕵️ <i>Собираю досье на @{clean_user}...</i>")
        
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

        await msg.edit_text(f"🕵️ <i>Проверяю Sherlock...</i>")
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
        caption = (
            f"📄 <b>ДОСЬЕ НА @{clean_user}</b>\n"
            f"{LINE}\n"
            f"Файл готов! Для жалобы перейди: https://telegram.org/support"
        )
        await m.answer_document(FSInputFile(filepath), caption=caption)
        await msg.delete()
        
        if os.path.exists(filepath):
            os.remove(filepath)
        return

    if t == "fssp":
        parts = q.split()
        msg = await m.answer(f"⚖️ <i>Ищу долги...</i>")
        res = check_fssp(" ".join(parts[:-1]), parts[-1])
        await msg.edit_text(f"⚖️ <b>ФССП:</b> {res.get('error') or res.get('info') or 'Данные найдены.'}")
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

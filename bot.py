import asyncio
import sqlite3
import os
import re
import uuid

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

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("""CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, query TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.commit()

ALLOWED_IDS = [6847416129]

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_IDS

def detect_type(q: str) -> str:
    q = q.strip()
    if q.startswith("@"): return "tg_username"
    if re.match(r"^\+?[\d\s\-()]{7,20}$", q): return "phone"
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", q): return "ip"
    if "@" in q and "." in q: return "email"
    if re.match(r"^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$", q, re.IGNORECASE): return "auto"
    if len(q) == 17 and q.isalnum(): return "vin"
    return "text"

@dp.message(Command("start"))
async def start(m: Message):
    if not is_allowed(m.from_user.id):
        await m.answer("⛔ <b>Доступ запрещен.</b>")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    await m.answer("🛡 <b>SWILL OSINT BOT</b>\n\nВыберите категорию:", reply_markup=kb)

@dp.callback_query(F.data == "menu_tools")
async def menu_tools(cb: CallbackQuery):
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Номер", callback_data="menu_phone"), InlineKeyboardButton(text="🌐 IP", callback_data="menu_ip")],
        [InlineKeyboardButton(text="📧 Email", callback_data="menu_email"), InlineKeyboardButton(text="⚖️ ФССП", callback_data="menu_fssp")],
        [InlineKeyboardButton(text="🕵️ Поиск по юзернейму", callback_data="menu_tg")],
        [InlineKeyboardButton(text="🚗 Госномер / VIN", callback_data="menu_auto")],
        [InlineKeyboardButton(text="🔑 Генератор UUID", callback_data="menu_uuid")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]
    ])
    await cb.message.edit_text("🔍 <b>Инструменты поиска</b>:", reply_markup=kb)

@dp.callback_query(F.data == "menu_devs")
async def menu_devs(cb: CallbackQuery):
    await cb.answer()
    text = (
        "👨‍💻 <b>Разработчики</b>\n\n"
        "Бот создан командой <b>Swill Way</b>.\n"
        "📂 <b>GitHub:</b> <a href='https://github.com/killroite/Lanaev-Search'>Lanaev-Search</a>\n"
        "🔗 <b>Связь:</b> @ceokvist\n\n"
        "Нажмите кнопку ниже, чтобы узнать о последних обновлениях."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Журнал обновлений", callback_data="menu_changelog")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")]
    ])
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_changelog")
async def menu_changelog(cb: CallbackQuery):
    await cb.answer()
    text = (
        "📜 <b>Последние обновления (v5.0)</b>\n\n"
        "✅ <b>Добавлено:</b>\n"
        "├ 📄 Генерация PDF-отчета по номеру\n"
        "├ 🕵️ Интеграция Sherlock\n"
        "├ 🚗 Заготовка поиска по Госномеру/VIN\n"
        "└ 🔒 Белый список\n\n"
        "<i>В планах: база утечек.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_devs")]])
    await cb.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_back")
async def menu_back(cb: CallbackQuery):
    await cb.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Инструменты", callback_data="menu_tools")],
        [InlineKeyboardButton(text="👨‍💻 Разработчики", callback_data="menu_devs")]
    ])
    await cb.message.edit_text("🛡 <b>SWILL OSINT BOT</b>\n\nВыберите категорию:", reply_markup=kb)

@dp.callback_query(F.data == "menu_uuid")
async def menu_uuid(cb: CallbackQuery):
    await cb.answer()
    new_uuid = str(uuid.uuid4())
    await cb.message.answer(f"🔑 <b>Ваш UUID:</b>\n<code>{new_uuid}</code>")

@dp.callback_query()
async def cb_handler(cb: CallbackQuery):
    await cb.answer()
    texts = {
        "menu_phone": "Введи номер (+7...)",
        "menu_ip": "Введи IP-адрес",
        "menu_email": "Введи email",
        "menu_fssp": "Введи ФИО и дату (Иванов Иван 01.01.1990)",
        "menu_auto": "Введи госномер (А123ВС77) или VIN (17 символов)",
        "menu_tg": "Введи @username или ник (например, ceokvist)"
    }
    await cb.message.answer(texts.get(cb.data, "Неизвестная команда"))

@dp.message(F.text)
async def handle(m: Message):
    if not is_allowed(m.from_user.id):
        return
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
        
        # --- ГЕНЕРАЦИЯ PDF ---
        report_data = {
            "Номер": p['e164'],
            "Регион": p['region'],
            "Оператор": p['carrier'],
            "Telegram": mess.get('telegram'),
            "WhatsApp": mess.get('whatsapp'),
            "Viber": mess.get('viber'),
            "VK": mess.get('vk')
        }
        
        filepath = generate_pdf_report(p['e164'], report_data)
        await m.answer_document(FSInputFile(filepath), caption="📄 <b>PDF-отчет готов!</b>")
        
        if os.path.exists(filepath):
            os.remove(filepath)
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
        try:
            chat = await bot.get_chat(f"@{clean_user}")
            chat_type = "Канал" if chat.type == "channel" else "Группа" if chat.type == "supergroup" else "Пользователь"
            text = f"🕵️ <b>Профиль Telegram ({chat_type})</b>\n├ 🆔 ID: <code>{chat.id}</code>\n"
            if chat.title: text += f"├ 📛 Название: <b>{chat.title}</b>\n"
            if chat.username: text += f"├ 🔗 Ссылка: <a href='https://t.me/{chat.username}'>@{chat.username}</a>\n"
            if chat.description: text += f"└ 📝 Описание: {chat.description[:100]}...\n"
            await m.answer(text)
        except Exception:
            await m.answer("❌ Профиль Telegram не найден (или скрыт).")

        await m.answer("🔎 <i>Ищу аккаунты с этим ником на других сайтах (Sherlock)... Это займет 15-30 секунд.</i>")
        sherlock_res = await run_sherlock(clean_user)
        
        if "error" in sherlock_res:
            await m.answer(f"⚠️ Sherlock: {sherlock_res['error']}")
        elif "info" in sherlock_res:
            await m.answer(f"🔍 Sherlock: {sherlock_res['info']}")
        else:
            text = f"🌐 <b>Найдено на {sherlock_res['total']} сайтах:</b>\n\n"
            for item in sherlock_res["results"][:10]:
                text += f"├ <a href='{item['url']}'>{item['site']}</a>\n"
            if len(sherlock_res["results"]) > 10:
                text += f"└ <i>...и еще {len(sherlock_res['results']) - 10} сайтов</i>"
            await m.answer(text)
        return

    if t == "fssp":
        parts = q.split()
        await m.answer(f"⏳ <i>Ищу долги для <b>{' '.join(parts[:-1])}</b>...</i>")
        res = check_fssp(" ".join(parts[:-1]), parts[-1])
        await m.answer(f"⚖️ <b>ФССП:</b> {res.get('error') or res.get('info') or 'Данные найдены.'}")
        return

    if t == "auto" or t == "vin":
        await m.answer("🚗 <i>В разработке. Требуется платный API.</i>")
        return

    await m.answer("🤷‍♂️ Неизвестный запрос.")

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

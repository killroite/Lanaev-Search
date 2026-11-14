import asyncio, sqlite3, os, re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiohttp import web
from aiogram.enums import ParseMode

from config import BOT_TOKEN, DB_PATH
from modules.phone import analyze_phone
from modules.fssp import check_fssp

bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)

conn.execute("""CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, query TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")

conn.execute("""CREATE TABLE IF NOT EXISTS tg_history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    username TEXT,
    old_name TEXT,
    new_name TEXT,
    old_username TEXT,
    new_username TEXT,
    changed_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
conn.commit()

def detect_type(q: str) -> str:
    q = q.strip()
    if q.startswith("@"): return "tg_username"
    if "vk.com/" in q: return "vk_link"
    if "ok.ru/" in q: return "ok_link"
    if re.match(r"^\+?[\d\s\-()]{7,20}$", q): return "phone"
    parts = q.split()
    if len(parts) >= 3 and any(char.isdigit() for char in parts[-1]):
        return "fssp"
    return "text"

@dp.message(Command("start"))
async def start(m: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Проверить номер", callback_data="menu_phone")],
        [InlineKeyboardButton(text="🕵️ Пробив @username", callback_data="menu_tg")],
        [InlineKeyboardButton(text="⚖️ Долги ФССП", callback_data="menu_fssp")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu_help")]
    ])

    text = (
        "🛡 <b>SWILL OSINT BOT</b>\n\n"
        "Привет! Я помогу найти открытую информацию.\n\n"
        "Выбери действие на кнопках ниже или просто отправь мне запрос:\n"
        "• <code>+7 900 000 00 00</code>\n"
        "• <code>@username</code>\n"
        "• <code>Иванов Иван 01.01.1990</code>"
    )
    
    await m.answer(text, reply_markup=keyboard)

@dp.callback_query()
async def handle_buttons(callback: CallbackQuery):
    await callback.answer()
    
    if callback.data == "menu_help":
        await callback.message.answer(
            "📖 <b>Как пользоваться:</b>\n\n"
            "1. Отправь номер (например, <code>+79000000000</code>) — узнаешь оператора и регион.\n"
            "2. Отправь <code>@username</code> — узнаешь ID и историю имен.\n"
            "3. Отправь ФИО и дату — проверишь долги ФССП.\n\n"
            "База данных бота обновляется автоматически."
        )
    elif callback.data == "menu_phone":
        await callback.message.answer("Введи номер телефона в формате <code>+7...</code>")
    elif callback.data == "menu_tg":
        await callback.message.answer("Введи юзернейм в формате <code>@username</code>")
    elif callback.data == "menu_fssp":
        await callback.message.answer("Введи ФИО и дату рождения (например, <code>Иванов Иван Иванович 01.01.1990</code>)")

@dp.message(F.text)
async def handle(m: Message):
    q = m.text.strip()
    conn.execute("INSERT INTO logs(user_id, query) VALUES(?,?)", (m.from_user.id, q))
    conn.commit()

    t = detect_type(q)
    
    # Для ФССП и Телеграма делаем отдельные карточки, для остального — общий отчет
    if t == "tg_username":
        clean_user = q.lstrip("@")
        try:
            chat = await bot.get_chat(f"@{clean_user}")
            current_name = chat.title or chat.full_name or "Без имени"
            current_username = chat.username or "Без юзернейма"
            tg_id = chat.id

            cursor = conn.cursor()
            cursor.execute("SELECT old_name, new_name, old_username, new_username, changed_at FROM tg_history WHERE tg_id = ? ORDER BY changed_at DESC", (tg_id,))
            history = cursor.fetchall()

            text = (
                f"🕵️ <b>Профиль Telegram</b>\n"
                f"├ 🆔 ID: <code>{tg_id}</code>\n"
                f"├ 👤 Имя: <b>{current_name}</b>\n"
                f"├ 🔗 Ссылка: <a href='https://t.me/{current_username}'>@{current_username}</a>\n"
            )
            
            if history:
                text += f"\n📜 <b>История изменений:</b>\n"
                for old_n, new_n, old_u, new_u, changed_at in history:
                    if old_n != new_n:
                        text += f"• Имя: {old_n} ➡️ <b>{new_n}</b>\n"
                    if old_u != new_u:
                        text += f"• Юзер: @{old_u} ➡️ <b>@{new_u}</b>\n"
            else:
                text += "\n📜 <i>История пуста. Я вижу его впервые.</i>"

            if history:
                last_old_n, last_new_n, last_old_u, last_new_u, _ = history[0]
                if last_new_n != current_name or last_new_u != current_username:
                    conn.execute("""INSERT INTO tg_history
                        (tg_id, username, old_name, new_name, old_username, new_username)
                        VALUES (?,?,?,?,?,?)""",
                        (tg_id, clean_user, last_new_n, current_name, last_new_u, current_username))
                    conn.commit()
            else:
                conn.execute("""INSERT INTO tg_history
                    (tg_id, username, old_name, new_name, old_username, new_username)
                    VALUES (?,?,?,?,?,?)""",
                    (tg_id, clean_user, current_name, current_name, current_username, current_username))
                conn.commit()

            await m.answer(text)

        except Exception as e:
            err_text = str(e)
            if "chat not found" in err_text:
                await m.answer("❌ <b>Ошибка:</b> Пользователь с таким юзернеймом не найден.")
            else:
                await m.answer(f"❌ <b>Ошибка Telegram:</b> {err_text}")
        return

    if t == "fssp":
        parts = q.split()
        bdate = parts[-1]
        fio = " ".join(parts[:-1])
        
        await m.answer(f"⏳ Проверяю базу ФССП для <b>{fio}</b> ({bdate})...")
        fssp_res = check_fssp(fio, bdate)
        
        if "error" in fssp_res:
            await m.answer(f"❌ <b>Ошибка:</b> {fssp_res['error']}")
        elif "results" in fssp_res:
            text = f"⚖️ <b>Найдено записей: {fssp_res['total']}</b>\n\n"
            for item in fssp_res["results"][:3]:
                text += f"• 💰 Сумма: <b>{item.get('Сумма')} руб.</b>\n  📄 ИП: {item.get('Номер ИП')}\n\n"
            await m.answer(text)
        else:
            await m.answer(f"✅ <b>ФССП:</b> {fssp_res.get('info', 'Долгов не найдено.')}")
        return

    # Остальные типы (номер, текст)
    report = [f"🔍 <b>Запрос:</b> {q}\n"]

    if t == "phone":
        p = analyze_phone(q)
        if p.get("valid"):
            report += [
                f"📱 <b>Анализ номера</b>",
                f"├ 📞 Формат: <code>{p['e164']}</code>",
                f"├ 🇷🇺 Регион: <b>{p['region']}</b>",
                f"└ 📶 Оператор: <b>{p['carrier']}</b>",
            ]
        else:
            report.append("❌ Номер невалиден для РФ/BY/UA.")

    else:
        report.append("🤷‍♂️ Неизвестный тип запроса. Используй кнопки меню.")

    report.append("\n<i>Лимит открытых данных. Для расширения — подключай API.</i>")
    await m.answer("\n".join(report))

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


import asyncio, sqlite3, osimport asyncio, sqlite3, os, re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiohttp import web

from config import BOT_TOKEN, DB_PATH
from modules.phone import analyze_phone
from modules.fssp import check_fssp

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect(DB_PATH)

# Таблица логов запросов
conn.execute("""CREATE TABLE IF NOT EXISTS logs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, query TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)""")

# Таблица истории Telegram
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
    await m.answer(
        "SWILL OSINT BOT\n\n"
        "Отправь:\n"
        "• номер (+7..., +375..., +380...)\n"
        "• @username (Telegram)\n"
        "• ФИО и дату рождения\n"
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
        clean_user = q.lstrip("@")
        try:
            chat = await bot.get_chat(f"@{clean_user}")
            current_name = chat.title or chat.full_name or "Без имени"
            current_username = chat.username or "Без юзернейма"
            tg_id = chat.id

            # Ищем последнюю запись по ID
            cursor = conn.cursor()
            cursor.execute("SELECT old_name, new_name, old_username, new_username, changed_at FROM tg_history WHERE tg_id = ? ORDER BY changed_at DESC", (tg_id,))
            history = cursor.fetchall()

            report.append(f"Telegram ID: {tg_id}")
            report.append(f"Текущее имя: {current_name}")
            report.append(f"Текущий юзернейм: @{current_username}")

            if history:
                report.append("\n[История изменений]:")
                for old_n, new_n, old_u, new_u, changed_at in history:
                    if old_n != new_n:
                        report.append(f"• Имя: '{old_n}' -> '{new_n}' ({changed_at})")
                    if old_u != new_u:
                        report.append(f"• Юзернейм: '@{old_u}' -> '@{new_u}' ({changed_at})")
            else:
                report.append("\n[История пуста. Бот видит этого пользователя впервые.]")

            # Записываем изменения (если имя или юзернейм изменились)
            if history:
                last_old_n, last_new_n, last_old_u, last_new_u, _ = history[0]
                if last_new_n != current_name or last_new_u != current_username:
                    conn.execute("""INSERT INTO tg_history
                        (tg_id, username, old_name, new_name, old_username, new_username)
                        VALUES (?,?,?,?,?,?)""",
                        (tg_id, clean_user, last_new_n, current_name, last_new_u, current_username))
                    conn.commit()
            else:
                # Первая запись
                conn.execute("""INSERT INTO tg_history
                    (tg_id, username, old_name, new_name, old_username, new_username)
                    VALUES (?,?,?,?,?,?)""",
                    (tg_id, clean_user, current_name, current_name, current_username, current_username))
                conn.commit()

        except Exception as e:
            err_text = str(e)
            if "chat not found" in err_text:
                report.append("Telegram: Пользователь не найден.")
            else:
                report.append(f"Telegram: ошибка {err_text}")

    if t == "fssp":
        parts = q.split()
        bdate = parts[-1]
        fio = " ".join(parts[:-1])
        
        report.append(f"[Проверка ФССП для: {fio}, {bdate}]")
        fssp_res = check_fssp(fio, bdate)
        
        if "error" in fssp_res:
            report.append(f"Ошибка: {fssp_res['error']}")
        elif "results" in fssp_res:
            report.append(f"Найдено записей: {fssp_res['total']}")
            for item in fssp_res["results"][:3]:
                report.append(f"• {item.get('Сумма')} руб. (ИП: {item.get('Номер ИП')})")
        else:
            report.append(f"{fssp_res.get('info', 'Нет данных')}")

    report.append("\nЛимит открытых данных.")
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
    asyncio.create_task(start_web())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

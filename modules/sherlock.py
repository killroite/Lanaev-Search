import asyncio
import re

async def run_sherlock(username: str) -> dict:
    clean_user = re.sub(r"[^a-zA-Z0-9_.-]", "", username)
    if not clean_user:
        return {"error": "Некорректный юзернейм."}

    process = await asyncio.create_subprocess_exec(
        "sherlock", clean_user,
        "--print-found",
        "--timeout", "10",
        "--no-color",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        return {"error": f"Sherlock завершился с ошибкой."}
    
    output = stdout.decode()
    found_links = []
    
    for line in output.split("\n"):
        if line.startswith("[+]"):
            parts = line.split(": ", 1)
            if len(parts) == 2:
                site = parts[0].replace("[+] ", "")
                url = parts[1].strip()
                found_links.append({"site": site, "url": url})
    
    if not found_links:
        return {"info": "Аккаунтов с таким ником не найдено."}
    
    return {"total": len(found_links), "results": found_links}

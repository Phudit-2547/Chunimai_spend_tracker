import asyncio
import json
import requests
import asyncpg  # PostgreSQL async library
from playwright.async_api import async_playwright
from datetime import datetime
import os

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# ✅ CONFIG: Enable or disable games
CONFIG = {"chunithm": True, "maimai": True}


async def connect_db():
    """Connects to the PostgreSQL database."""
    return await asyncpg.connect(DATABASE_URL)


async def insert_or_update_play_count(date, maimai_count, chunithm_count):
    """Inserts or updates play count for a given date."""
    conn = await connect_db()  # ✅ Await the coroutine to get the connection object
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    try:
        await conn.execute(
            """
            INSERT INTO public.play_data (play_date, maimai_play_count, chunithm_play_count)
            VALUES ($1, $2, $3)
            ON CONFLICT (play_date) DO UPDATE
            SET maimai_play_count = EXCLUDED.maimai_play_count,
                chunithm_play_count = EXCLUDED.chunithm_play_count;
        """,
            date_obj,
            maimai_count,
            chunithm_count,
        )

        print(
            f"✅ Data saved: {date} | Maimai: {maimai_count} | Chunithm: {chunithm_count}"
        )
    finally:
        await conn.close()  # ✅ Always close the connection


async def login_and_get_play_count(game):
    """Logs into the game website and counts today's plays."""
    LOGIN_URLS = {
        "chunithm": "https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=chuniex&redirect_url=https://chunithm-net-eng.com/mobile/&back_url=https://chunithm.sega.com/",
        "maimai": "https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=maimaidxex&redirect_url=https://maimaidx-eng.com/maimai-mobile/&back_url=https://maimai.sega.com/",
    }
    HOME_URLS = {
        "chunithm": "https://chunithm-net-eng.com/mobile/home/",
        "maimai": "https://maimaidx-eng.com/maimai-mobile/home/",
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"🔄 Logging into {game}...")
        await page.goto(LOGIN_URLS[game], wait_until="domcontentloaded")
        await page.locator("span.c-button--openid--segaId").click()
        await page.locator("#sid").fill(USERNAME)
        await page.locator("#password").fill(PASSWORD)
        await page.locator("input#btnSubmit.c-button--login").click()
        await page.wait_for_url(HOME_URLS[game])

        play_count = 0
        today_str = datetime.today().strftime("%Y/%m/%d")

        if game == "chunithm":
            await page.goto(
                "https://chunithm-net-eng.com/mobile/record/",
                wait_until="domcontentloaded",
            )
            await page.locator("li.submenu_play a").click()
            await page.wait_for_url(
                "https://chunithm-net-eng.com/mobile/record/playlog"
            )

            date_track_pairs = await page.locator("div.frame02.w400").evaluate_all(
                "elements => elements.map(e => [e.querySelector('.play_datalist_date')?.innerText.split(' ')[0], e.querySelector('.play_track_text')?.innerText.split(' ')[1]])"
            )

            checker = [track for date, track in date_track_pairs if date == today_str]

            if not checker:
                print("✅ No Chunithm plays found for today.")
                return 0

            for i in range(len(checker) - 1):
                if checker[i] < checker[i + 1]:
                    play_count += 1
            play_count += 1

        elif game == "maimai":
            await page.goto(
                "https://maimaidx-eng.com/maimai-mobile/record/",
                wait_until="domcontentloaded",
            )
            records = await page.locator(f"text={today_str}").all()

            if not records:
                print("✅ No Maimai plays found for today.")
                return 0

            track_elements = await page.locator(
                "div.sub_title.t_c.f_r.f_11"
            ).all_text_contents()
            checker = []

            for txt in track_elements:
                track = txt.split()[1]
                date = txt.split()[2]
                if date == today_str:
                    checker.append(track)

            for i in range(len(checker) - 1):
                if checker[i] < checker[i + 1]:
                    play_count += 1

            play_count += 1

        print(f"✅ {game.capitalize()} plays today: {play_count}")
        await browser.close()
        return play_count


def send_discord_notification(game, play_count):
    """Sends a message to Discord only if play_count > 0."""
    if play_count > 0:
        message = {
            "username": "Game Scraper Bot",
            "avatar_url": "https://storage.sekai.best/sekai-jp-assets/character/member/res005_no026_rip/card_normal.webp",
            "content": f"🎵 **{game.capitalize()}**: You have played **{play_count}** credits today!"
        }
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 204:
            print(f"✅ Sent Discord notification for {game}.")
        else:
            print(f"❌ Failed to send Discord message. Response: {response.text}")



async def main():
    today_str = datetime.today().strftime(
        "%Y-%m-%d"
    )  # Format for PostgreSQL DATE column

    chunithm_plays = (
        await login_and_get_play_count("chunithm") if CONFIG["chunithm"] else 0
    )
    maimai_plays = await login_and_get_play_count("maimai") if CONFIG["maimai"] else 0

    await insert_or_update_play_count(today_str, maimai_plays, chunithm_plays)

    # Uncomment to enable Discord notifications
    send_discord_notification("chunithm", chunithm_plays)
    send_discord_notification("maimai", maimai_plays)


if __name__ == "__main__":
    asyncio.run(main()) 

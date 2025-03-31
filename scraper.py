import asyncio
import json
import os
import re
import requests
import asyncpg  # PostgreSQL async library
from playwright.async_api import async_playwright
from datetime import datetime, timedelta

# Get configuration from environment variables
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

# ✅ CONFIG: Enable or disable games
CONFIG = {"chunithm": True, "maimai": True}


async def connect_db():
    """Connects to the PostgreSQL database."""
    return await asyncpg.connect(DATABASE_URL)


async def get_yesterday_cumulative(game, yesterday_date):
    """
    Retrieves yesterday's cumulative play count for a given game from the database.
    Returns 0 if no record exists.
    """
    conn = await connect_db()
    try:
        # Convert yesterday_date from string to a proper date object.
        yesterday_obj = datetime.strptime(yesterday_date, "%Y-%m-%d")

        if game == "maimai":
            query = """
                SELECT maimai_cumulative FROM public.play_data 
                WHERE play_date = $1
            """
        elif game == "chunithm":
            query = """
                SELECT chunithm_cumulative FROM public.play_data 
                WHERE play_date = $1
            """
        row = await conn.fetchrow(query, yesterday_obj)
        if row:
            return row["maimai_cumulative"] if game == "maimai" else row["chunithm_cumulative"] or 0
        return 0
    finally:
        await conn.close()


async def insert_or_update_play_data(date, maimai_new, chunithm_new, maimai_cumulative, chunithm_cumulative):
    """
    Inserts or updates play data for a given date.
    - maimai_play_count & chunithm_play_count: Daily new plays (cumulative difference)
    - maimai_cumulative & chunithm_cumulative: Cumulative total play counts
    """
    conn = await connect_db()
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    try:
        await conn.execute(
            """
            INSERT INTO public.play_data 
                (play_date, maimai_play_count, chunithm_play_count, maimai_cumulative, chunithm_cumulative)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (play_date) DO UPDATE
            SET 
                maimai_play_count = EXCLUDED.maimai_play_count,
                chunithm_play_count = EXCLUDED.chunithm_play_count,
                maimai_cumulative = EXCLUDED.maimai_cumulative,
                chunithm_cumulative = EXCLUDED.chunithm_cumulative;
            """,
            date_obj,
            maimai_new,
            chunithm_new,
            maimai_cumulative,
            chunithm_cumulative,
        )
        print(f"✅ Data saved: {date} | Maimai new: {maimai_new}, Chunithm new: {chunithm_new} | "
              f"Maimai cumulative: {maimai_cumulative}, Chunithm cumulative: {chunithm_cumulative}")
    finally:
        await conn.close()


async def login_and_get_play_count(game):
    """
    Logs into the game website and retrieves the cumulative play count from the Player Data page.
    
    For **chunithm**: Navigates to https://chunithm-net-eng.com/mobile/home/playerData
       and extracts the number from:
         <div class="user_data_play_count">
             <div class="user_data_text">72</div>
         </div>
    
    For **maimai**: Navigates to https://maimaidx-eng.com/maimai-mobile/playerData/ and uses regex
       to extract the cumulative count (e.g., "maimaiDX total play count：300").
    """
    LOGIN_URLS = {
        "chunithm": ("https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=chuniex"
                      "&redirect_url=https://chunithm-net-eng.com/mobile/&back_url=https://chunithm.sega.com/"),
        "maimai": ("https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=maimaidxex"
                   "&redirect_url=https://maimaidx-eng.com/maimai-mobile/&back_url=https://maimai.sega.com/"),
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

        if game == "chunithm":
            await page.goto("https://chunithm-net-eng.com/mobile/home/playerData", wait_until="domcontentloaded")
            play_count_text = await page.locator("div.user_data_play_count div.user_data_text").inner_text()
            cumulative = int(play_count_text) if play_count_text.isdigit() else 0

        elif game == "maimai":
            await page.goto("https://maimaidx-eng.com/maimai-mobile/playerData/", wait_until="domcontentloaded")
            play_count_text = await page.locator("div.m_5.m_b_5.t_r.f_12").inner_text()
            match = re.search(r"maimaiDX total play count：(\d+)", play_count_text)
            cumulative = int(match.group(1)) if match else 0

        await browser.close()
        return cumulative


def send_discord_notification(game, play_count):
    """Sends a Discord notification if play_count (daily new plays) > 0."""
    if play_count > 0:
        message = {
            "username": "Game Scraper Bot",
            "avatar_url": "https://storage.sekai.best/sekai-jp-assets/character/member/res005_no026_rip/card_normal.webp",
            "content": f"🎵 **{game.capitalize()}**: You played **{play_count}** new credits today!"
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

async def generate_spending_report():
    """Calculates and sends weekly & monthly spending report to Discord."""
    conn = await connect_db()
    try:
        today = datetime.today()

        # WEEKLY CALCULATION (Last Monday-Sunday)
        last_sunday = today - timedelta(days=today.weekday() + 1)  # Last Sunday
        last_monday = last_sunday - timedelta(days=6)  # Monday before that
        query_weekly = """
            SELECT SUM(maimai_play_count) AS maimai_total, SUM(chunithm_play_count) AS chunithm_total
            FROM public.play_data 
            WHERE play_date BETWEEN $1 AND $2;
        """
        weekly_row = await conn.fetchrow(query_weekly, last_monday, last_sunday)

        maimai_weekly = weekly_row["maimai_total"] or 0
        chunithm_weekly = weekly_row["chunithm_total"] or 0
        maimai_weekly_cost = maimai_weekly * 40
        chunithm_weekly_cost = chunithm_weekly * 40

        avg_maimai_weekly = maimai_weekly_cost / 7 if maimai_weekly > 0 else 0
        avg_chunithm_weekly = chunithm_weekly_cost / 7 if chunithm_weekly > 0 else 0

        # MONTHLY CALCULATION (Last Calendar Month)
        month_start = today.replace(day=1)  # First day of current month
        last_month_end = month_start - timedelta(days=1)  # Last day of previous month
        last_month_start = last_month_end.replace(day=1)  # First day of previous month
        query_monthly = """
            SELECT SUM(maimai_play_count) AS maimai_total, SUM(chunithm_play_count) AS chunithm_total
            FROM public.play_data 
            WHERE play_date BETWEEN $1 AND $2;
        """
        monthly_row = await conn.fetchrow(query_monthly, last_month_start, last_month_end)

        maimai_monthly = monthly_row["maimai_total"] or 0
        chunithm_monthly = monthly_row["chunithm_total"] or 0
        maimai_monthly_cost = maimai_monthly * 40
        chunithm_monthly_cost = chunithm_monthly * 40

        avg_maimai_monthly = maimai_monthly_cost / last_month_end.day if maimai_monthly > 0 else 0
        avg_chunithm_monthly = chunithm_monthly_cost / last_month_end.day if chunithm_monthly > 0 else 0

        # Generate report message
        report_content = (
            f"📊 **Spending Report**\n"
            f"📅 **Last Week (Mon-Sun):**\n"
            f"🎵 **Maimai**: {maimai_weekly} plays → 💰 {maimai_weekly_cost:,} THB (avg {avg_maimai_weekly:.2f} THB/day)\n"
            f"🎶 **Chunithm**: {chunithm_weekly} plays → 💰 {chunithm_weekly_cost:,} THB (avg {avg_chunithm_weekly:.2f} THB/day)\n\n"
            f"📆 **Last Month ({last_month_start.strftime('%B %Y')}):**\n"
            f"🎵 **Maimai**: {maimai_monthly} plays → 💰 {maimai_monthly_cost:,} THB (avg {avg_maimai_monthly:.2f} THB/day)\n"
            f"🎶 **Chunithm**: {chunithm_monthly} plays → 💰 {chunithm_monthly_cost:,} THB (avg {avg_chunithm_monthly:.2f} THB/day)"
        )

        # Send report to Discord
        message = {
            "username": "Game Stats Bot",
            "avatar_url": "https://static.wikitide.net/projectsekaiwiki/0/0f/Minori_V2.png",
            "content": report_content,
        }
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 204:
            print("✅ Spending report sent to Discord.")
        else:
            print(f"❌ Failed to send spending report. Response: {response.text}")
    finally:
        await conn.close()

async def main():
    today_str = datetime.today().strftime("%Y-%m-%d")
    yesterday_str = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Run weekly report every Monday
    if datetime.today().weekday() == 0:
        await generate_spending_report()

    # Run monthly report on the 1st of each month
    if datetime.today().day == 1:
        await generate_spending_report()

    # Get cumulative play counts from the websites.
    chunithm_cumulative = await login_and_get_play_count("chunithm") if CONFIG["chunithm"] else 0
    maimai_cumulative = await login_and_get_play_count("maimai") if CONFIG["maimai"] else 0

    # Retrieve yesterday's cumulative values from the database.
    yesterday_chunithm = await get_yesterday_cumulative("chunithm", yesterday_str)
    yesterday_maimai = await get_yesterday_cumulative("maimai", yesterday_str)

    # Calculate new plays (daily count) as the difference.
    chunithm_new = max(0, chunithm_cumulative - yesterday_chunithm)
    maimai_new = max(0, maimai_cumulative - yesterday_maimai)

    # Update the database with today's data.
    await insert_or_update_play_data(today_str, maimai_new, chunithm_new, maimai_cumulative, chunithm_cumulative)

    # Send Discord notifications for daily new plays.
    send_discord_notification("chunithm", chunithm_new)
    send_discord_notification("maimai", maimai_new)

if __name__ == "__main__":
    asyncio.run(main())

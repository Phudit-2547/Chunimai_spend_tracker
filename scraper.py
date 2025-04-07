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
            "username": "毎日みのり",
            "avatar_url": "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg&name=4096x4096",
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

async def generate_weekly_report():
    """Generates a report of weekly play averages and sends it to Discord."""
    conn = await connect_db()
    try:
        today = datetime.today()
        last_sunday = today - timedelta(days=today.weekday() + 1)  # Last Sunday
        last_monday = last_sunday - timedelta(days=6)  # Monday before last Sunday

        # Query for last week
        query = """
            SELECT SUM(maimai_play_count) AS maimai_total, SUM(chunithm_play_count) AS chunithm_total
            FROM public.play_data 
            WHERE play_date BETWEEN $1 AND $2;
        """
        row = await conn.fetchrow(query, last_monday, last_sunday)

        # Default to 0 if no data exists
        maimai_week = row["maimai_total"] or 0
        chunithm_week = row["chunithm_total"] or 0

        # Calculate weekly cost (1 play = 40 THB)
        cost_maimai_week = maimai_week * 40
        cost_chunithm_week = chunithm_week * 40
        total_cost_week = cost_maimai_week + cost_chunithm_week
        
        # Compute weekly averages
        avg_maimai_week = cost_maimai_week / 7 if maimai_week > 0 else 0
        avg_chunithm_week = cost_chunithm_week / 7 if chunithm_week > 0 else 0
        avg_total_week = total_cost_week / 7 if (maimai_week + chunithm_week) > 0 else 0
        
        # Generate the report message
        report_content = (
            f"📊 **Last Week Play Report**\n\n"
            f"🎵 **Maimai**: {maimai_week} plays → **{cost_maimai_week:,} THB** (avg {avg_maimai_week:.2f} THB/day)\n"
            f"🎶 **Chunithm**: {chunithm_week} plays → **{cost_chunithm_week:,} THB** (avg {avg_chunithm_week:.2f} THB/day)\n"
            f"**Total**: {maimai_week + chunithm_week} plays → **{total_cost_week:,} THB** (avg {avg_total_week:.2f} THB/day)"
        )

        # Send to Discord
        message = {
            "username": "毎週みのり",
            "avatar_url": "https://pbs.twimg.com/media/F2kuDs2bkAA9wVR?format=jpg&name=4096x4096",
            "content": report_content,
        }
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 204:
            print("✅ Weekly report sent to Discord.")
        else:
            print(f"❌ Failed to send weekly report. Response: {response.text}")
    finally:
        await conn.close()

async def generate_monthly_report():
    """Generates a report of monthly play averages and sends it to Discord."""
    conn = await connect_db()
    try:
        today = datetime.today()
        month_start = today.replace(day=1)  # First day of this month
        last_month_end = month_start - timedelta(days=1)  # Last day of the previous month
        last_month_start = last_month_end.replace(day=1)  # First day of the previous month

        # Query for last month
        query = """
            SELECT SUM(maimai_play_count) AS maimai_total, SUM(chunithm_play_count) AS chunithm_total
            FROM public.play_data 
            WHERE play_date BETWEEN $1 AND $2;
        """
        row = await conn.fetchrow(query, last_month_start, last_month_end)

        # Default to 0 if no data exists
        maimai_month = row["maimai_total"] or 0
        chunithm_month = row["chunithm_total"] or 0

        # Calculate monthly cost (1 play = 40 THB)
        cost_maimai_month = maimai_month * 40
        cost_chunithm_month = chunithm_month * 40
        total_cost_month = cost_maimai_month + cost_chunithm_month
        
        # Compute monthly averages
        avg_maimai_month = cost_maimai_month / last_month_end.day if maimai_month > 0 else 0
        avg_chunithm_month = cost_chunithm_month / last_month_end.day if chunithm_month > 0 else 0
        avg_total_month = total_cost_month / last_month_end.day if (maimai_month + chunithm_month) > 0 else 0
        
        # Generate the report message
        report_content = (
            f"📊 **Monthly Play Report ({last_month_start.strftime('%B %Y')})**\n\n"
            f"🎵 **Maimai**: {maimai_month} plays → **{cost_maimai_month:,} THB** (avg {avg_maimai_month:.2f} THB/day)\n"
            f"🎶 **Chunithm**: {chunithm_month} plays → **{cost_chunithm_month:,} THB** (avg {avg_chunithm_month:.2f} THB/day)\n"
            f"**Total**: {maimai_month + chunithm_month} plays → **{total_cost_month:,} THB** (avg {avg_total_month:.2f} THB/day)"
        )

        # Send to Discord
        message = {
            "username": "桃井 愛莉",
            "avatar_url": "https://pbs.twimg.com/media/F2kuFKjaYAEWnpO?format=jpg&name=4096x4096",
            "content": report_content,
        }
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 204:
            print("✅ Monthly report sent to Discord.")
        else:
            print(f"❌ Failed to send monthly report. Response: {response.text}")
    finally:
        await conn.close()

async def main():
    today_str = datetime.today().strftime("%Y-%m-%d")
    yesterday_str = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.today()
    
    # Send the monthly report on the 1st of each month
    if today.day == 1:
        await generate_monthly_report()
    
    # Send the weekly report every Monday
    if today.weekday() == 0:  # Monday (0 = Monday, 6 = Sunday)
        await generate_weekly_report()
        
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

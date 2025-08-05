import asyncio
import re

import requests
from playwright.async_api import async_playwright

from play_counter.config import PASSWORD, USERNAME
from play_counter.utils.constants import DISCORD_WEBHOOK_URL, HOME_URLS, LOGIN_URLS

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def send_discord_notification(game: str, error_message: str):
    """Send notification to Discord when scraping fails."""
    payload = {
        "content": f"🚨 **Scraping Failed** 🚨\n\n**Game:** {game}\n**Error:** {error_message}\n**All {MAX_RETRIES} retries exhausted.**"
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("✅ Discord notification sent successfully")
        else:
            print(f"⚠️ Failed to send Discord notification: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Error sending Discord notification: {e}")


async def fetch_cumulative(game: str) -> int:
    """
    Logs into the game website and retrieves the cumulative play count from the Player Data page.

    For chunithm: Navigates to https://chunithm-net-eng.com/mobile/home/playerData
       and extracts the number from:
         <div class="user_data_play_count">
             <div class="user_data_text">72</div>
         </div>

    For maimai: Navigates to https://maimaidx-eng.com/maimai-mobile/playerData/ and uses regex
       to extract the cumulative count (e.g., "maimaiDX total play count：300").
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with async_playwright() as p:
                browser = await p.firefox.launch(headless=True)
                context = await browser.new_context()

                # Start tracing
                await context.tracing.start(
                    screenshots=True, snapshots=True, sources=True
                )
                page = await context.new_page()

                print(f"🔄 Logging into {game}... (Attempt {attempt})")
                await page.goto(LOGIN_URLS[game], wait_until="domcontentloaded")
                await page.locator("span.c-button--openid--segaId").click()
                await page.locator("#sid").fill(USERNAME)
                await page.locator("#password").fill(PASSWORD)
                # Check the agreement checkbox right before login
                await page.locator("label.c-form__label--bg").click()
                await page.wait_for_timeout(1000)

                # Ensure checkbox is checked (retry if needed)
                for i in range(3):  # Try up to 3 times
                    is_checked = await page.locator("#agree").is_checked()
                    if is_checked:
                        break
                    print(f"🔄 Checkbox unchecked, clicking again... (attempt {i+1})")
                    await page.locator("label.c-form__label--bg").click()
                    await page.wait_for_timeout(500)

                # Wait for login button to be enabled and click
                print("🔄 Waiting for login button to be enabled...")
                await page.wait_for_selector("button#btnSubmit:not([disabled])", timeout=10000)
                await page.locator("button#btnSubmit").click()
                print("✅ Login button clicked successfully")

                print(f"🔄 Waiting for {game} home page...")
                try:
                    await page.wait_for_url(HOME_URLS[game])
                except Exception as e:
                    print(page.url)
                    print(f"❌ Failed to load {game} home page: {e}")
                    await context.tracing.stop(path="trace.zip")
                    await browser.close()
                    raise

                if game == "chunithm":
                    await page.goto(
                        f"{HOME_URLS[game]}playerData", wait_until="domcontentloaded"
                    )
                    play_count_text = await page.locator(
                        "div.user_data_play_count div.user_data_text"
                    ).inner_text()
                    cumulative = (
                        int(play_count_text) if play_count_text.isdigit() else 0
                    )

                elif game == "maimai":
                    await page.goto(
                        "https://maimaidx-eng.com/maimai-mobile/playerData/",
                        wait_until="domcontentloaded",
                    )
                    play_count_text = await page.locator(
                        "div.m_5.m_b_5.t_r.f_12"
                    ).inner_text()
                    match = re.search(
                        r"maimaiDX total play count：(\d+)", play_count_text
                    )
                    cumulative = int(match.group(1)) if match else 0

                await context.tracing.stop(path="trace.zip")
                await browser.close()
                print(f"✅ Fetched cumulative {game} play count: {cumulative}")
                return cumulative
        except Exception as e:
            last_error = str(e)
            print(f"⚠️ Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"⏳ Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print("❌ All retries failed.")
                send_discord_notification(game, last_error)
                return 0

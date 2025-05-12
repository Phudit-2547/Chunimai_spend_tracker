import re
from playwright.async_api import async_playwright
from play_counter.config import USERNAME, PASSWORD
from play_counter.utils.constants import LOGIN_URLS, HOME_URLS


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
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()

        # Start tracing
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = await context.new_page()

        print(f"🔄 Logging into {game}...")
        await page.goto(LOGIN_URLS[game], wait_until="domcontentloaded")
        await page.locator("span.c-button--openid--segaId").click()
        await page.locator("#sid").fill(USERNAME)
        await page.locator("#password").fill(PASSWORD)
        await page.locator("input#btnSubmit.c-button--login").click()

        print(f"🔄 Waiting for {game} home page...")
        try:
            await page.wait_for_url(HOME_URLS[game])
        except Exception as e:
            print(page.url)
            print(f"❌ Failed to load {game} home page: {e}")
            await context.tracing.stop(path="trace.zip")
            await browser.close()
            return 0

        if game == "chunithm":
            await page.goto(f"{HOME_URLS[game]}playerData", wait_until="domcontentloaded")
            play_count_text = await page.locator("div.user_data_play_count div.user_data_text").inner_text()
            cumulative = int(play_count_text) if play_count_text.isdigit() else 0

        elif game == "maimai":
            await page.goto("https://maimaidx-eng.com/maimai-mobile/playerData/",wait_until="domcontentloaded")
            play_count_text = await page.locator("div.m_5.m_b_5.t_r.f_12").inner_text()
            match = re.search(r"maimaiDX total play count：(\d+)", play_count_text)
            cumulative = int(match.group(1)) if match else 0

        await context.tracing.stop(path="trace.zip")
        await browser.close()
        print(f"✅ Fetched cumulative {game} play count: {cumulative}")
        return cumulative

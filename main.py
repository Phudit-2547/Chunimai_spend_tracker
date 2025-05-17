import asyncio
from datetime import datetime, timedelta

from play_counter.config import CONFIG
from play_counter.scraper import fetch_cumulative
from play_counter.db import get_cumulative, upsert_play_data
from play_counter.daily_play_notifier import send_notification
from play_counter.reports.weekly import generate_weekly_report
from play_counter.reports.monthly import generate_monthly_report  

async def main():
    today = datetime.today()
    today_str = today.strftime("%Y-%m-%d")
    yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    if today.day == 1:
        await generate_monthly_report()  
    if today.weekday() == 0:
        await generate_weekly_report()

    tasks = {game: fetch_cumulative(game) for game, enable in CONFIG.items() if enable}
    cumulative_values = await asyncio.gather(*tasks.values())
    cumulative = dict(zip(tasks.keys(), cumulative_values))

    prev = {game: await get_cumulative(game, yesterday_str) for game in cumulative}
    new = {game: max(0, cumulative[game] - prev[game]) for game in cumulative}

    await upsert_play_data(
        today_str,
        new.get("maimai", 0),
        new.get("chunithm", 0),
        cumulative.get("maimai", 0),
        cumulative.get("chunithm", 0)
    )

    send_notification("chunithm", new.get("chunithm", 0))
    send_notification("maimai", new.get("maimai", 0))

if __name__ == "__main__":
    asyncio.run(main())

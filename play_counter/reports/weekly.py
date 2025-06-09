import json

import requests

from play_counter.config import NOTIFICATION_CONFIG
from play_counter.config import WEEKREPORT_WEBHOOK as DISCORD_WEBHOOK_URL
from play_counter.db import connect_db
from play_counter.utils.date_helpers import last_week_range


async def generate_weekly_report():
    """Generates a report of weekly play averages and sends it to Discord."""
    conn = await connect_db()
    try:
        # Get last week's date range
        last_monday, last_sunday = last_week_range()

        # Get weekly report specific configuration
        config = NOTIFICATION_CONFIG.get("weekly", NOTIFICATION_CONFIG["default"])

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

        # Generate the report message using config template if available
        maimai_config = NOTIFICATION_CONFIG.get("maimai", {})
        chunithm_config = NOTIFICATION_CONFIG.get("chunithm", {})

        maimai_emoji = maimai_config.get("emoji", "🎵")
        chunithm_emoji = chunithm_config.get("emoji", "🎶")

        report_content = (
            f"📊 **Last Week Play Report**\n\n"
            f"{maimai_emoji} **Maimai**: {maimai_week} plays → **{cost_maimai_week:,} THB** (avg {avg_maimai_week:.2f} THB/day)\n"
            f"{chunithm_emoji} **CHUNITHM**: {chunithm_week} plays → **{cost_chunithm_week:,} THB** (avg {avg_chunithm_week:.2f} THB/day)\n"
            f"**Total**: {maimai_week + chunithm_week} plays → **{total_cost_week:,} THB** (avg {avg_total_week:.2f} THB/day)"
        )

        message = {
            "username": config.get("username", "毎週みのり"),
            "avatar_url": config.get(
                "avatar_url", "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg"
            ),
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

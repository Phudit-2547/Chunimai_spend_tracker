import requests
import json
from play_counter.db import connect_db
from play_counter.utils.constants import DISCORD_WEBHOOK_URL
from play_counter.utils.date_helpers import last_week_range


async def generate_weekly_report():
    """Generates a report of weekly play averages and sends it to Discord."""
    conn = await connect_db()
    try:
        # Get last week's date range
        last_monday, last_sunday = last_week_range()

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

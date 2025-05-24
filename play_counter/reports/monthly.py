import requests
import json

from play_counter.db import connect_db
from play_counter.utils.constants import COST_PER_PLAY, MONTHREPORT_WEBHOOK
from play_counter.utils.date_helpers import last_month_range


async def generate_monthly_report():
    """Generates a report of monthly play averages and sends it to Discord."""
    # Get the date range for the last month
    start, end = last_month_range()
    conn = await connect_db()
    try:
        # Query for last month's data
        query = """
            SELECT SUM(maimai_play_count) AS maimai_total,
                   SUM(chunithm_play_count) AS chunithm_total
            FROM public.play_data 
            WHERE play_date BETWEEN $1 AND $2;
        """
        row = await conn.fetchrow(query, start, end)

        # Default to 0 if no data exists
        maimai_total = row["maimai_total"] or 0
        chunithm_total = row["chunithm_total"] or 0

        # Calculate costs
        cost_maimai = maimai_total * COST_PER_PLAY
        cost_chunithm = chunithm_total * COST_PER_PLAY
        total_cost = cost_maimai + cost_chunithm

        # Calculate averages
        days = (end - start).days + 1
        avg_maimai = cost_maimai / days if maimai_total > 0 else 0
        avg_chunithm = cost_chunithm / days if chunithm_total > 0 else 0
        avg_total = total_cost / days if (maimai_total + chunithm_total) > 0 else 0

        # Generate the report message
        report_content = (
            f"📊 **Monthly Play Report ({start:%B %Y})**\n\n"
            f"🎵 **maimai**: {maimai_total} plays → **{cost_maimai:,} THB** (avg {avg_maimai:.2f} THB/day)\n"
            f"🎶 **CHUNITHM**: {chunithm_total} plays → **{cost_chunithm:,} THB** (avg {avg_chunithm:.2f} THB/day)\n"
            f"**Total**: {maimai_total + chunithm_total} plays → **{total_cost:,} THB** (avg {avg_total:.2f} THB/day)"
        )

        # Send to Discord
        message = {
            "username": "桃井 愛莉",
            "avatar_url": "https://pbs.twimg.com/media/F2kuFKjaYAEWnpO?format=jpg&name=4096x4096",
            "content": report_content,
        }
        response = requests.post(
            MONTHREPORT_WEBHOOK,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 204:
            print("✅ Monthly report sent to Discord.")
        else:
            print(f"❌ Failed to send monthly report. Response: {response.text}")
    finally:
        await conn.close()

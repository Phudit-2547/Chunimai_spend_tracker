import requests

from play_counter.config import DISCORD_WEBHOOK_URL


def send_notification(game: str, new_plays: int):
    if new_plays <= 0:
        return
    payload = {
        "username": "毎日みのり",
        "avatar_url": "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg",
        "content": f"**{game.capitalize()}**: You played **{new_plays}** new credits today!",
    }
    res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if res.status_code != 204:
        print("❌ Discord error:", res.text)

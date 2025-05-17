from envparse import env

env.read_envfile()

DISCORD_WEBHOOK_URL = env("DISCORD_WEBHOOK_URL")
DATABASE_URL = env("DATABASE_URL")
USERNAME = env("USERNAME")
PASSWORD = env("PASSWORD")
CONFIG = {"chunithm": True, "maimai": True}

NOTIFICATION_CONFIG = {
    "default": {
        "username": "毎日みのり",
        "avatar_url": "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg",
    },
    "maimai": {
        "username": "毎日みのり",
        "avatar_url": "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg",
        "message_template": "**{game.capitalize()}**: You played **{new_plays}** credits today!",
        "emoji": "🎵",
    },
    "chunithm": {
        "username": "毎日みのり",
        "avatar_url": "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg",
        "message_template": "**{game.capitalize()}**: You played **{new_plays}** credits today!",
        "emoji": "🎶",
    },
}
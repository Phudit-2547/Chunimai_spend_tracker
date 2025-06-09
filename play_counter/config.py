from envparse import env

env.read_envfile()

DISCORD_WEBHOOK_URL = env("DISCORD_WEBHOOK_URL")
WEEKREPORT_WEBHOOK = env.str("WEEKREPORT_WEBHOOK", default=DISCORD_WEBHOOK_URL)
DATABASE_URL = env("DATABASE_URL")
USERNAME = env("USERNAME")
PASSWORD = env("PASSWORD")
CONFIG = {"chunithm": True, "maimai": True}

NOTIFICATION_CONFIG = {
    "default": {
        "username": "毎日みのり",
        "avatar_url": "https://pbs.twimg.com/media/GjfKtY6acAIo5Ga?format=jpg",
    },
    "weekly": {
        "username": "毎週みのり",
        "avatar_url": "https://cdn.discordapp.com/attachments/917303163470635018/1381649633981239407/GCaygD2XUAAFTrl.png?ex=684848fe&is=6846f77e&hm=5e7af379f28414de436e5ebf133581eb3a5b94a78b010f3b79d9b86278148007&",
    },
    "maimai": {
        "username": "毎日みのり",
        "avatar_url": "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg",
        "message_template": "**{game}**: You played **{new_plays}** credit(s) today!",
        "emoji": "🎵",
    },
    "chunithm": {
        "username": "毎日みのり",
        "avatar_url": "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg",
        "message_template": "**{game}**: You played **{new_plays}** credit(s) today!",
        "emoji": "🎶",
    },
}

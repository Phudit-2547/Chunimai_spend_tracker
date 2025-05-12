from envparse import env

env.read_envfile()

DISCORD_WEBHOOK_URL = env("DISCORD_WEBHOOK_URL")
DATABASE_URL = env("DATABASE_URL")
USERNAME = env("USERNAME")
PASSWORD = env("PASSWORD")
CONFIG = {"chunithm": True, "maimai": True}

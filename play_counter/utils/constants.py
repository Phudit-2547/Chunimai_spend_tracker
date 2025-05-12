from play_counter.config import DISCORD_WEBHOOK_URL

COST_PER_PLAY      = 40
LOGIN_URLS = {
    "chunithm": (
        "https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=chuniex"
        "&redirect_url=https://chunithm-net-eng.com/mobile/&back_url=https://chunithm.sega.com/"
    ),
    "maimai": (
        "https://lng-tgk-aime-gw.am-all.net/common_auth/login?site_id=maimaidxex"
        "&redirect_url=https://maimaidx-eng.com/maimai-mobile/&back_url=https://maimai.sega.com/"
    )
}
HOME_URLS = {
    "chunithm": "https://chunithm-net-eng.com/mobile/home/",
    "maimai": "https://maimaidx-eng.com/maimai-mobile/home/",
}
WEEKREPORT_WEBHOOK = DISCORD_WEBHOOK_URL
MONTHREPORT_WEBHOOK = DISCORD_WEBHOOK_URL
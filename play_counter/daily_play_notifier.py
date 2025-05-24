import requests
import time
from play_counter.config import DISCORD_WEBHOOK_URL, NOTIFICATION_CONFIG


def send_notification(
    game: str,
    new_plays: int,
    notify_on_zero: bool = False,
    max_retries: int = 3,
    retry_delay: int = 2,
) -> bool:
    """
    Send a notification about new game plays.

    Args:
        game: Game identifier (e.g., "maimai", "chunithm")
        new_plays: Number of new plays
        notify_on_zero: Whether to send notification when there are no new plays
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Boolean indicating success or failure
    """
    # Skip notification if no new plays and not configured to notify on zero
    if new_plays <= 0 and not notify_on_zero:
        return True

    # Get game-specific configuration
    config = NOTIFICATION_CONFIG.get(game, NOTIFICATION_CONFIG["default"])

    # Create message based on play count
    if new_plays > 0:
        message_template = config.get(
            "message_template",
            "**{game}**: You played **{new_plays}** credits today!",
        )
        message = message_template.format(game=game, new_plays=new_plays)
    else:
        message = f"**{game}**: No new plays today."

    # Prepare payload
    payload = {
        "username": config.get("username", "毎日みのり"),
        "avatar_url": config.get(
            "avatar_url", "https://pbs.twimg.com/media/Fg4AsmAaUAA2TDX?format=jpg"
        ),
        "content": message,
    }

    # Send with retry mechanism
    success = False
    for attempt in range(max_retries):
        try:
            res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if res.status_code == 204:
                print(f"✅ Notification sent for {game} after {attempt + 1} attempt(s)")
                success = True
                break
            else:
                print(
                    f"❌ Discord error (attempt {attempt + 1}/{max_retries}): {res.text}"
                )
        except Exception as e:
            print(
                f"❌ Exception during notification (attempt {attempt + 1}/{max_retries}): {str(e)}"
            )

        # Only sleep if we're going to retry
        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    if not success:
        print(f"❌ Failed to send notification for {game} after {max_retries} attempts")

    return success

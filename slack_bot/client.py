import logging
import time
from typing import Optional, Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config.settings import settings

logger = logging.getLogger("synapse.slack")

class SlackService:
    """Manages Slack API interactions with persona masking and error handling."""

    def __init__(self):
        self.bot_token = settings.slack_bot_token
        self.default_channel = settings.slack_default_channel
        self.client = WebClient(token=self.bot_token) if self.bot_token else None

    def health_check(self) -> Dict[str, Any]:
        """Verifies Slack bot token validity and workspace info."""
        if not self.client:
            return {"status": "unhealthy", "error": "SLACK_BOT_TOKEN missing"}
        try:
            auth_res = self.client.auth_test()
            return {
                "status": "healthy",
                "team": auth_res.get("team"),
                "user": auth_res.get("user"),
                "bot_id": auth_res.get("bot_id"),
                "team_id": auth_res.get("team_id")
            }
        except SlackApiError as e:
            return {"status": "unhealthy", "error": e.response.get("error", str(e))}

    def post_message(
        self,
        text: str,
        channel: Optional[str] = None,
        thread_ts: Optional[str] = None,
        username: Optional[str] = None,
        icon_emoji: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Posts a message to Slack with dynamic persona customization and rate-limit backoff.
        """
        if not self.client:
            logger.error("Slack client not initialized.")
            return None

        target_channel = channel or self.default_channel

        payload: Dict[str, Any] = {
            "channel": target_channel,
            "text": text,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts
        if username:
            payload["username"] = username
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat_postMessage(**payload)
                if response.get("ok"):
                    return {
                        "ts": response.get("ts"),
                        "channel": response.get("channel"),
                        "message": response.get("message")
                    }
            except SlackApiError as e:
                err_code = e.response.get("error")
                logger.warning(f"Slack API error (attempt {attempt}/{max_retries}): {err_code}")
                
                # Handle rate limiting
                if err_code == "ratelimited":
                    retry_after = int(e.response.headers.get("Retry-After", 2))
                    logger.info(f"Rate limited by Slack. Backing off for {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                elif attempt < max_retries:
                    time.sleep(1.0 * attempt)
                    continue
                else:
                    logger.error(f"Failed to post Slack message after {max_retries} attempts: {e}")
                    return None
            except Exception as ex:
                logger.error(f"Unexpected error posting to Slack: {ex}")
                return None

        return None

# Singleton instance
slack_service = SlackService()

from __future__ import annotations

import logging

import httpx


logger = logging.getLogger(__name__)


class LineNotifier:
    def __init__(self, channel_access_token: str, user_id: str) -> None:
        self.channel_access_token = channel_access_token.strip()
        self.user_id = user_id.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.channel_access_token and self.user_id)

    async def send_text(self, text: str) -> bool:
        if not self.enabled:
            logger.warning("LINE notifier is not configured")
            return False

        payload = {
            "to": self.user_id,
            "messages": [{"type": "text", "text": text[:5000]}],
        }

        headers = {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.post(
                    "https://api.line.me/v2/bot/message/push",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("LINE push failed status=%s body=%s", exc.response.status_code, exc.response.text)
            return False
        except httpx.RequestError as exc:
            logger.error("LINE push request failed: %s", exc)
            return False

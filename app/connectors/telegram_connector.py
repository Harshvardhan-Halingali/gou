import requests
import hashlib
from typing import Dict, Any
from app.config import settings
from app.connectors.base_connector import SocialConnector
from app.database.repository import ForensicRepository
import imagehash
from PIL import Image
import io

class TelegramConnector(SocialConnector):
    @property
    def platform_name(self) -> str:
        return "Telegram Bot Ingestion API"

    def is_configured(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN)

    def sync_media(self, max_items: int = 10) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "platform": self.platform_name,
                "status": "NOT_CONFIGURED",
                "message": "Telegram Bot Token is not configured in environment.",
                "synced_count": 0
            }

        token = settings.TELEGRAM_BOT_TOKEN
        url = f"https://api.telegram.org/bot{token}/getUpdates"
        params = {"limit": max_items}

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                return {
                    "platform": self.platform_name,
                    "status": "FAILED",
                    "error": resp.text,
                    "synced_count": 0
                }

            updates = resp.json().get("result", [])
            repo = ForensicRepository()
            synced = 0

            for upd in updates:
                msg = upd.get("message", {})
                photos = msg.get("photo", [])
                if photos:
                    # Best resolution is usually the last photo object
                    best_photo = photos[-1]
                    file_id = best_photo["file_id"]
                    
                    # Call getFile
                    f_resp = requests.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}", timeout=10)
                    if f_resp.status_code == 200:
                        file_path = f_resp.json().get("result", {}).get("file_path")
                        if file_path:
                            download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
                            media_resp = requests.get(download_url, timeout=10)
                            if media_resp.status_code == 200:
                                content = media_resp.content
                                sha256_val = hashlib.sha256(content).hexdigest()
                                with Image.open(io.BytesIO(content)) as img:
                                    phash_val = str(imagehash.phash(img.convert("RGB")))

                                repo.add_indexed_image(
                                    item_id=f"tg_{file_id[:16]}",
                                    source_platform="TELEGRAM",
                                    external_media_id=file_id,
                                    source_url=f"tg://msg/{msg.get('message_id')}",
                                    account_identifier=str(msg.get("chat", {}).get("id")),
                                    file_path="TELEGRAM_BUFFER",
                                    sha256=sha256_val,
                                    phash=phash_val
                                )
                                synced += 1

            return {
                "platform": self.platform_name,
                "status": "COMPLETED",
                "synced_count": synced
            }
        except Exception as e:
            return {
                "platform": self.platform_name,
                "status": "FAILED",
                "error": str(e),
                "synced_count": 0
            }

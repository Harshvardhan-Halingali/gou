import requests
import hashlib
from typing import Dict, Any
from app.config import settings
from app.connectors.base_connector import SocialConnector
from app.database.repository import ForensicRepository
import imagehash
from PIL import Image
import io

class FacebookConnector(SocialConnector):
    @property
    def platform_name(self) -> str:
        return "Facebook Pages (Graph API)"

    def is_configured(self) -> bool:
        return bool(settings.FB_PAGE_ACCESS_TOKEN and settings.FB_PAGE_ID)

    def sync_media(self, max_items: int = 10) -> Dict[str, Any]:
        if not self.is_configured():
            return {
                "platform": self.platform_name,
                "status": "NOT_CONFIGURED",
                "message": "Facebook Page Access Token or Page ID is not configured.",
                "synced_count": 0
            }

        url = f"https://graph.facebook.com/v19.0/{settings.FB_PAGE_ID}/photos"
        params = {
            "fields": "id,images,created_time,link",
            "access_token": settings.FB_PAGE_ACCESS_TOKEN,
            "limit": max_items
        }

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                return {
                    "platform": self.platform_name,
                    "status": "FAILED",
                    "error": resp.text,
                    "synced_count": 0
                }

            data = resp.json().get("data", [])
            repo = ForensicRepository()
            synced = 0

            for item in data:
                images = item.get("images", [])
                if images:
                    img_url = images[0].get("source")
                    if img_url:
                        media_resp = requests.get(img_url, timeout=10)
                        if media_resp.status_code == 200:
                            content = media_resp.content
                            sha256_val = hashlib.sha256(content).hexdigest()
                            with Image.open(io.BytesIO(content)) as img:
                                phash_val = str(imagehash.phash(img.convert("RGB")))

                            repo.add_indexed_image(
                                item_id=f"fb_{item['id']}",
                                source_platform="FACEBOOK",
                                external_media_id=item["id"],
                                source_url=item.get("link") or img_url,
                                account_identifier=settings.FB_PAGE_ID,
                                publication_timestamp=item.get("created_time"),
                                file_path="REMOTE_URL",
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

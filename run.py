import os
import sys
import uvicorn
from app.config import settings

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    reload = os.getenv("RELOAD", "false").lower() in ("true", "1", "yes")

    print("==================================================================")
    print(f"           {settings.APP_NAME} — Forensic Analysis Platform               ")
    print("==================================================================")
    print(f"Starting server at http://{host}:{port} (reload={reload}) ...")
    uvicorn.run("app.main:app", host=host, port=port, reload=reload, log_level="info")

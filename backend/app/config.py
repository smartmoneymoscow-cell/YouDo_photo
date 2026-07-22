import os
from dotenv import load_dotenv

load_dotenv()

# Cloudflare R2
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "youdo-photo")
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")

# Processing
MAX_FILE_SIZE_MB = 100
MAX_FILES_PER_SESSION = 500
SESSION_TTL_HOURS = 48  # auto-cleanup after

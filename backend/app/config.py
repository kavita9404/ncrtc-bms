import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bms.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "480"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

# Tick script (live-map simulator)
TICK_SECONDS = float(os.getenv("TICK_SECONDS", "5"))
# Demo time compression: a bus covers (real speed x multiplier) so movement is visible on the map.
TICK_SPEED_MULTIPLIER = float(os.getenv("TICK_SPEED_MULTIPLIER", "8"))

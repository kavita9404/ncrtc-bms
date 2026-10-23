import os

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, UPLOAD_DIR
from .routers import admin, auth, avls, incidents, notices, reports, scheduling

app = FastAPI(
    title="NCRTC Bus Management System",
    version="1.0.0",
    description="Student capstone backend: AVLS, Scheduling, IMS and CMS modules. All data is seeded demo data.",
)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

api = APIRouter(prefix="/api")
for module in (auth, admin, avls, scheduling, incidents, notices, reports):
    api.include_router(module.router)
app.include_router(api)

os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import webhook, admin

# ✅ NEW IMPORTS (added)
from services.config_manager import get_all_configs
from services.analytics_manager import get_analytics

import logging

# ✅ logging setup (added)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = FastAPI(title="Instagram Comment-to-DM Automation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)
app.include_router(admin.router)

# ✅ startup hook (added)
@app.on_event("startup")
def startup_event():
    try:
        # config auto load + migrate
        get_all_configs()

        # analytics file init check
        get_analytics(days=7)

        logger.info("✅ Backend started successfully")
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")


@app.get("/")
def root():
    return {"status": "ok", "service": "Instagram Comment-to-DM Automation"}


@app.get("/health")
def health():
    return {"status": "healthy"}

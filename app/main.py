from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.admin.images import router as images_router
from app.api.v1.chat.router import router as chat_router
from app.api.v1.voice.router import router as voice_router
from app.api.v1.voice.ws_test import ws_router as voice_ws_router
from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.admin.businesses import router as admin_businesses_router
from app.api.v1.admin.services import router as admin_services_router
from app.api.v1.admin.operating_hours import router as admin_hours_router
from app.api.v1.public.router import router as public_router
from app.api.v1.payments.router import router as payment_router
from app.api.v1.admin.dashboard import router as admin_dashboard_router
from app.api.v1.admin.bookings import router as admin_bookings_router
from app.api.v1.admin.platform import router as admin_platform_router
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.v1.contact.router import router as contact_router
from app.api.v1.public.reviews import router as reviews_router
from app.api.v1.admin.settings import router as admin_settings_router
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import settings



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()

app = FastAPI(
    title="AI Booking System",
    description="LangGraph-powered booking chatbot with voice support, admin dashboard, and Stripe payments",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ai-reservation-crm-system.onrender.com",
        "https://ai-reservation-crm-system-xjz3.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Mount static files for uploaded images
_upload_dir = Path(settings.UPLOAD_DIR).resolve()
_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_upload_dir)), name="uploads")

# Include routers
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(voice_router, prefix="/api/v1/voice", tags=["Voice"])
app.include_router(voice_ws_router, prefix="/api/v1/voice", tags=["Voice WS Test"])
app.include_router(admin_auth_router, prefix="/api/v1/admin/auth", tags=["Admin Auth"])
app.include_router(admin_businesses_router, prefix="/api/v1/admin/businesses", tags=["Admin Businesses"])
app.include_router(admin_services_router, prefix="/api/v1/admin", tags=["Admin Services"])
app.include_router(admin_hours_router, prefix="/api/v1/admin", tags=["Admin Operating Hours"])
app.include_router(public_router, prefix="/api/v1/public", tags=["Public"])
app.include_router(payment_router, prefix="/api/v1", tags=["Payments"])
app.include_router(admin_dashboard_router, prefix="/api/v1/admin", tags=["Admin Dashboard"])
app.include_router(admin_bookings_router, prefix="/api/v1/admin", tags=["Admin Bookings"])
app.include_router(admin_platform_router, prefix="/api/v1/admin", tags=["Admin Platform"])
app.include_router(contact_router, prefix="/api/v1", tags=["Contact"])
app.include_router(images_router, prefix="/api/v1/admin/businesses", tags=["Images"])
app.include_router(reviews_router, prefix="/api/v1/public", tags=["Reviews"])
app.include_router(admin_settings_router)
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
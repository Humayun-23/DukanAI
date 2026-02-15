from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import google.generativeai as genai
from twilio.rest import Client

from config import settings
from database.db import engine, Base
from routers import whatsapp
from endpoints import inventory, dashboard
from services.scheduler import proactive_scheduler

# Initialize database
Base.metadata.create_all(bind=engine)

# Twilio Client Initialization
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

# FastAPI app
app = FastAPI(
    title="Bharat Biz-Agent API",
    description="Autonomous AI Co-Pilot for Indian Businesses - WhatsApp-first, Multilingual, Action-Oriented",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(whatsapp.router, prefix="/api/v1", tags=["WhatsApp Agent"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["Inventory"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard & Analytics"])

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Starting Bharat Biz-Agent...")
    print("=" * 50)
    
    # Start proactive scheduler
    proactive_scheduler.start()
    
    print("=" * 50)
    print("✅ Bharat Biz-Agent is ready!")
    print("📱 WhatsApp webhook: /api/v1/whatsapp")
    print("📊 API docs: /docs")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down Bharat Biz-Agent...")
    proactive_scheduler.stop()
    print("✅ Shutdown complete")

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Bharat Biz-Agent",
        "version": "1.0.0",
        "description": "Autonomous AI Co-Pilot for Indian Businesses",
        "features": [
            "Multilingual Support (Hindi/English/Hinglish)",
            "WhatsApp-first Interface",
            "Autonomous Invoice Generation",
            "Payment Tracking & Reminders",
            "Inventory Management",
            "Voice-to-Text Support",
            "GST Compliance",
            "UPI Integration",
            "Proactive Notifications",
            "Human-in-the-Loop Confirmations"
        ],
        "status": "operational"
    }

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": "2026-02-15T00:00:00Z"
    }

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "path": str(request.url)
        }
    )



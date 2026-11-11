from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers import auth, availability, bookings, businesses, services, slots, users

app = FastAPI(title=settings.app_name)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(businesses.router)
app.include_router(services.router)
app.include_router(availability.router)
app.include_router(slots.router)
app.include_router(bookings.router)


@app.get("/health")
def health():
    """Liveness check: is the API process up?"""
    return {"status": "ok"}


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """Readiness check: can the API actually reach the database?"""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}

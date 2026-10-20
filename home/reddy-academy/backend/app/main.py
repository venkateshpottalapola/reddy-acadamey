from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import FRONTEND_DIR, get_settings
from app.database import get_db
from app.routes import admin_router, public_router
from app.security import get_current_admin


settings = get_settings()
app = FastAPI(title="REDDY ACADEMY Enquiries", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(public_router)
app.include_router(admin_router)


@app.get("/admin/login", include_in_schema=False)
def admin_login_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "admin" / "login.html")


@app.get("/admin/dashboard", include_in_schema=False)
def admin_dashboard_page(request: Request, db: Session = Depends(get_db)):
    try:
        get_current_admin(request, db)
    except HTTPException:
        return RedirectResponse("/admin/login", status_code=303)
    return FileResponse(FRONTEND_DIR / "admin" / "dashboard.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="public-website")

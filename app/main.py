from fastapi import FastAPI

from app.core.config import settings
from app.api.webhooks.whatsapp import router as whatsapp_router
from app.api.admin.products import router as admin_products_router
from app.api.admin.appointments import router as admin_appointments_router
from app.api.admin.me import router as admin_me_router
from app.api.admin.onboarding import router as admin_onboarding_router
from app.api.admin.employees import router as admin_employees_router

# Instancia principal de FastAPI con metadata básica.
app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

# Registramos el router del webhook.
# Todos los endpoints de whatsapp.py quedan accesibles desde la raíz.
app.include_router(whatsapp_router)
app.include_router(admin_products_router)
app.include_router(admin_appointments_router)
app.include_router(admin_me_router)
app.include_router(admin_onboarding_router)
app.include_router(admin_employees_router)


@app.get("/health")
async def health_check():
    # Endpoint de health check para el ALB de AWS.
    # Devuelve 200 si la aplicación está arriba.
    return {"status": "ok", "env": settings.app_env}
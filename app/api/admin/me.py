from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/api/admin/me")
async def get_me(current_user: User = Depends(get_current_user)):
    # Primer endpoint protegido de verdad — confirma de punta a punta que un
    # token de Cognito válido resuelve al User local correcto. Los demás
    # endpoints admin seguirán usando business_id como query param sin
    # protección hasta que conectemos esta pieza a todos ellos (siguiente
    # paso de Fase 5, deliberadamente aparte para no mezclar cambios).
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "role": current_user.role.value,
        "business_id": str(current_user.business_id),
    }
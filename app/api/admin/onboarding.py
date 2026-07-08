from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.auth import get_verified_claims
from app.core.database import get_db_session
from app.models.business import Business
from app.models.user import RoleEnum, User

router = APIRouter()


class BusinessSignupRequest(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    owner_name: str = Field(min_length=1, max_length=255)
    whatsapp_number: str = Field(min_length=1, max_length=20)


@router.post("/api/admin/businesses")
async def create_business(body: BusinessSignupRequest, claims: dict = Depends(get_verified_claims)):
    # Alta de negocio nueva: convierte un login de Cognito "huérfano" (sin
    # User local todavía) en un negocio real con su dueño. Sustituye tener
    # que correr scripts/link_cognito_user.py a mano por cada negocio nuevo.
    cognito_sub = claims["sub"]

    async with get_db_session() as db:
        existing_user = (
            await db.execute(select(User).where(User.cognito_id == cognito_sub))
        ).scalar_one_or_none()
        if existing_user is not None:
            raise HTTPException(
                status_code=409,
                detail="Este usuario de Cognito ya tiene un negocio enlazado.",
            )

        business = Business(name=body.business_name, whatsapp_number=body.whatsapp_number)
        db.add(business)
        await db.flush()  # para obtener business.id antes del commit

        owner = User(
            business_id=business.id,
            whatsapp_number=body.whatsapp_number,
            name=body.owner_name,
            role=RoleEnum.owner,
            cognito_id=cognito_sub,
        )
        db.add(owner)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Ya existe un negocio con ese número de WhatsApp.",
            )

        return {
            "business_id": str(business.id),
            "business_name": business.name,
            "owner_name": owner.name,
        }
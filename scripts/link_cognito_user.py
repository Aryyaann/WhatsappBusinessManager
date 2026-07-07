"""Enlaza un usuario ya creado en Cognito con un User local de un negocio.

Uso:
    python scripts/link_cognito_user.py \\
        --business-id d62a4701-f49a-4f90-8503-9d59346f91e5 \\
        --cognito-sub <sub-del-token-de-cognito> \\
        --name "Aryan" \\
        --whatsapp-number "+34677453127" \\
        --role owner

Se necesita esto porque el login del panel (Cognito) y el flujo de WhatsApp
identifican al usuario de formas distintas: WhatsApp mira Business.whatsapp_
number directamente, mientras que Cognito necesita un User local con
cognito_id para saber a qué negocio/rol pertenece un login. Este script crea
ese puente. Se puede volver a correr para cada negocio/dueño nuevo que se dé
de alta con panel web.
"""
import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.core.database import get_db_session
from app.models.user import User, RoleEnum


async def link_cognito_user(
    business_id: str,
    cognito_sub: str,
    name: str,
    whatsapp_number: str,
    role: str,
) -> None:
    async with get_db_session() as db:
        existing = (
            await db.execute(select(User).where(User.cognito_id == cognito_sub))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Ya existe un User con ese cognito_id: {existing.id} ({existing.name})")
            return

        user = User(
            id=uuid.uuid4(),
            business_id=business_id,
            whatsapp_number=whatsapp_number,
            name=name,
            role=RoleEnum(role),
            cognito_id=cognito_sub,
        )
        db.add(user)
        await db.commit()
        print(f"Usuario creado y enlazado: {user.id} ({user.name}, rol={user.role.value})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--cognito-sub", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--whatsapp-number", required=True)
    parser.add_argument("--role", choices=["owner", "employee"], default="owner")
    args = parser.parse_args()

    asyncio.run(
        link_cognito_user(
            business_id=args.business_id,
            cognito_sub=args.cognito_sub,
            name=args.name,
            whatsapp_number=args.whatsapp_number,
            role=args.role,
        )
    )
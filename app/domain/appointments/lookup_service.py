from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, RoleEnum
from app.models.service import Service


class AppointmentLookupService:
    # Resuelve nombres en lenguaje natural ("Ana", "corte de pelo") a los
    # registros reales de empleado/servicio dentro de un negocio. No usa
    # embeddings (a diferencia del catálogo de productos) porque el número
    # de empleados y servicios de un negocio es pequeño — un ILIKE parcial
    # es suficiente y mucho más barato.

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_employee_by_name(self, business_id: str, name: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(
                User.business_id == business_id,
                User.role == RoleEnum.employee,
                User.name.ilike(f"%{name}%"),
            )
        )
        return result.scalars().first()

    async def find_service_by_name(self, business_id: str, name: str) -> Optional[Service]:
        result = await self.db.execute(
            select(Service).where(
                Service.business_id == business_id,
                Service.is_active == True,
                Service.name.ilike(f"%{name}%"),
            )
        )
        return result.scalars().first()

    async def list_employees(self, business_id: str) -> list[User]:
        # Todos los empleados del negocio — se usa para buscar alternativas
        # cuando el empleado pedido no tiene horario planificado esa
        # semana. NOTA: no filtra por "quién hace este servicio" porque
        # employee_services (la tabla pensada para eso) no se usa todavía
        # en ningún sitio del código — de momento se comprueba disponibilidad
        # de todos los empleados sin distinción.
        result = await self.db.execute(
            select(User).where(User.business_id == business_id, User.role == RoleEnum.employee).order_by(User.name)
        )
        return list(result.scalars().all())
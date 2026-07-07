import asyncio
from datetime import date, time, timedelta
from decimal import Decimal

from app.core.database import get_db_session
from app.models.user import User, RoleEnum
from app.models.service import Service
from app.models.employee_schedule import EmployeeSchedule
from app.models.employee_service import EmployeeService
from app.domain.appointments.booking_handler import handle_appointment_request

BUSINESS_ID = "d62a4701-f49a-4f90-8503-9d59346f91e5"

# Próximo lunes desde hoy, para que la prueba tenga sentido temporal.
def next_monday():
    today = date.today()
    days_ahead = (0 - today.weekday()) % 7
    days_ahead = days_ahead or 7  # si hoy ya es lunes, coge el siguiente
    return today + timedelta(days=days_ahead)

TARGET_DATE = next_monday()


async def setup():
    async with get_db_session() as db:
        employee = User(
            business_id=BUSINESS_ID,
            whatsapp_number="+34600111222",  # número de prueba, no hace falta que sea real
            name="Ana",
            role=RoleEnum.employee,
        )
        db.add(employee)
        await db.flush()  # para tener employee.id sin hacer commit todavía

        service = Service(
            business_id=BUSINESS_ID,
            name="Corte de pelo",
            duration_minutes=30,
            price=Decimal("15.00"),
        )
        db.add(service)
        await db.flush()

        db.add(EmployeeSchedule(
            user_id=employee.id,
            day_of_week=0,  # lunes
            start_time=time(9, 0),
            end_time=time(14, 0),
        ))
        db.add(EmployeeService(user_id=employee.id, service_id=service.id))

        await db.commit()
        print(f"Empleada creada: {employee.id} — Ana", flush=True)
        print(f"Servicio creado: {service.id} — Corte de pelo (30 min)", flush=True)
        print(f"Horario: lunes 9:00-14:00 | Próximo lunes de prueba: {TARGET_DATE}", flush=True)


async def main():
    await setup()

    async with get_db_session() as db:
        # 1. Preguntar disponibilidad
        result = await handle_appointment_request(
            db,
            business_id=BUSINESS_ID,
            customer_phone="+34600999888",
            message_text=f"quiero un corte de pelo con Ana el {TARGET_DATE.strftime('%d/%m/%Y')}",
        )
        print("\n--- Consulta de disponibilidad ---", flush=True)
        print("Respuesta:", result["reply"], flush=True)
        print("Tools llamadas:", result["tools_called"], flush=True)

    async with get_db_session() as db:
        # 2. Reservar directamente a las 9:00
        result = await handle_appointment_request(
            db,
            business_id=BUSINESS_ID,
            customer_phone="+34600999888",
            message_text=f"resérvame el corte con Ana el {TARGET_DATE.strftime('%d/%m/%Y')} a las 9:00, soy Lucía",
        )
        print("\n--- Reserva ---", flush=True)
        print("Respuesta:", result["reply"], flush=True)
        print("Tools llamadas:", result["tools_called"], flush=True)

asyncio.run(main())
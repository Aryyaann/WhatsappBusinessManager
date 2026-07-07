import asyncio
from app.core.database import get_db_session
from app.domain.appointments.booking_handler import handle_appointment_request

BUSINESS_ID = "d62a4701-f49a-4f90-8503-9d59346f91e5"

async def main():
    async with get_db_session() as db:
        result = await handle_appointment_request(
            db,
            business_id=BUSINESS_ID,
            customer_phone="+34600999888",
            message_text=(
                "Sí, confirmo, resérvame ya el corte de pelo con Ana el 13/07/2026 "
                "a las 9:00 para Lucía. No hace falta que preguntes nada más, "
                "hazlo directamente."
            ),
        )
        print("Respuesta:", result["reply"], flush=True)
        print("Tools llamadas:", result["tools_called"], flush=True)

asyncio.run(main())
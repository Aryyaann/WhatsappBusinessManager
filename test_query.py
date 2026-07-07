print("PASO 0: el script arrancó", flush=True)

import sys
print(f"PASO 1: Python {sys.version}", flush=True)

from app.core.config import settings
print("PASO 2: config cargada OK", flush=True)

from app.core.database import get_db_session
print("PASO 3: database module OK", flush=True)

from app.domain.conversations.query_handler import handle_stock_query
print("PASO 4: query_handler importado OK", flush=True)

import asyncio
import traceback

BUSINESS_ID = "d62a4701-f49a-4f90-8503-9d59346f91e5"
PREGUNTA = "¿qué me queda de tinte rubio?"

async def main():
    print("PASO 5: entrando a main()", flush=True)
    async with get_db_session() as db:
        print("PASO 6: sesión de BD abierta, llamando a Claude...", flush=True)
        result = await handle_stock_query(db, business_id=BUSINESS_ID, query_text=PREGUNTA)
        print("PASO 7: Respuesta de Claude:", result["reply"], flush=True)
        print("PASO 7b: ¿Usó la herramienta?:", result["tool_called"], flush=True)

try:
    asyncio.run(main())
except Exception:
    print("ERROR CAPTURADO:", flush=True)
    traceback.print_exc()

print("PASO 8: script terminado", flush=True)
import sys
import os
import asyncio

# Configurar encoding UTF-8 en stdout/stderr de Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    if sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    port = getattr(settings, "SERVER_PORT", getattr(settings, "API_PORT", 8001))
    host = getattr(settings, "SERVER_HOST", "0.0.0.0")
    print(f"Iniciando Sistema Fruver (Gestión de Pedidos, Clientes y Facturas) en http://{host}:{port}")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        loop="asyncio"
    )

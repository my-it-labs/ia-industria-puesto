"""Esclavo Modbus TCP. Registro 10 es el paro de seguridad y nadie lo escribe."""
import threading
import time

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartTcpServer

from linea.config import MODBUS_PORT
from linea.estado import leer


def main() -> None:
    # Dirección 0.. ; el 10 queda en 0 (paro de seguridad).
    bloque = ModbusSequentialDataBlock(0, [0] * 16)
    contexto_esclavo = ModbusSlaveContext(hr=bloque)
    contexto = ModbusServerContext(slaves=contexto_esclavo, single=True)

    def refrescar():
        while True:
            try:
                estado = leer()
            except (OSError, ValueError):
                time.sleep(0.5)
                continue
            # El esclavo suma 1 a la dirección del cliente (zero_mode desactivado).
            bloque.setValues(
                1,
                [
                    int(round(estado["temperatura_c"] * 10)),
                    int(round(estado["vibracion_mm_s"] * 1000)),
                    int(round(estado["corriente_a"] * 100)),
                    int(estado["secuencia"]) % 10000,
                ],
            )
            time.sleep(0.5)

    threading.Thread(target=refrescar, daemon=True).start()
    print(f"modbus: escuchando en 0.0.0.0:{MODBUS_PORT}", flush=True)
    StartTcpServer(context=contexto, address=("0.0.0.0", MODBUS_PORT))


if __name__ == "__main__":
    main()

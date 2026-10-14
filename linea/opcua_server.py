"""Servidor OPC-UA: expone el último estado de EST-01."""
import asyncio
import json

from asyncua import Server

from linea.estado import leer


async def main() -> None:
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/linea/server")
    server.set_server_name("EST-01")
    idx = await server.register_namespace("urn:linea:est01")
    obj = await server.nodes.objects.add_object(idx, "Estacion")
    temp = await obj.add_variable(idx, "Temperatura", 0.0)
    vib = await obj.add_variable(idx, "Vibracion", 0.0)
    cur = await obj.add_variable(idx, "Corriente", 0.0)
    pieza = await obj.add_variable(idx, "Pieza", "P0000")
    for nodo in (temp, vib, cur, pieza):
        await nodo.set_writable()
    print(f"opcua: escuchando, namespace={idx}", flush=True)
    async with server:
        while True:
            try:
                estado = leer()
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                await asyncio.sleep(0.5)
                continue
            await temp.write_value(float(estado["temperatura_c"]))
            await vib.write_value(float(estado["vibracion_mm_s"]))
            await cur.write_value(float(estado["corriente_a"]))
            await pieza.write_value(str(estado["pieza_id"]))
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(main())

"""Origen de la línea: escribe el estado y lo publica por MQTT."""
import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from linea.config import ESTACION, MQTT_HOST, MQTT_PORT, TOPIC_CICLO
from linea.estado import escribir

INTERVALO = 1.0


def lectura(n: int) -> dict:
    rng = random.Random(1000 + n)
    temperatura = 61.0 + (n % 7) * 0.35 + rng.uniform(-0.15, 0.15)
    vibracion = 0.22 + (n % 5) * 0.015
    corriente = 4.05 + rng.uniform(-0.08, 0.08)
    return {
        "estacion": ESTACION,
        "pieza_id": f"P{n:04d}",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "temperatura_c": round(temperatura, 2),
        "vibracion_mm_s": round(vibracion, 3),
        "corriente_a": round(corriente, 2),
        "secuencia": n,
    }


def conectar():
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sensor-est01")
    while True:
        try:
            cliente.connect(MQTT_HOST, MQTT_PORT, 30)
            cliente.loop_start()
            return cliente
        except Exception as exc:
            print(f"sensor: esperando al broker ({exc})", flush=True)
            time.sleep(1)


def main() -> None:
    cliente = conectar()
    n = 1
    while True:
        estado = lectura(n)
        escribir(estado)
        cliente.publish(TOPIC_CICLO, json.dumps(estado), qos=0)
        print(f"sensor: {estado['pieza_id']} {estado['temperatura_c']} C", flush=True)
        n += 1
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()

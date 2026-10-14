"""Almacén: cada ciclo MQTT queda en SQLite."""
import json
import sqlite3
import time

import paho.mqtt.client as mqtt

from linea.config import DATA, MQTT_HOST, MQTT_PORT, TOPIC_CICLO


def conectar_db() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DATA / "historial.sqlite")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pieza_id TEXT,
            ts TEXT,
            temperatura_c REAL,
            vibracion_mm_s REAL,
            corriente_a REAL,
            payload TEXT
        )
        """
    )
    con.commit()
    return con


def main() -> None:
    con = conectar_db()

    def on_message(_client, _userdata, msg):
        estado = json.loads(msg.payload.decode())
        con.execute(
            "INSERT INTO lecturas (pieza_id, ts, temperatura_c, vibracion_mm_s, corriente_a, payload) VALUES (?, ?, ?, ?, ?, ?)",
            (
                estado.get("pieza_id"),
                estado.get("ts"),
                estado.get("temperatura_c"),
                estado.get("vibracion_mm_s"),
                estado.get("corriente_a"),
                msg.payload.decode(),
            ),
        )
        con.commit()
        print(f"archivador: {estado.get('pieza_id')}", flush=True)

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="archivador-est01")
    cliente.on_message = on_message
    while True:
        try:
            cliente.connect(MQTT_HOST, MQTT_PORT, 30)
            break
        except Exception as exc:
            print(f"archivador: esperando al broker ({exc})", flush=True)
            time.sleep(1)
    cliente.subscribe(TOPIC_CICLO)
    cliente.loop_forever()


if __name__ == "__main__":
    main()

import os
from pathlib import Path

ESTACION = "EST-01"
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC_CICLO = "linea/est01/ciclo"
TOPIC_DICTAMEN = "linea/est01/dictamen"
OPCUA_ENDPOINT = os.getenv("OPCUA_ENDPOINT", "opc.tcp://opcua:4840/linea/server")
MODBUS_HOST = os.getenv("MODBUS_HOST", "modbus")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "1502"))
PANEL_URL = os.getenv("PANEL_URL", "http://panel:8501")
API_URL = os.getenv("API_URL", "http://api:8000")
LLM_URL = os.getenv("LLM_URL", "http://llm:8088")
DATA = Path(os.getenv("DATA_DIR", "/data"))
MODELO_PATH = Path(os.getenv("MODELO_PATH", "/modelos/qwen2.5-0.5b-instruct-q4_k_m.gguf"))
MODELO_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/"
    "qwen2.5-0.5b-instruct-q4_k_m.gguf"
)
UMBRAL_TEMPERATURA = 70.0
VERSION_ARRANQUE = "defecto-0.1"
REGISTRO_PARO = 10

SERVICIOS = [
    {"nombre": "mosquitto", "puerto": 1883, "para": "transporte MQTT de los ciclos"},
    {"nombre": "sensor", "puerto": None, "para": "origen: publica el estado de EST-01"},
    {"nombre": "archivador", "puerto": None, "para": "almacén SQLite de ciclos"},
    {"nombre": "opcua", "puerto": 4840, "para": "la misma señal, como servidor OPC-UA"},
    {"nombre": "modbus", "puerto": 1502, "para": "la misma señal, como esclavo Modbus TCP"},
    {"nombre": "panel", "puerto": 8501, "para": "indicadores del turno"},
    {"nombre": "llm", "puerto": 8088, "para": "inferencia del modelo generativo, solo en M05"},
    {"nombre": "api", "puerto": 8000, "para": "servicio de inferencia del clasificador, desde M07"},
]

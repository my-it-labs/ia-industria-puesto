"""Importa los paquetes que instala la imagen de los laboratorios."""
modulos = (
    "paho.mqtt.client",
    "asyncua",
    "pymodbus",
    "pandas",
    "sklearn",
    "numpy",
    "PIL",
    "fastapi",
    "uvicorn",
    "streamlit",
    "joblib",
    "httpx",
    "diskcache",
    "llama_cpp",
)
for nombre in modulos:
    __import__(nombre)
print("OK imports", flush=True)

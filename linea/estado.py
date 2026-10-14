import json
from linea.config import DATA


def ruta():
    return DATA / "estado.json"


def escribir(estado: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    destino = ruta()
    temporal = destino.with_suffix(".json.tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    temporal.replace(destino)


def leer() -> dict:
    return json.loads(ruta().read_text(encoding="utf-8"))

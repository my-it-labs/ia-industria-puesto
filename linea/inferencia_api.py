"""Servicio de inferencia del clasificador de defecto. La versión se fija al arrancar."""
import json
from datetime import datetime, timezone

import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from linea.config import DATA, VERSION_ARRANQUE

app = FastAPI(title="EST-01 inferencia")
MODELO = None
VERSION = VERSION_ARRANQUE


class Pieza(BaseModel):
    pieza_id: str
    temperatura_c: float
    vibracion_mm_s: float
    corriente_a: float
    presion_bar: float


@app.on_event("startup")
def cargar():
    global MODELO, VERSION
    ruta = DATA / "modelo_defecto.joblib"
    if not ruta.exists():
        raise RuntimeError("No está modelo_defecto.joblib. Corre antes el laboratorio M03-03.")
    MODELO = joblib.load(ruta)
    fichero = DATA / "VERSION"
    VERSION = fichero.read_text(encoding="utf-8").strip() if fichero.exists() else VERSION_ARRANQUE


@app.get("/salud")
def salud():
    return {"estado": "ok", "version": VERSION}


@app.post("/predecir")
def predecir(pieza: Pieza):
    if MODELO is None:
        raise HTTPException(503, "modelo no cargado")
    import pandas as pd

    fila = pd.DataFrame(
        [
            {
                "temperatura_c": pieza.temperatura_c,
                "vibracion_mm_s": pieza.vibracion_mm_s,
                "corriente_a": pieza.corriente_a,
                "presion_bar": pieza.presion_bar,
            }
        ]
    )
    proba = float(MODELO.predict_proba(fila)[0, 1])
    dictamen = "revisar" if proba >= 0.5 else "seguir"
    registro = {
        "pieza_id": pieza.pieza_id,
        "version": VERSION,
        "entrada": pieza.model_dump(),
        "dictamen": dictamen,
        "probabilidad": round(proba, 4),
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / "predicciones.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro

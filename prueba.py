"""Carga el modelo pequeño y responde una frase. No es un laboratorio."""
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

MODELO = Path(os.environ["MODELO_PATH"])
app = FastAPI()
LLM = None


class Mensaje(BaseModel):
    role: str
    content: str


class Peticion(BaseModel):
    messages: list[Mensaje]
    max_tokens: int = 16


@app.on_event("startup")
def cargar():
    global LLM
    if not MODELO.exists():
        raise RuntimeError(f"Falta el modelo en {MODELO}")
    from llama_cpp import Llama

    LLM = Llama(model_path=str(MODELO), n_ctx=1024, n_threads=4, verbose=False)


@app.get("/salud")
def salud():
    return {"estado": "ok"}


@app.post("/v1/chat/completions")
def chat(peticion: Peticion):
    return LLM.create_chat_completion(
        messages=[m.model_dump() for m in peticion.messages],
        max_tokens=peticion.max_tokens,
        temperature=0.1,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8088)

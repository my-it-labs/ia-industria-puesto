"""Inferencia local del modelo generativo pequeño. No sale a ninguna API externa."""
from fastapi import FastAPI
from pydantic import BaseModel

from linea.config import MODELO_PATH

app = FastAPI(title="EST-01 llm local")
LLM = None


class Mensaje(BaseModel):
    role: str
    content: str


class Peticion(BaseModel):
    messages: list[Mensaje]
    max_tokens: int = 80


@app.on_event("startup")
def cargar():
    global LLM
    if not MODELO_PATH.exists():
        raise RuntimeError(f"Falta el modelo en {MODELO_PATH}")
    from llama_cpp import Llama

    LLM = Llama(
        model_path=str(MODELO_PATH),
        n_ctx=1024,
        n_threads=4,
        verbose=False,
    )
    print("llm: modelo cargado", flush=True)


@app.get("/salud")
def salud():
    return {"estado": "ok", "modelo": MODELO_PATH.name}


@app.post("/v1/chat/completions")
def chat(peticion: Peticion):
    salida = LLM.create_chat_completion(
        messages=[m.model_dump() for m in peticion.messages],
        max_tokens=peticion.max_tokens,
        temperature=0.1,
    )
    return salida


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8088)

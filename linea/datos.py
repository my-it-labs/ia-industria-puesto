"""Históricos sintéticos de EST-01. La etiqueta de defecto llega después del proceso."""
import random
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

from linea.config import DATA


COLUMNAS = ["pieza_id", "temperatura_c", "vibracion_mm_s", "corriente_a", "presion_bar", "defecto"]


def _fila(i: int, rng: random.Random) -> dict:
    temperatura = rng.gauss(62, 2.4)
    vibracion = abs(rng.gauss(0.25, 0.07))
    corriente = rng.gauss(4.1, 0.15)
    presion = rng.gauss(6.0, 0.12)
    defecto = int(temperatura > 65.5 or vibracion > 0.42)
    if rng.random() < 0.02:
        defecto = 1 - defecto
    return {
        "pieza_id": f"H{i:04d}",
        "temperatura_c": round(temperatura, 2),
        "vibracion_mm_s": round(vibracion, 3),
        "corriente_a": round(corriente, 2),
        "presion_bar": round(presion, 2),
        "defecto": defecto,
    }


def generar_limpio(n: int = 800, seed: int = 7) -> pd.DataFrame:
    rng = random.Random(seed)
    return pd.DataFrame([_fila(i, rng) for i in range(1, n + 1)])


def escribir_crudo(destino: Path | None = None, n: int = 800, seed: int = 7) -> Path:
    """Copia de planta: huecos, décimas y un sensor clavado en 9999."""
    df = generar_limpio(n=n, seed=seed)
    rng = random.Random(seed + 1)
    crudo = df.copy()
    for i in crudo.index:
        tiro = rng.random()
        if tiro < 0.04:
            crudo.at[i, "temperatura_c"] = pd.NA
        elif tiro < 0.07:
            crudo.at[i, "temperatura_c"] = round(float(crudo.at[i, "temperatura_c"]) * 10, 1)
        elif tiro < 0.08:
            crudo.at[i, "temperatura_c"] = 9999
    ruta = destino or (DATA / "crudo.csv")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    crudo.to_csv(ruta, index=False)
    return ruta


def limpiar(origen: Path, destino: Path) -> dict:
    crudo = pd.read_csv(origen)
    trabajo = crudo.copy()
    imposibles = []
    temperaturas = []
    for valor in trabajo["temperatura_c"]:
        if pd.isna(valor):
            temperaturas.append(pd.NA)
            continue
        numero = float(valor)
        if numero >= 9999:
            imposibles.append(numero)
            temperaturas.append(pd.NA)
            continue
        if numero > 150:
            numero = numero / 10
        temperaturas.append(round(numero, 2))
    trabajo["temperatura_c"] = temperaturas
    trabajo["hueco"] = trabajo["temperatura_c"].isna().astype(int)
    imposibles_df = crudo[crudo["temperatura_c"].apply(lambda v: pd.notna(v) and float(v) >= 9999)]
    limpio = trabajo.dropna(subset=["temperatura_c"]).drop_duplicates("pieza_id")
    destino.parent.mkdir(parents=True, exist_ok=True)
    limpio.to_csv(destino, index=False)
    ruta_imp = destino.with_name("imposibles.csv")
    imposibles_df.to_csv(ruta_imp, index=False)
    return {
        "filas_crudo": int(len(crudo)),
        "filas_limpias": int(len(limpio)),
        "huecos": int(trabajo["hueco"].sum()),
        "imposibles": int(len(imposibles_df)),
        "piezas_unicas": int(limpio["pieza_id"].nunique()),
    }


def vigilancia(n_normal: int = 180, n_raros: int = 20, seed: int = 11) -> pd.DataFrame:
    rng = random.Random(seed)
    filas = []
    for i in range(1, n_normal + 1):
        fila = _fila(i, rng)
        fila["inyectada"] = 0
        filas.append(fila)
    for i in range(n_normal + 1, n_normal + n_raros + 1):
        fila = _fila(i, rng)
        fila["vibracion_mm_s"] = round(1.1 + rng.random() * 0.4, 3)
        fila["inyectada"] = 1
        filas.append(fila)
    return pd.DataFrame(filas)


def _imagen(buena: bool, semilla: int, marca: int | None = None) -> tuple[Image.Image, int | None]:
    rng = random.Random(semilla)
    imagen = Image.new("L", (64, 64), color=170 + rng.randint(0, 15))
    draw = ImageDraw.Draw(imagen)
    draw.ellipse((12, 14, 52, 50), fill=120 + rng.randint(0, 10))
    y = None
    if not buena:
        y = marca if marca is not None else rng.randint(20, 44)
        draw.line((8, y, 56, y), fill=250, width=2)
    return imagen, y


def generar_imagenes(raiz: Path | None = None) -> dict:
    raiz = raiz or (DATA / "imagenes")
    buenas = raiz / "buenas"
    malas = raiz / "defectuosas"
    buenas.mkdir(parents=True, exist_ok=True)
    malas.mkdir(parents=True, exist_ok=True)
    manifiesto = []
    for i in range(40):
        img, _ = _imagen(True, 2000 + i)
        ruta = buenas / f"ok_{i:02d}.png"
        img.save(ruta)
        manifiesto.append({"ruta": str(ruta), "defecto": 0, "y": ""})
    for i in range(40):
        y = 18 + (i % 20)
        img, y = _imagen(False, 3000 + i, marca=y)
        ruta = malas / f"ko_{i:02d}.png"
        img.save(ruta)
        manifiesto.append({"ruta": str(ruta), "defecto": 1, "y": y})
    tabla = pd.DataFrame(manifiesto)
    tabla.to_csv(raiz / "manifiesto.csv", index=False)
    return {"buenas": 40, "defectuosas": 40, "raiz": str(raiz)}

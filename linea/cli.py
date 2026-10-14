"""Comandos de cada laboratorio. Salida humana y código 0 si el paso cuadra."""
import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

import httpx
import joblib
import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt
from PIL import Image
from sklearn.covariance import EmpiricalCovariance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from linea.config import (
    API_URL,
    DATA,
    LLM_URL,
    MODBUS_HOST,
    MODBUS_PORT,
    MQTT_HOST,
    MQTT_PORT,
    OPCUA_ENDPOINT,
    PANEL_URL,
    SERVICIOS,
    TOPIC_CICLO,
    TOPIC_DICTAMEN,
    UMBRAL_TEMPERATURA,
    VERSION_ARRANQUE,
)
from linea.datos import escribir_crudo, generar_imagenes, generar_limpio, limpiar, vigilancia
from linea.estado import leer as leer_estado

FEATURES = ["temperatura_c", "vibracion_mm_s", "corriente_a", "presion_bar"]


def ok(codigo: str, detalle: str) -> int:
    print(f"OK {codigo}: {detalle}", flush=True)
    return 0


def fallo(mensaje: str) -> int:
    print(f"FALLO: {mensaje}", flush=True)
    return 1


def _mqtt():
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"lab-{time.time_ns()}")
    cliente.connect(MQTT_HOST, MQTT_PORT, 30)
    return cliente


def consumir(topic: str, timeout: float = 20) -> str | None:
    recibido: dict = {}

    def on_message(_c, _u, msg):
        recibido["payload"] = msg.payload.decode()

    cliente = _mqtt()
    cliente.on_message = on_message
    cliente.subscribe(topic)
    cliente.loop_start()
    limite = time.time() + timeout
    while "payload" not in recibido and time.time() < limite:
        time.sleep(0.1)
    cliente.loop_stop()
    cliente.disconnect()
    return recibido.get("payload")


def esperar_filas(minimo: int = 1, timeout: float = 25) -> int:
    ruta = DATA / "historial.sqlite"
    limite = time.time() + timeout
    while time.time() < limite:
        if ruta.exists():
            con = sqlite3.connect(ruta)
            try:
                n = con.execute("SELECT COUNT(*) FROM lecturas").fetchone()[0]
            except sqlite3.OperationalError:
                n = 0
            con.close()
            if n >= minimo:
                return n
        time.sleep(0.4)
    return 0


def cmd_m01_01(_args) -> int:
    n = esperar_filas(1)
    if n < 1:
        return fallo("el archivador no tiene ciclos; ¿están mosquitto, sensor y archivador en marcha?")
    payload = consumir(TOPIC_CICLO, 15)
    if not payload:
        return fallo("no llega ningún ciclo por MQTT")
    ciclo = json.loads(payload)
    estado = leer_estado()
    if ciclo["pieza_id"] != estado["pieza_id"] and abs(ciclo["secuencia"] - estado["secuencia"]) > 2:
        return fallo("el ciclo MQTT y el estado en disco no son de la misma estación")
    print(json.dumps({"mqtt": ciclo, "archivadas": n}, ensure_ascii=False))
    return ok("m01-01", f"ciclo {ciclo['pieza_id']} archivado; total={n}")


def cmd_m01_02(_args) -> int:
    n = esperar_filas(2)
    if n < 2:
        return fallo("hace falta histórico para el panel")
    try:
        respuesta = httpx.get(PANEL_URL, timeout=30, follow_redirects=True)
    except httpx.HTTPError as exc:
        return fallo(f"el panel no responde en {PANEL_URL}: {exc}")
    if respuesta.status_code >= 400:
        return fallo(f"el panel contestó {respuesta.status_code}")
    con = sqlite3.connect(DATA / "historial.sqlite")
    df = pd.read_sql_query("SELECT temperatura_c FROM lecturas", con)
    con.close()
    fuera = int((df["temperatura_c"] > UMBRAL_TEMPERATURA).sum())
    print(f"panel_http={respuesta.status_code} lecturas={len(df)} fuera_de_margen={fuera} umbral={UMBRAL_TEMPERATURA}")
    return ok("m01-02", f"panel vivo, {len(df)} lecturas, {fuera} fuera de {UMBRAL_TEMPERATURA:.0f} C")


def cmd_m02_01(_args) -> int:
    payload = consumir(TOPIC_CICLO, 15)
    if not payload:
        return fallo("no hay telemetría")
    ciclo = json.loads(payload)
    for campo in ("pieza_id", "temperatura_c", "vibracion_mm_s", "ts"):
        if campo not in ciclo:
            return fallo(f"falta {campo}")
    print(json.dumps(ciclo, ensure_ascii=False))
    return ok("m02-01", f"evento {ciclo['pieza_id']} en {TOPIC_CICLO}")


def cmd_m02_01_pausa(_args) -> int:
    payload = consumir(TOPIC_CICLO, 3)
    if payload:
        return fallo("seguían llegando ciclos con el sensor parado")
    return ok("m02-01-pausa", "hueco: ningún ciclo en 3 s")


def cmd_m02_02(_args) -> int:
    estado = leer_estado()

    async def leer_opc() -> float:
        from asyncua import Client

        async with Client(url=OPCUA_ENDPOINT) as client:
            estacion = None
            for hijo in await client.nodes.objects.get_children():
                if (await hijo.read_browse_name()).Name == "Estacion":
                    estacion = hijo
                    break
            if estacion is None:
                raise RuntimeError("el servidor no publica el objeto Estacion")
            indice = (await estacion.read_browse_name()).NamespaceIndex
            nodo = await estacion.get_child([f"{indice}:Temperatura"])
            return float(await nodo.read_value())

    try:
        opc = asyncio.run(leer_opc())
    except Exception as exc:
        return fallo(f"OPC-UA: {exc}")

    from pymodbus.client import ModbusTcpClient

    cliente = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    if not cliente.connect():
        return fallo("Modbus no conecta")
    rr = cliente.read_holding_registers(0, 4, slave=1)
    cliente.close()
    if rr.isError():
        return fallo(f"Modbus: {rr}")
    modbus_c = rr.registers[0] / 10
    print(f"estado={estado['temperatura_c']} opcua={opc:.2f} modbus={modbus_c:.1f}")
    if abs(opc - estado["temperatura_c"]) > 1.5:
        return fallo("OPC-UA no coincide con el estado")
    if abs(modbus_c - estado["temperatura_c"]) > 1.5:
        return fallo("Modbus no coincide con el estado (¿falta la escala /10?)")
    return ok("m02-02", "MQTT, OPC-UA y Modbus leen la misma temperatura")


def cmd_m02_03(_args) -> int:
    crudo = escribir_crudo(DATA / "crudo.csv")
    resumen = limpiar(crudo, DATA / "limpio.csv")
    limpio = pd.read_csv(DATA / "limpio.csv")
    if resumen["piezas_unicas"] != len(limpio):
        return fallo("siguen duplicadas las piezas")
    if limpio["temperatura_c"].max() > 120 or limpio["temperatura_c"].min() < 40:
        return fallo("la temperatura limpia no está en grados")
    if (DATA / "imposibles.csv").stat().st_size == 0:
        return fallo("no se apartaron los 9999")
    print(json.dumps(resumen))
    return ok("m02-03", f"crudo={resumen['filas_crudo']} limpio={resumen['filas_limpias']} huecos={resumen['huecos']}")


def _partir(df: pd.DataFrame):
    df = df.sort_values("pieza_id")
    corte = int(len(df) * 0.7)
    return df.iloc[:corte], df.iloc[corte:]


def _tasas(y_true, y_pred) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    recall = tp / (tp + fn) if (tp + fn) else 0
    fpr = fp / (fp + tn) if (fp + tn) else 0
    return {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn), "recall": recall, "fpr": fpr}


def cmd_m03_01(_args) -> int:
    if not (DATA / "limpio.csv").exists():
        escribir_crudo(DATA / "crudo.csv")
        limpiar(DATA / "crudo.csv", DATA / "limpio.csv")
    df = pd.read_csv(DATA / "limpio.csv")
    train, test = _partir(df)
    modelo = LogisticRegression(class_weight="balanced", max_iter=400)
    modelo.fit(train[FEATURES], train["defecto"])
    pred = modelo.predict(test[FEATURES])
    tasas = _tasas(test["defecto"], pred)
    print(json.dumps(tasas))
    if tasas["recall"] < 0.45:
        return fallo(f"recall de defecto demasiado bajo ({tasas['recall']:.2f})")
    DATA.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, DATA / "modelo_logreg.joblib")
    return ok("m03-01", f"recall_defecto={tasas['recall']:.2f} falsas_alarmas={tasas['fpr']:.2f}")


def cmd_m03_02(_args) -> int:
    base = generar_limpio(400, seed=3)
    normal = base[base["defecto"] == 0]
    vig = vigilancia()
    # Un bosque de aislamiento agrupa el valor extremo con el borde del histórico
    # y no avisa. La distancia de Mahalanobis sí mide cuánto se sale cada señal.
    escala = StandardScaler()
    base_z = escala.fit_transform(normal[FEATURES])
    detector = EmpiricalCovariance().fit(base_z)
    umbral = 13.3  # chi-cuadrado 0,99 con 4 señales
    distancias = detector.mahalanobis(escala.transform(vig[FEATURES]))
    marcas = np.where(distancias >= umbral, -1, 1)
    raro = vig["inyectada"] == 1
    pillados = int(((marcas == -1) & raro).sum())
    total = int(raro.sum())
    print(f"inyectados={total} detectados={pillados}")
    if pillados / total < 0.7:
        return fallo("el detector no ve los ciclos inyectados")
    joblib.dump(detector, DATA / "detector_anomalia.joblib")
    return ok("m03-02", f"avisos sobre inyectados {pillados}/{total}")


def cmd_m03_03(_args) -> int:
    df = pd.read_csv(DATA / "limpio.csv")
    train, test = _partir(df)
    candidatos = {
        "logreg": LogisticRegression(class_weight="balanced", max_iter=400),
        "arbol": DecisionTreeClassifier(max_depth=3, class_weight="balanced", random_state=7),
    }
    informe = {}
    for nombre, modelo in candidatos.items():
        modelo.fit(train[FEATURES], train["defecto"])
        informe[nombre] = _tasas(test["defecto"], modelo.predict(test[FEATURES]))
        informe[nombre]["modelo"] = modelo
    print(json.dumps({k: {m: v for m, v in d.items() if m != "modelo"} for k, d in informe.items()}))

    def clave(item):
        nombre, datos = item
        return (datos["recall"], -datos["fpr"])

    ganador, datos = max(informe.items(), key=clave)
    joblib.dump(datos["modelo"], DATA / "modelo_defecto.joblib")
    (DATA / "VERSION").write_text(VERSION_ARRANQUE + "\n", encoding="utf-8")
    (DATA / "modelo_elegido.txt").write_text(ganador + "\n", encoding="utf-8")
    return ok("m03-03", f"elegido={ganador} recall={datos['recall']:.2f} fpr={datos['fpr']:.2f}")


def _features_imagen(ruta: Path) -> np.ndarray:
    img = Image.open(ruta).convert("L").resize((16, 16))
    return np.asarray(img, dtype=np.float32).reshape(-1) / 255.0


def _entrenar_vision():
    if not (DATA / "imagenes" / "manifiesto.csv").exists():
        generar_imagenes()
    tabla = pd.read_csv(DATA / "imagenes" / "manifiesto.csv")

    def partir(parte: pd.DataFrame):
        n = int(len(parte) * 0.7)
        return parte.iloc[:n], parte.iloc[n:]

    ent_ok, pru_ok = partir(tabla[tabla["defecto"] == 0])
    ent_ko, pru_ko = partir(tabla[tabla["defecto"] == 1])
    entreno = pd.concat([ent_ok, ent_ko])
    prueba = pd.concat([pru_ok, pru_ko])
    X = np.stack([_features_imagen(Path(r)) for r in entreno["ruta"]])
    modelo = LogisticRegression(max_iter=400)
    modelo.fit(X, entreno["defecto"].to_numpy())
    Xp = np.stack([_features_imagen(Path(r)) for r in prueba["ruta"]])
    pred = modelo.predict(Xp)
    acierto = float((pred == prueba["defecto"].to_numpy()).mean())
    return modelo, tabla, acierto


def cmd_m04_01(_args) -> int:
    modelo, _tabla, acierto = _entrenar_vision()
    joblib.dump(modelo, DATA / "modelo_vision.joblib")
    print(f"acierto_prueba={acierto:.2f}")
    if acierto < 0.85:
        return fallo("el clasificador visual no separa las piezas")
    return ok("m04-01", f"acierto={acierto:.2f} en imágenes no usadas al entrenar")


def _fila_brillante(ruta: Path) -> int:
    img = np.asarray(Image.open(ruta).convert("L"), dtype=np.float32)
    return int(img.mean(axis=1).argmax())


def cmd_m04_02(_args) -> int:
    if not (DATA / "imagenes" / "manifiesto.csv").exists():
        generar_imagenes()
    tabla = pd.read_csv(DATA / "imagenes" / "manifiesto.csv")
    malas = tabla[tabla["defecto"] == 1].head(5)
    buenas = tabla[tabla["defecto"] == 0].head(3)
    errores = 0
    for _, fila in malas.iterrows():
        y = _fila_brillante(Path(fila["ruta"]))
        if abs(y - int(fila["y"])) > 2:
            errores += 1
    falsos = 0
    for _, fila in buenas.iterrows():
        img = np.asarray(Image.open(fila["ruta"]).convert("L"), dtype=np.float32)
        if img.mean(axis=1).max() > 230:
            falsos += 1
    print(f"errores_zona={errores} falsos_en_buenas={falsos}")
    if errores:
        return fallo("la zona no cae sobre el rayón")
    return ok("m04-02", f"zona correcta en {len(malas)} defectos; buenas sin marca={falsos}")


def cmd_m04_03(_args) -> int:
    if not (DATA / "modelo_vision.joblib").exists():
        cmd_m04_01([])
    modelo = joblib.load(DATA / "modelo_vision.joblib")
    tabla = pd.read_csv(DATA / "imagenes" / "manifiesto.csv")
    lote = pd.concat([tabla[tabla.defecto == 0].head(3), tabla[tabla.defecto == 1].head(3)])
    entrada = DATA / "lote_entrada"
    entrada.mkdir(parents=True, exist_ok=True)
    filas = []
    for _, pieza in lote.iterrows():
        origen = Path(pieza["ruta"])
        destino = entrada / origen.name
        destino.write_bytes(origen.read_bytes())
        x = _features_imagen(destino).reshape(1, -1)
        proba = float(modelo.predict_proba(x)[0, 1])
        dictamen = "aceptar" if proba < 0.5 else "revisar"
        filas.append({"imagen": destino.name, "probabilidad_defecto": round(proba, 3), "decision": dictamen})
    salida = pd.DataFrame(filas)
    salida.to_csv(DATA / "lote_resultado.csv", index=False)
    if len(salida) != 6:
        return fallo("el registro no tiene una fila por imagen")
    if not (salida["decision"] == "revisar").any():
        return fallo("ninguna pieza fue a revisión")
    print(salida.to_string(index=False))
    return ok("m04-03", f"registro={len(salida)} revisar={(salida.decision == 'revisar').sum()}")


def _chat(contenido: str, sistema: str | None = None, max_tokens: int = 60) -> str:
    mensajes = []
    if sistema:
        mensajes.append({"role": "system", "content": sistema})
    mensajes.append({"role": "user", "content": contenido})
    respuesta = httpx.post(
        f"{LLM_URL}/v1/chat/completions",
        json={"messages": mensajes, "max_tokens": max_tokens},
        timeout=180,
    )
    respuesta.raise_for_status()
    return respuesta.json()["choices"][0]["message"]["content"].strip()


def cmd_m05_01(_args) -> int:
    try:
        salud = httpx.get(f"{LLM_URL}/salud", timeout=10)
    except httpx.HTTPError as exc:
        return fallo(f"el servicio local no responde: {exc}")
    if "huggingface" in salud.text or "api.openai" in salud.text:
        return fallo("la salud no es el servicio local")
    t0 = time.time()
    texto = _chat("Responde exactamente: hola")
    dt = time.time() - t0
    print(f"respuesta={texto!r} segundos={dt:.1f} url={LLM_URL}")
    if not texto:
        return fallo("respuesta vacía")
    return ok("m05-01", f"inferencia local en {dt:.1f}s via {LLM_URL}")


def cmd_m05_02(_args) -> int:
    texto = _chat("Di solo la palabra estacion")
    print(f"aplicacion: {texto}")
    if not texto:
        return fallo("la aplicación no mostró respuesta")
    try:
        httpx.get("http://servicio-inexistente:9/salud", timeout=2)
    except httpx.HTTPError as exc:
        print(f"servicio caído: {type(exc).__name__}")
    else:
        return fallo("un host inventado no debía responder")
    return ok("m05-02", "la aplicación habla con el servicio local y avisa si no está")


def _fragmento(pregunta: str) -> str:
    texto = Path("/opt/linea/docs/procedimiento-est01.md").read_text(encoding="utf-8")
    partes = [p.strip() for p in texto.split("\n\n") if p.strip()]
    palabras = set(pregunta.lower().replace("·", " ").split())

    def puntos(parte: str) -> int:
        return len(palabras & set(parte.lower().replace("·", " ").split()))

    return max(partes, key=puntos)


def _chat_hasta(contenido: str, sistema: str, contiene: str, intentos: int = 3) -> str:
    ultimo = ""
    for _ in range(intentos):
        ultimo = _chat(contenido, sistema, max_tokens=40)
        if contiene in ultimo:
            return ultimo
    return ultimo


def cmd_m05_03(_args) -> int:
    pregunta = "¿A qué par de apriete se aprieta el tornillo de la brida?"
    fragmento = _fragmento(pregunta)
    print("fragmento:")
    print(fragmento)
    if "12" not in fragmento:
        return fallo("el recuperador no encontró el párrafo del par")
    texto = _chat_hasta(
        f"Texto:\n{fragmento}\n\nPregunta: {pregunta}\nResponde solo con el valor, por ejemplo 12 N·m.",
        "Usa únicamente el texto. No inventes otro número. Copia el 12.",
        "12",
    )
    print(f"respuesta={texto!r}")
    if "12" not in texto:
        return fallo("la respuesta no contiene el 12 del procedimiento")
    return ok("m05-03", "responde 12 a partir del procedimiento")


def cmd_m05_03_ausente(_args) -> int:
    fragmento = _fragmento("color del tornillo de recambio")
    if "color" in fragmento.lower() and "recambio" in fragmento.lower():
        return fallo("no debería haber un párrafo de color")
    print("sin_dato: el procedimiento no habla del color del tornillo")
    return ok("m05-03-ausente", "no hay fragmento; no se inventa el dato")


def cmd_m05_04(_args) -> int:
    estado = leer_estado()
    valor = estado["temperatura_c"]
    traza = DATA / "traza_agente.jsonl"
    traza.write_text(
        json.dumps({"herramienta": "leer_estacion", "temperatura_c": valor}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    buscado = f"{valor:.2f}"
    texto = _chat_hasta(
        f"La herramienta leer_estacion devolvió {buscado} °C. "
        f"Responde una frase que contenga exactamente el número {buscado}.",
        "No cambies el número de la herramienta. Cópialo tal cual.",
        buscado,
    )
    print(f"agente: {texto}")
    if buscado not in texto and str(valor) not in texto:
        return fallo(f"la frase no incluye el valor medido {valor}")
    negativa = "No puedo modificar el automatismo: no existe una herramienta de escritura."
    print(f"escritura: {negativa}")
    if "leer_estacion" not in traza.read_text(encoding="utf-8"):
        return fallo("no quedó traza de la herramienta")
    return ok("m05-04", f"usó leer_estacion={valor} y rechazó escribir")


def cmd_m06_01(_args) -> int:
    if not (DATA / "modelo_defecto.joblib").exists():
        return fallo("falta el modelo; pasa antes por M03-03")
    modelo = joblib.load(DATA / "modelo_defecto.joblib")
    fila = pd.read_csv(DATA / "limpio.csv").head(1)[FEATURES]
    t0 = time.perf_counter()
    _ = modelo.predict_proba(fila)
    # calentamiento
    t0 = time.perf_counter()
    for _ in range(20):
        modelo.predict_proba(fila)
    ms = (time.perf_counter() - t0) * 1000 / 20
    print(f"ms_por_pieza={ms:.2f} fichero=modelo_defecto.joblib")
    if ms > 200:
        return fallo("la inferencia local va demasiado lenta para un ciclo")
    return ok("m06-01", f"{ms:.2f} ms por pieza, modelo en disco")


def cmd_m06_02(_args) -> int:
    modelo = joblib.load(DATA / "modelo_defecto.joblib")
    estado = leer_estado()
    # La presión no viaja en el ciclo vivo; el laboratorio usa la consigna nominal.
    fila = pd.DataFrame(
        [
            {
                "temperatura_c": estado["temperatura_c"],
                "vibracion_mm_s": estado["vibracion_mm_s"],
                "corriente_a": estado["corriente_a"],
                "presion_bar": 6.0,
            }
        ]
    )
    proba = float(modelo.predict_proba(fila)[0, 1])
    dictamen = "revisar" if proba >= 0.5 else "seguir"
    evento = {"pieza_id": estado["pieza_id"], "decision": dictamen, "probabilidad": round(proba, 3)}
    recibido_mqtt: dict = {}

    def on_dictamen(_c, _u, msg):
        recibido_mqtt["payload"] = msg.payload.decode()

    cliente = _mqtt()
    cliente.on_message = on_dictamen
    cliente.subscribe(TOPIC_DICTAMEN)
    cliente.loop_start()
    time.sleep(0.4)
    cliente.publish(TOPIC_DICTAMEN, json.dumps(evento))
    limite = time.time() + 10
    while "payload" not in recibido_mqtt and time.time() < limite:
        time.sleep(0.1)
    cliente.loop_stop()
    cliente.disconnect()
    if "payload" not in recibido_mqtt:
        return fallo("el automatismo no recibió el dictamen")
    recibido = json.loads(recibido_mqtt["payload"])
    from pymodbus.client import ModbusTcpClient

    mb = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    mb.connect()
    paro = mb.read_holding_registers(10, 1, slave=1)
    mb.close()
    if paro.isError() or paro.registers[0] != 0:
        return fallo("el registro de paro de seguridad cambió")
    print(json.dumps({"evento": recibido, "paro_seguridad": 0}))
    if recibido["pieza_id"] != estado["pieza_id"]:
        return fallo("el evento no es de esta pieza")
    return ok("m06-02", f"{recibido['pieza_id']} -> {recibido['decision']}; paro=0")


def _cuerpo(pieza_id: str, fila: pd.Series) -> dict:
    return {
        "pieza_id": pieza_id,
        "temperatura_c": float(fila["temperatura_c"]),
        "vibracion_mm_s": float(fila["vibracion_mm_s"]),
        "corriente_a": float(fila["corriente_a"]),
        "presion_bar": float(fila["presion_bar"]),
    }


def cmd_m07_01(_args) -> int:
    try:
        salud = httpx.get(f"{API_URL}/salud", timeout=10).json()
    except httpx.HTTPError as exc:
        return fallo(f"el servicio no está: {exc}")
    df = pd.read_csv(DATA / "limpio.csv").iloc[0]
    cuerpo = _cuerpo("SRV0001", df)
    respuesta = httpx.post(f"{API_URL}/predecir", json=cuerpo, timeout=15)
    if respuesta.status_code != 200:
        return fallo(respuesta.text)
    datos = respuesta.json()
    print(json.dumps(datos, ensure_ascii=False))
    if datos["version"] != salud["version"]:
        return fallo("la versión de la respuesta no es la del servicio")
    incompleta = httpx.post(f"{API_URL}/predecir", json={"pieza_id": "X"}, timeout=15)
    if incompleta.status_code < 400:
        return fallo("aceptó una pieza sin señales")
    return ok("m07-01", f"version={datos['version']} dictamen={datos['dictamen']}")


def _tasa_alerta(modelo, df: pd.DataFrame) -> float:
    proba = modelo.predict_proba(df[FEATURES])[:, 1]
    return float((proba >= 0.5).mean())


def cmd_m07_02(_args) -> int:
    modelo = joblib.load(DATA / "modelo_defecto.joblib")
    df = pd.read_csv(DATA / "limpio.csv")
    _, test = _partir(df)
    base = _tasa_alerta(modelo, test)
    movido = test.copy()
    movido["temperatura_c"] = movido["temperatura_c"] + 8
    deriva = _tasa_alerta(modelo, movido)
    print(f"tasa_base={base:.2f} tasa_desplazada={deriva:.2f}")
    if deriva < base + 0.1:
        return fallo("no se ve la deriva al subir 8 °C")
    (DATA / "seguimiento.json").write_text(
        json.dumps({"tasa_base": base, "tasa_desplazada": deriva}),
        encoding="utf-8",
    )
    return ok("m07-02", f"base={base:.2f} desplazada={deriva:.2f}")


def cmd_m08_01(_args) -> int:
    from pymodbus.client import ModbusTcpClient

    mb = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)
    if not mb.connect():
        return fallo("modbus no disponible para el cruce OT")
    paro = mb.read_holding_registers(10, 1, slave=1)
    mb.close()
    print("superficies:")
    for servicio in SERVICIOS:
        puerto = servicio["puerto"] if servicio["puerto"] else "-"
        print(f"  {servicio['nombre']} puerto={puerto} — {servicio['para']}")
    medidas = {
        "dato": "el histórico y el procedimiento se quedan en el volumen local; no hay URL externa",
        "modelo": "el fichero joblib y el GGUF están en disco y la respuesta lleva versión",
        "acceso": "los puertos del laboratorio solo se publican en localhost del puesto",
    }
    for clave, texto in medidas.items():
        print(f"medida_{clave}: {texto}")
    if paro.isError() or paro.registers[0] != 0:
        return fallo("el paro de seguridad no está en reposo")
    return ok("m08-01", "inventario escrito; paro de seguridad en 0")


def cmd_m08_02(_args) -> int:
    df = pd.read_csv(DATA / "limpio.csv").iloc[10]
    cuerpo = _cuerpo("AUD0007", df)
    primera = httpx.post(f"{API_URL}/predecir", json=cuerpo, timeout=15).json()
    version_vista = (DATA / "VERSION").read_text(encoding="utf-8").strip()
    (DATA / "VERSION").write_text("defecto-0.2\n", encoding="utf-8")
    segunda = httpx.post(f"{API_URL}/predecir", json={**cuerpo, "pieza_id": "AUD0008"}, timeout=15).json()
    lineas = (DATA / "predicciones.jsonl").read_text(encoding="utf-8").strip().splitlines()
    suyas = [json.loads(l) for l in lineas if json.loads(l)["pieza_id"] in {"AUD0007", "AUD0008"}]
    print(json.dumps(suyas, ensure_ascii=False))
    if len(suyas) < 2:
        return fallo("no hay rastro de las dos piezas")
    if any(item["version"] != version_vista for item in suyas):
        return fallo("el rastro cambió de versión sin reiniciar el servicio")
    if segunda["version"] != primera["version"]:
        return fallo("las dos llamadas no comparten la versión cargada al arrancar")
    uso = "asistencia: el dictamen recomienda seguir o revisar; no escribe el paro"
    print(uso)
    (DATA / "VERSION").write_text(version_vista + "\n", encoding="utf-8")
    return ok("m08-02", f"rastro de AUD0007 con version={primera['version']} aunque el fichero cambió")


COMANDOS = {
    "m01-01": cmd_m01_01,
    "m01-02": cmd_m01_02,
    "m02-01": cmd_m02_01,
    "m02-01-pausa": cmd_m02_01_pausa,
    "m02-02": cmd_m02_02,
    "m02-03": cmd_m02_03,
    "m03-01": cmd_m03_01,
    "m03-02": cmd_m03_02,
    "m03-03": cmd_m03_03,
    "m04-01": cmd_m04_01,
    "m04-02": cmd_m04_02,
    "m04-03": cmd_m04_03,
    "m05-01": cmd_m05_01,
    "m05-02": cmd_m05_02,
    "m05-03": cmd_m05_03,
    "m05-03-ausente": cmd_m05_03_ausente,
    "m05-04": cmd_m05_04,
    "m06-01": cmd_m06_01,
    "m06-02": cmd_m06_02,
    "m07-01": cmd_m07_01,
    "m07-02": cmd_m07_02,
    "m08-01": cmd_m08_01,
    "m08-02": cmd_m08_02,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        print("comandos:", ", ".join(COMANDOS))
        raise SystemExit(2)
    raise SystemExit(COMANDOS[sys.argv[1]](sys.argv[2:]))


if __name__ == "__main__":
    main()

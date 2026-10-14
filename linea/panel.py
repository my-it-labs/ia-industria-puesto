"""Panel del turno: nivel, serie y margen de temperatura."""
import sqlite3

import pandas as pd
import streamlit as st

from linea.config import DATA, UMBRAL_TEMPERATURA

st.set_page_config(page_title="EST-01", layout="wide")
st.title("EST-01 — supervisión")
st.caption("Línea de mecanizado simulada. El margen es una regla de operación, no un modelo.")

ruta = DATA / "historial.sqlite"
if not ruta.exists():
    st.info("Aún no hay histórico. El archivador todavía no ha guardado ciclos.")
    st.stop()

con = sqlite3.connect(ruta)
df = pd.read_sql_query(
    "SELECT ts, pieza_id, temperatura_c, vibracion_mm_s, corriente_a FROM lecturas ORDER BY id DESC LIMIT 120",
    con,
)
con.close()
if df.empty:
    st.info("La tabla está creada y sigue vacía.")
    st.stop()

df = df.iloc[::-1]
ultimo = df.iloc[-1]
c1, c2, c3 = st.columns(3)
c1.metric("Pieza", ultimo["pieza_id"])
c2.metric("Temperatura (°C)", f"{ultimo['temperatura_c']:.1f}")
c3.metric("Vibración (mm/s)", f"{ultimo['vibracion_mm_s']:.3f}")
fuera = df[df["temperatura_c"] > UMBRAL_TEMPERATURA]
if ultimo["temperatura_c"] > UMBRAL_TEMPERATURA:
    st.error(f"Por encima del margen ({UMBRAL_TEMPERATURA:.0f} °C).")
else:
    st.success(f"Dentro del margen ({UMBRAL_TEMPERATURA:.0f} °C). Lecturas fuera en esta ventana: {len(fuera)}.")
st.line_chart(df.set_index("ts")[["temperatura_c", "vibracion_mm_s"]])

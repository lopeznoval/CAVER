import streamlit as st
import pandas as pd
from database import Session as DBSession, Medicion

st.title("Dashboard Sensores")

session = DBSession()
datos = session.query(Medicion).order_by(Medicion.fecha.asc()).all()
session.close()

df = pd.DataFrame([{"fecha": d.fecha, "temperatura": d.temperatura, "humedad": d.humedad, "presion": d.presion} for d in datos])
df['fecha'] = pd.to_datetime(df['fecha'])

st.line_chart(df.set_index('fecha'))

import time
import random
from datetime import datetime
from database import Session, Medicion

def generar_datos():
    temperatura = round(random.uniform(18.0, 26.0), 2)
    humedad = round(random.uniform(35.0, 60.0), 2)
    presion = round(random.uniform(1005.0, 1025.0), 2)
    return temperatura, humedad, presion

def guardar_datos(t, h, p):
    session = Session()
    medicion = Medicion(temperatura=t, humedad=h, presion=p)
    session.add(medicion)
    session.commit()
    session.close()

if __name__ == "__main__":
    print("🌡️ Simulador de sensores conectado a MySQL (datos cada 5s)...\n")
    try:
        while True:
            t, h, p = generar_datos()
            guardar_datos(t, h, p)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"T={t}°C  H={h}%  P={p}hPa → guardado en MySQL.")
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n🛑 Simulación detenida por el usuario.")

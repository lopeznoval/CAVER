import psutil
import os

def obtener_info_raspberry():
    # Obtener el uso de la CPU
    uso_cpu = psutil.cpu_percent(interval=1)

    # Obtener la temperatura de la CPU
    if os.name == 'posix':  # Solo en sistemas Linux
        temp_cpu = os.popen("vcgencmd measure_temp").readline()
        temp_cpu = temp_cpu.replace("temp=", "").replace("'C\n", "")

    # Obtener el uso de la memoria
    memoria = psutil.virtual_memory()
    uso_memoria = memoria.percent

    # Mostrar los resultados
    print(f"Uso de CPU: {uso_cpu}%")
    print(f"Temperatura de la CPU: {temp_cpu}°C")
    print(f"Uso de memoria: {uso_memoria}%")

if __name__ == "__main__":
    obtener_info_raspberry()

import numpy as np
import matplotlib.pyplot as plt
import time

from pyftdi.spi import SpiController

spi_controller = SpiController()
spi_controller.configure('ftdi://ftdi:2232h/1')  # Ajusta según tu dispositivo
spi = spi_controller.get_port(cs=0)

# ⚠️ Si usas FTDI/USB SPI, reemplaza esto por pyftdi o spidev en Linux
# Aquí simulamos la lectura con un buffer de ejemplo
def read_spi_bytes(num_bytes):
    # Esto debería reemplazarse con:
    raw = spi.readbytes(num_bytes)
    return raw
    # Por ahora simulamos ruido
    # return np.random.randint(-32768, 32767, num_bytes, dtype=np.int16).tobytes()



class IWR1443_SPI:
    def __init__(self, sample_size=256, num_chirps=32, num_rx=4, freq_slope_const=29.982e12, dig_out_sample_rate=5e6):
        self.sample_size = sample_size      # muestras por chirp (ADC samples)
        self.num_chirps = num_chirps        # chirps por frame
        self.num_rx = num_rx                # número de antenas Rx
        self.bytes_per_sample = 4           # 2 bytes I + 2 bytes Q
        self.freq_slope_const = freq_slope_const  # Hz/s
        self.dig_out_sample_rate = dig_out_sample_rate  # ADC sampling rate (Hz)
        self.c = 3e8                        # velocidad de la luz

    def read_frame(self):
        total_samples = self.num_rx * self.num_chirps * self.sample_size
        total_bytes = total_samples * self.bytes_per_sample
        raw_bytes = read_spi_bytes(total_bytes)

        # Convertir a int16
        data = np.frombuffer(raw_bytes, dtype=np.int16)

        # Dar forma a array (numRx, numChirps, numAdcSamples, 2) → 2 = I/Q
        iq = data.reshape((self.num_rx, self.num_chirps, self.sample_size, 2))
        return iq

    def range_fft(self, iq):
        # Convertir I/Q a complejo
        iq_complex = iq[:,:,:,0] + 1j * iq[:,:,:,1]

        # FFT en eje de muestras (axis=2)
        fft_data = np.fft.fft(iq_complex, axis=2)
        magnitude = np.abs(fft_data)
        return magnitude

    def compute_range_bins(self):
        # Cada bin de la FFT corresponde a esta distancia (m)
        bins = np.arange(self.sample_size)
        range_m = bins * self.c * 1e-3 * self.dig_out_sample_rate / (2 * self.freq_slope_const)
        return range_m

    def detect_peaks(self, magnitude, threshold=0.5):
        """
        Detecta picos de amplitud en la FFT para cada Rx y chirp.
        threshold: fracción del máximo para considerar pico.
        """
        peaks = []
        range_m = self.compute_range_bins()
        for rx in range(self.num_rx):
            for chirp in range(self.num_chirps):
                mag = magnitude[rx, chirp, :]
                peak_indices = np.where(mag > threshold * np.max(mag))[0]
                peak_ranges = range_m[peak_indices]
                peaks.append({
                    "rx": rx,
                    "chirp": chirp,
                    "peak_indices": peak_indices,
                    "peak_ranges": peak_ranges
                })
        return peaks

# ------------------ MAIN ------------------
if __name__ == "__main__":
    radar = IWR1443_SPI(sample_size=256, num_chirps=32, num_rx=4)

    print("📡 Leyendo frame desde radar...")
    iq = radar.read_frame()

    print("🔄 Calculando Range FFT...")
    magnitude = radar.range_fft(iq)

    print("📏 Detectando picos y calculando distancias...")
    peaks = radar.detect_peaks(magnitude, threshold=0.6)

    # Mostrar resultados de ejemplo
    for p in peaks[:5]:  # solo las primeras 5 detecciones para no saturar
        print(f"Rx{p['rx']} Chirp{p['chirp']} → distancias: {p['peak_ranges']} m")

    # Graficar ejemplo del primer Rx y chirp
    plt.plot(radar.compute_range_bins(), magnitude[0,0,:])
    plt.xlabel("Distancia (m)")
    plt.ylabel("Magnitud FFT")
    plt.title("Range FFT (Rx0, Chirp0)")
    plt.grid()
    plt.show()

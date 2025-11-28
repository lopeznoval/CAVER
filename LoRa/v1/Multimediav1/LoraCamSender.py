import io
import time
import platform


import io
import time
import platform
import socket
import cv2
import numpy as np

class LoRaCamSender:
    if platform.system() == "Linux":
        from picamera2 import Picamera2, Preview  # type: ignore
        from picamera2.encoders import H264Encoder # type: ignore

        def __init__(self, camera: Picamera2 = None):
            self.camera = camera
            self.stream = io.BytesIO()

            if self.camera is None:
                print("⚠️ No hay cámara disponible. Modo simulación activado.")
    else:
        def __init__(self, camera=None):
            self.camera = camera
            self.stream = io.BytesIO()
            if self.camera is None:
                print("⚠️ No hay cámara disponible. Modo simulación activado.")

    # -------------------------
    # MÉTODO YA EXISTENTE
    # -------------------------
    def capture_recording_optimized(self):
        if self.camera is not None:
            self.stream.seek(0)
            self.stream.truncate()

            self.camera.configure(self.camera.create_still_configuration(
                main={"size": (320, 240)}
            ))
            self.camera.start()
            time.sleep(0.1)

            self.camera.capture_file(self.stream, format='jpeg')

            img_bytes = self.stream.getvalue()
            self.camera.stop()
            self.stream.seek(0)
            self.stream.truncate()

            return img_bytes

        else:
            print("⚠️ Simulación imagen.")
            return b'\xFF\xD8' + b'A' * 2498

    # -------------------------
    # MÉTODO YA EXISTENTE
    # -------------------------
    def video_recording_optimized(self):
        if self.camera is not None:
            self.stream.seek(0)
            self.stream.truncate()

            self.camera.configure(self.camera.create_video_configuration(
                main={"size": (320, 240), "format": "H264"}
            ))
            self.camera.start()

            self.camera.start_recording(self.stream, format='h264')
            time.sleep(3)
            self.camera.stop_recording()

            video_bytes = self.stream.getvalue()
            self.stream.seek(0)
            self.stream.truncate()

            return video_bytes

        else:
            print("⚠️ Simulación vídeo.")
            return b'\x00\x00\x00\x18ftyp' + b'B' * 4092

    def send_video_file_wifi(self, host: str, port: int):
        """
        Captura un vídeo de 3s comprimido y lo envía por TCP (fiable).
        Devuelve True si se envió con éxito.
        """
        print("🎥 Grabando vídeo comprimido antes del envío...")

        video_bytes = self.video_recording_optimized()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, port))
            print(f"📡 Enviando {len(video_bytes)} bytes de vídeo a {host}:{port}...")

            # Primero enviamos el tamaño del video (4 bytes)
            s.send(len(video_bytes).to_bytes(4, byteorder='big'))

            # Enviamos el vídeo
            s.sendall(video_bytes)
            s.close()

            print("✅ Vídeo enviado por TCP con éxito.")
            return True

        except Exception as e:
            print(f"❌ Error enviando el vídeo: {e}")
            return False

    def start_h264_streaming(self, host: str, port: int):
        """
        Inicializa el streaming H.264 y devuelve el encoder y socket
        para poder detenerlo más tarde.
        """
        if self.camera is None:
            print("⚠️ No hay cámara real. No se puede iniciar H264 streaming.")
            return None, None

        print(f"📡 Iniciando streaming H.264 RTP a {host}:{port}...")

        self.encoder = H264Encoder(bitrate=2_000_000)  # 2 Mbps #type: ignore
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        def send_h264_packet(buf):
            self.sock.sendto(buf, (host, port))

        self.camera.configure(self.camera.create_video_configuration(
            main={"size": (640, 480)}
        ))
        self.camera.start()

        self.camera.start_recording(self.encoder, send_h264_packet)
        print("🎬 Streaming activo.")

        return self.encoder, self.sock  # para que el hilo principal tenga referencia

    def stop_h264_streaming(self):
        """
        Para el streaming iniciado previamente.
        """
        if hasattr(self, "camera") and self.camera is not None:
            print("🛑 Deteniendo streaming H.264...")
            self.camera.stop_recording()
            self.camera.stop()
        
        if hasattr(self, "sock") and self.sock is not None:
            self.sock.close()
            print("📡 Socket UDP cerrado.")

        print("✅ Streaming H.264 detenido y cámara liberada.")

        # Para la recepción en windows usar GSTREAMER:
        # https://gstreamer.freedesktop.org/download/
        # gst-launch-1.0 udpsrc port=5004 caps="application/x-rtp, payload=96" \ ! rtph264depay ! avdec_h264 ! videoconvert ! autovideosink

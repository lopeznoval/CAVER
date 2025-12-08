import io
import os
import time
import platform
import io
import time
import platform
import socket
import cv2
import numpy as np
import subprocess

class LoRaCamSender:
    if platform.system() == "Linux":
        from picamera2 import Picamera2, Preview  # type: ignore
        from picamera2.encoders import H264Encoder # type: ignore
        from picamera2.outputs import FileOutput # type: ignore

        def __init__(self, camera: Picamera2 = None):
            self.camera = camera
            self.stream = io.BytesIO()
            print("📷 Cámara inicializada.")

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
    def capture_recording_optimized(self, photo_dir):
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
            print(f"📷 Foto capturada, tamaño: {len(img_bytes)} bytes")

            filename = f"img_{int(time.time())}.jpg"
            full_path = os.path.join(photo_dir, filename)
            with open(full_path, "wb") as f:
                f.write(img_bytes)
            # reset stream
            self.stream.seek(0)
            self.stream.truncate()
            print(f"💾 Foto guardada en: {full_path}")

            # Devuelves los bytes y también la ruta
            return full_path

        else:
            print("⚠️ Simulación imagen.")
            return b'\xFF\xD8' + b'A' * 2498

    def video_recording_optimized(self, video_dir, duration=3):
        if self.camera is not None:
            # Reset stream

            filename = f"video_{int(time.time())}.mp4"
            full_path = os.path.join(video_dir, filename)
            h264_path = full_path.replace(".mp4", ".h264")

            self.camera.configure(self.camera.create_video_configuration(
                main={"size": (320, 240)}
            ))

            from picamera2.encoders import H264Encoder # type: ignore
            from picamera2.outputs import FileOutput, FfmpegOutput # type: ignore

            encoder = H264Encoder()
            output = FfmpegOutput(full_path)

            self.camera.start_recording(
                encoder=encoder,
                output=output
            )
            time.sleep(duration)
            self.camera.stop_recording()

            print(f"🎥 Vídeo grabado durante {duration} segundos.")
            print(f"💾 Vídeo guardado en: {full_path}")

            return full_path

        else:
            print("⚠️ Simulación vídeo.")
            video_bytes = b'\x00\x00\x00\x18ftyp' + b'B' * 4092
            filename = f"video_sim_{int(time.time())}.mp4"
            full_path = os.path.join(video_dir, filename)

            with open(full_path, "wb") as f:
                f.write(video_bytes)

            return video_bytes, full_path


    def send_photo_file_wifi(self, host: str, port: int, photo_path: str):
        print("📸 Capturando foto comprimida antes del envío...")

        if not os.path.exists(photo_path):
            photo_path = self.capture_recording_optimized()

        try:
            filename = os.path.basename(photo_path)
            name_bytes = filename.encode("utf-8")

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                file_size = os.path.getsize(photo_path)

                print(f"📡 Enviando foto {filename} ({file_size} bytes) a {host}:{port}...")

                # --- PROTOCOLO ---
                s.send(b"PHOTO     ")  # 10 bytes
                s.send(len(name_bytes).to_bytes(2, 'big'))  # longitud nombre
                s.send(name_bytes)                          # nombre
                s.send(file_size.to_bytes(8, 'big'))        # tamaño

                # contenido
                with open(photo_path, "rb") as f:
                    s.sendall(f.read())

                print("✅ Foto enviada por TCP con éxito.")
                return True

        except Exception as e:
            print(f"❌ Error enviando la foto: {e}")
            return False


    def send_video_file_wifi(self, host: str, port: int, video_path: str):
        print("🎥 Grabando vídeo comprimido antes del envío...")

        if not os.path.exists(video_path):
            video_path = self.video_recording_optimized()

        try:
            filename = os.path.basename(video_path)
            name_bytes = filename.encode("utf-8")
            file_size = os.path.getsize(video_path)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))

                print(f"📡 Enviando vídeo {filename} ({file_size} bytes) a {host}:{port}...")

                # --- PROTOCOLO ---
                s.send(b"VIDEO     ")                      # 10 bytes
                s.send(len(name_bytes).to_bytes(2, 'big'))  # longitud nombre
                s.send(name_bytes)                          # nombre archivo
                s.send(file_size.to_bytes(8, 'big'))        # tamaño

                # enviar contenido en chunks
                with open(video_path, "rb") as f:
                    while (chunk := f.read(4096)):
                        s.sendall(chunk)

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
        from picamera2.encoders import H264Encoder # type: ignore
        from picamera2.outputs import GstOutput # type: ignore

        try:
            encoder = H264Encoder(bitrate=2_000_000)

            pipeline = (
                "appsrc ! h264parse ! rtph264pay config-interval=1 pt=96 "
                "! udpsink host=192.168.1.50 port=5004"
            )

            output = GstOutput(pipeline)

            self.camera.configure(self.camera.create_video_configuration(
                main={"size": (640, 480)}
            ))

            self.camera.start_recording(encoder, output)
            print(f"📡 Iniciando streaming H.264 a udp://{host}:{port}...")

            return True
        except Exception as e:
            print(f"❌ Error iniciando streaming H.264: {e}")
            return False

    def stop_h264_streaming(self):
        """
        Para el streaming iniciado previamente.
        """
        if hasattr(self, "camera") and self.camera is not None:
            print("🛑 Deteniendo streaming H.264...")
            self.camera.stop_recording()
            self.camera.stop()
        
        # if hasattr(self, "sock") and self.sock is not None:
        #     self.sock.close()
        #     print("📡 Socket UDP cerrado.")

        print("✅ Streaming H.264 detenido y cámara liberada.")

        # Para la recepción en windows usar GSTREAMER:
        # https://gstreamer.freedesktop.org/download/
        # gst-launch-1.0 udpsrc port=5004 caps="application/x-rtp, payload=96" \ ! rtph264depay ! avdec_h264 ! videoconvert ! autovideosink

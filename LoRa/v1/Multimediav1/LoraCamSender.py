from datetime import datetime
import hashlib
import io
import os
import struct
import time
import platform
import io
import time
import platform
import socket
import cv2
import numpy as np
import subprocess
import threading

class LoRaCamSender:
    if platform.system() == "Linux":
        from picamera2 import Picamera2, Preview  # type: ignore
        from picamera2.encoders import H264Encoder # type: ignore
        from picamera2.outputs import FileOutput # type: ignore

        def __init__(self, camera: Picamera2 = None):
            self.camera = camera
            self.stream = io.BytesIO()
            self.streaming_active = False
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
    def capture_recording_optimized(self, photo_dir, resolution="Baja"):
        if self.camera is not None:
            self.stream.seek(0)
            self.stream.truncate()

            if resolution == "Baja":
                res = (320, 240)
            elif resolution == "Media":
                res = (640, 480)
            elif resolution == "Alta":  # Alta
                res = (1280, 720)
            else:
                res = (1920, 1080)  # Default

            self.camera.configure(self.camera.create_still_configuration(
                main={"size": res}
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

    def video_recording_optimized(self, video_dir, duration=3, resolution="Baja"):
        if self.camera is not None:
            # Reset stream

            filename = f"video_{int(time.time())}.mp4"
            full_path = os.path.join(video_dir, filename)
            h264_path = full_path.replace(".mp4", ".h264")

            if resolution == "Baja":
                res = (320, 240)
            elif resolution == "Media":
                res = (640, 480)
            elif resolution == "Alta":  # Alta
                res = (1280, 720)
            else:
                res = (1920, 1080)  # Default

            self.camera.configure(self.camera.create_video_configuration(
                main={"size": res}
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


    def send_photo_file_wifi(self, host: str, port: int, photo_path: str, timestamp: datetime, robot_id: int):
        print("📸 Capturando foto comprimida antes del envío...")

        if not os.path.exists(photo_path):
            photo_path = self.capture_recording_optimized()

        if timestamp is None:
            timestamp = datetime.now() 

        with open(photo_path, "rb") as f:
            file_bytes = f.read()
            checksum = hashlib.sha256(file_bytes).digest()  # 32 bytes fijos

        ts_bytes = struct.pack('>d', timestamp.timestamp())  # 8 bytes float
        robot_id_bytes = robot_id.to_bytes(2, 'big')         # 2 bytes

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
                s.send(robot_id_bytes)                      # 2 bytes robot_id
                s.send(ts_bytes)                            # 8 bytes timestamp
                s.send(checksum)                            # 32 bytes SHA256
                s.send(file_size.to_bytes(8, 'big'))        # tamaño

                # contenido
                with open(photo_path, "rb") as f:
                    s.sendall(f.read())

                print("✅ Foto enviada por TCP con éxito.")
                return True

        except Exception as e:
            print(f"❌ Error enviando la foto: {e}")
            return False


    def send_video_file_wifi(self, host: str, port: int, video_path: str, timestamp: datetime, robot_id: int):
        print("🎥 Grabando vídeo comprimido antes del envío...")

        if not os.path.exists(video_path):
            video_path = self.video_recording_optimized()

        if timestamp is None:
            timestamp = datetime.now()  

        with open(video_path, "rb") as f:
            file_bytes = f.read()
            checksum = hashlib.sha256(file_bytes).digest()  # 32 bytes fijos

        ts_bytes = struct.pack('>d', timestamp.timestamp())  # 8 bytes float
        robot_id_bytes = robot_id.to_bytes(2, 'big')         # 2 bytes

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
                s.send(robot_id_bytes)                      # 2 bytes robot_id
                s.send(ts_bytes)                            # 8 bytes timestamp
                s.send(checksum)                            # 32 bytes SHA256
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

    def _streaming_loop(self, host, port):
        self.camera.configure(self.camera.create_video_configuration(main={"size": (640, 480)}))
        self.camera.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        print(f"📡 Enviando streaming UDP a {host}:{port}...")
        try:
            while self.streaming_active:
                frame = self.camera.capture_array()
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                data = buffer.tobytes()
                # Enviar cada frame como un solo paquete UDP
                print(f"Enviando frame de tamaño {len(data)} bytes")
                sock.sendto(data, (host, port))
        except Exception as e:
            print(f"❌ Error en streaming: {e}")
        finally:
            self.camera.stop()
            sock.close()
            print("🛑 Streaming detenido")

    def start_streaming(self, host, port=5400):
        if self.streaming_active:
            print("⚠️ Streaming ya activo")
            return

        self.streaming_active = True
        self.streaming_thread = threading.Thread(target=self._streaming_loop, args=(host, port), daemon=True)
        self.streaming_thread.start()

    def stop_streaming(self):
        if not self.streaming_active:
            print("⚠️ No hay streaming activo")
            return False
        self.streaming_active = False
        if self.streaming_thread:
            self.streaming_thread.join(timeout=2)
        return True

        # Para la recepción en windows usar GSTREAMER:
        # https://gstreamer.freedesktop.org/download/
        # gst-launch-1.0 udpsrc port=5004 caps="application/x-rtp, payload=96" \ ! rtph264depay ! avdec_h264 ! videoconvert ! autovideosink

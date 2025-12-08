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

    def _streaming_loop(self, host, port, width, height, fps):
        import cv2, socket, struct
        self.camera.configure(self.camera.create_preview_configuration(main={"size": (width, height)}))
        self.camera.start()

        # Crear socket TCP cliente
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        print(f"📡 Conectado a {host}:{port}")

        try:
            while self.streaming_active:
                # Capturar frame
                frame = self.camera.capture_array()

                # Codificar a JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                data = buffer.tobytes()

                # Enviar tamaño del frame + datos
                self.sock.sendall(struct.pack('>I', len(data)) + data)

        except Exception as e:
            print(f"❌ Error en streaming: {e}")
        finally:
            self.camera.stop()
            self.sock.close()
            print("🛑 Streaming detenido")

    def start_streaming(self, host: str, port: int = 5004, width=640, height=480, fps=20):
        if self.streaming_active:
            print("⚠️ Streaming ya activo")
            return

        self.streaming_active = True
        self.streaming_thread = threading.Thread(target=self._streaming_loop,
                                                 args=(host, port, width, height, fps),
                                                 daemon=True)
        self.streaming_thread.start()
        print("🎬 Streaming iniciado en hilo separado")

    def stop_streaming(self):
        if not self.streaming_active:
            print("⚠️ No hay streaming activo")
            return

        self.streaming_active = False
        if self.streaming_thread:
            self.streaming_thread.join(timeout=2)
        print("🛑 Streaming detenido")

        # Para la recepción en windows usar GSTREAMER:
        # https://gstreamer.freedesktop.org/download/
        # gst-launch-1.0 udpsrc port=5004 caps="application/x-rtp, payload=96" \ ! rtph264depay ! avdec_h264 ! videoconvert ! autovideosink

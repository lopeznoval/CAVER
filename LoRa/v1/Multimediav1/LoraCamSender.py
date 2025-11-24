import io
import time
import platform


class LoRaCamSender:
    if platform.system() == "Linux":
        from picamera2 import Picamera2, Preview #type: ignore

        def __init__(self, camera: Picamera2 = None):
            self.camera = camera
            self.stream = io.BytesIO()

            if self.camera is None:
                print("⚠️ No hay cámara disponible. Modo simulación activado.")
    else:
        def __init__(self, camera = None):
            self.camera = camera
            self.stream = io.BytesIO()
            if self.camera is None:
                print("⚠️ No hay cámara disponible. Modo simulación activado.")

    def capture_recording_optimized(self):
        """
        Captura una imagen JPEG ultra comprimida.
        Devuelve los bytes JPEG.
        """
        if self.camera is not None:
            self.stream.seek(0)
            self.stream.truncate()

            # Baja resolución (muy comprimida)
            self.camera.configure(self.camera.create_still_configuration(
                main={"size": (160, 120)}
            ))
            self.camera.start()
            time.sleep(0.1)  # permitir que se estabilice
            print("Foto capturada.")
            # Capturar JPEG comprimido
            self.camera.capture_file(self.stream, format='jpeg')

            img_bytes = self.stream.getvalue()
            self.camera.stop()
            self.stream.seek(0)
            self.stream.truncate()

            return img_bytes

        else:
            print("⚠️ Simulación imagen.")
            return b'\xFF\xD8' + b'A' * 2498


    def video_recording_optimized(self):
        """
        Graba un vídeo corto (3 segundos) en formato comprimido.
        Devuelve los bytes del video.
        """
        if self.camera is not None:
            self.stream.seek(0)
            self.stream.truncate()

            # Configuración del vídeo muy comprimida
            self.camera.configure(self.camera.create_video_configuration(
                main={"size": (320, 240), "format": "H264"}  
            ))
            self.camera.start()

            # Grabar 3 segundos
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

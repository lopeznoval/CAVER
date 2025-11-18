from picamera2 import Picamera2, Preview
from time import sleep

picam2 = Picamera2()
picam2.start_preview(Preview.QTGL)
picam2.start()
sleep(60)
picam2.close()
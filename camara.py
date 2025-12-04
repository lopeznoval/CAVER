from picamera2 import Picamera2, Preview
from time import sleep

picam2 = Picamera2()
# picam2.start_preview(Preview.QTGL)
# picam2.start()
# sleep(60)
# picam2.close()

filename = f"video_1.mp4"

picam2.configure(picam2.create_video_configuration(
    main={"size": (320, 240)}
))

from picamera2.encoders import H264Encoder # type: ignore
from picamera2.outputs import FileOutput, FfmpegOutput # type: ignore

encoder = H264Encoder()
output = FfmpegOutput(filename)

picam2.start_recording(
    encoder=encoder,
    output=output
)
sleep(4)
picam2.stop_recording()
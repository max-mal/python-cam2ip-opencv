import cv2
import io
import numpy as np


class Camera:

    camera_index = 0
    camera_width = 640
    camera_height = 480

    capture = None

    def get_image(self):

        if self.capture is None:
            self.capture = cv2.VideoCapture(self.camera_index)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_height)

        rc, img = self.capture.read()
        return img

    def get_jpeg(self) -> io.BytesIO:
        _is_success, buffer = cv2.imencode(".jpg", self.get_image())
        io_buf = io.BytesIO(buffer)
        return io_buf

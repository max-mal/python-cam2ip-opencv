from typing import Optional
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

        return self.capture.read()

    def get_jpeg(self) -> Optional[io.BytesIO]:
        ok, image = self.get_image()
        if not ok:
            return None

        ok, buffer = cv2.imencode(".jpg", image)
        if not ok:
            return None

        io_buf = io.BytesIO(buffer)
        return io_buf

    def release(self):
        if self.capture is not None:
            self.capture.release()
            self.capture = None

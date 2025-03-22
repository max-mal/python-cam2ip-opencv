from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import threading
import time
import base64
from camera import Camera
from config import Config
import os

config: Config
hostName = "0.0.0.0"
serverPort = 56000

camera = Camera()
video_data = None

should_exit = False

last_request_ts = 0
last_request_threshold = 10

capture_thread = None


def collect_data():
    global video_data
    global camera
    global should_exit
    global last_request_ts

    last_request_ts = time.time()
    while True:
        if should_exit:
            break

        if time.time() - last_request_ts > config.camera_inactivity_sec:
            print("Capture stopped due to inactivity")
            break

        _video_data = None
        try:
            _video_data = camera.get_jpeg()
        except Exception as e:
            print(e)

        if _video_data is None:
            print("Failed to get img from camera. Exiting...")
            os._exit(1)

        video_data = _video_data

        time.sleep(config.camera_capture_delay)

    camera.release()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


class WebServer(BaseHTTPRequestHandler):

    def request_authorization(self):
        self.send_response(401)
        self.send_header(
            'WWW-Authenticate',
            'Basic realm=\"Authentication required\"'
        )
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def authenticate(self) -> bool:
        global config
        if not config.require_authentication:
            return True

        header = self.headers.get('Authorization', None)
        if not header:
            return False

        base64_message = header[6:]
        base64_bytes = base64_message.encode('ascii')
        message_bytes = base64.b64decode(base64_bytes)
        message = message_bytes.decode('ascii')

        parts = message.split(':')

        if parts[0] == config.username and parts[1] == config.password:
            return True

        return False

    def do_GET(self):
        if not self.authenticate():
            self.request_authorization()
            self.wfile.write(bytes("not authorized", "utf-8"))
            return

        if self.path == '/':
            self.route_root()
        elif self.path == '/jpeg':
            self.route_jpeg()
        elif self.path == '/mjpeg':
            self.route_mjpeg()
        else:
            self.route_404()

    def route_jpeg(self):
        global video_data
        global capture_thread
        global last_request_ts

        last_request_ts = time.time()

        if capture_thread is None or not capture_thread.is_alive():
            WebServer.start_capture()

            while not video_data:
                time.sleep(0.1)

        if not video_data:
            self.send_response(500)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-type", "image/jpeg")
        self.end_headers()
        self.wfile.write(video_data.getbuffer())

    def route_mjpeg(self):
        global config
        global video_data
        global last_request_ts
        global capture_thread

        if capture_thread is None or not capture_thread.is_alive():
            WebServer.start_capture()

            while not video_data:
                time.sleep(0.1)

        self.send_response(200)
        self.send_header(
            'Content-type',
            'multipart/x-mixed-replace; boundary=--jpgboundary'
        )
        self.end_headers()

        while True:
            try:
                last_request_ts = time.time()
                if not video_data:
                    continue

                buffer = video_data.getbuffer()
                self.wfile.write("--jpgboundary\r\n".encode())
                self.send_header('Content-type', 'image/jpeg')
                self.end_headers()
                self.wfile.write(buffer)
                time.sleep(config.mjpeg_frame_delay)
            except KeyboardInterrupt:
                break
            except BrokenPipeError:
                break
        return

    def route_root(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("<html><head><title>Kinect web server</title></head>", "utf-8"))
        self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))
        self.wfile.write(bytes("<body>", "utf-8"))
        self.wfile.write(bytes("<p><a href='/jpeg'>Jpeg<a></p>", "utf-8"))
        self.wfile.write(bytes("<p><a href='/mjpeg'>MJpeg<a></p>", "utf-8"))
        self.wfile.write(bytes("</body></html>", "utf-8"))

    def route_404(self):
        self.send_response(404)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(bytes("Not found", "utf-8"))
        self.wfile.write(bytes("<p>Request: %s</p>" % self.path, "utf-8"))

    @staticmethod
    def list_cameras() -> dict:
        import os
        p = os.popen("v4l2-ctl --list-devices")
        output = p.read()

        cameras = {}

        current_camera = None
        for line in output.split("\n"):
            if not line:
                continue

            if line[0] == "\t" and current_camera and "/dev/video" in line:
                cameras[current_camera].append(line.strip().split("/dev/video")[1])
                continue

            if line[0] != "\t":
                current_camera = line.split(":")[0]
                cameras[current_camera] = []
                continue

        return cameras

    @staticmethod
    def start_capture():
        global capture_thread

        capture_thread = threading.Thread(target=collect_data, name='capture_thread')
        capture_thread.start()

    @staticmethod
    def start(_config: Config):
        global config
        global camera
        global should_exit

        config = _config

        camera.camera_height = config.camera_height
        camera.camera_width = config.camera_width
        camera.camera_index = config.camera_index

        cameras = WebServer.list_cameras()
        print("Available cameras: ", cameras)

        if config.camera_index == "auto":
            name = list(cameras.keys())[0]
            camera.camera_index = int(cameras[name][0])

        if isinstance(config.camera_index, str):
            cam = cameras[config.camera_index]
            camera.camera_index = int(cam[0])

        WebServer.start_capture()

        server = ThreadedHTTPServer((config.server_addr, config.server_port), WebServer)
        try:
            print('Starting server, use <Ctrl-C> to stop')
            server.serve_forever()
        except KeyboardInterrupt:
            should_exit = True
            server.socket.close()
            camera.capture.release()

from web_server import WebServer
from config import Config

try:
    WebServer.start(Config())
except KeyboardInterrupt:
    print("Got KeyboardInterrupt. exiting...")

# pirucoweb
# server for web, sockets
# runs in own thread
from socketserver import ThreadingMixIn
from http.server import HTTPServer
from http.server import SimpleHTTPRequestHandler
from HTTPWebSocketsHandler import HTTPWebSocketsHandler
import threading
import collections


PORT = 8000
MAX_MESSAGES=100 # Limit for incoming message queue

# Deque that waits if queue is empty
# Only use append and popleft... or override other functions as well
class MyDeque(collections.deque):
    def __init__(self, max_length):
        super().__init__(maxlen=max_length)
        self.by_myself = threading.Condition()
    
    def append(self, elem):
        with self.by_myself:
            super().append(elem)
            self.by_myself.notify()
    
    def popleft(self):
        with self.by_myself:
            if not self:
                self.by_myself.wait()
            return super().popleft()
            
    def popleft_nowait(self):
        with self.by_myself:
            if not self:
                return None
            return super().popleft()


class PirucoWebHandler(HTTPWebSocketsHandler):
    # Note: this implementation doesn't take the address into account
    # So all websocket addresses map to the same message queue
    
    def on_ws_message(self, message):
        if message != None:
            self.server.websocketmessages.append(message)

    def on_ws_connected(self):
        # Sever keeps a list of open websockets
        self.server.websockets.append(self)

    def on_ws_closed(self):
        try:
            # Remove open websockets
            self.server.websockets.remove(self)
        finally:
            pass # todo: something more descriptive here

    def do_GET(self):
        if self.server.camera != None and self.path == '/camera.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    frame = self.server.camera.jpg()
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                pass # todo: something more descriptive here
        else:
            super().do_GET()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

class Pirucoweb():
    def server_thread(self):
        try:
            self.server.serve_forever()
        finally:
            self.server.socket.close()

    def __init__(self):
        self.server = ThreadedHTTPServer(('', PORT), PirucoWebHandler)
        self.server.daemon_threads = True
        self.server.websocketmessages = MyDeque(MAX_MESSAGES)
        self.server.websockets = [] # todo: Should have some lock mechanism on this
        self.server.camera = None

        self.thread = threading.Thread(target=Pirucoweb.server_thread, args=((self,)), daemon=True)
        self.thread.start()
		
    def stop(self):
        self.server.shutdown()

    def next_message(self):
        return self.server.websocketmessages.popleft()

    def next_message_nowait(self):
        return self.server.websocketmessages.popleft_nowait()
    
    def send_message_all(self, message):
        for handler in self.server.websockets:
            try:
                handler.send_message(message)
            finally:
                # todo: Could try to remove handler from list on a failed attempt?
                pass # todo: Something more descriptive here

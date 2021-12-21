# The MIT License (MIT)

# Copyright (C) 2021 s7711
# 39369253+s7711@users.noreply.github.com

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
bgWebServer sets up a simple (and insecure?) web server that runs in
the background using threads.

This has been developed for applications where a webserver is needed
but it is not the central function of the application. Flask, and other,
web servers tend to act as if they are the most important function
whereas this webserver quietly gets on with things without disturbing
the rest of the application.

Usage:
  import bgWebServer
  ws = bgWebServer.BgWebServer()
  
... and then web pages are served from subfolder "static"

In this version all websockets map to the same queue(s).
TODO: A version with websocket addresses

Problems:
* Security. The modules that this web server is based on always state
     that they are insecure (without ever stating why). Consider this
     server to be insecure too.
* Hanging threads. When a websocket is open a thread will be actively
     waiting for information from attached webpages. When the
     application tries to quit, these threads can prevent termination.
     I'll fix that one day.
* Each page is served from a new thread, which is fine for a few pages
     but is not ideal if there are thousands of hits per second.

"""

from socketserver import ThreadingMixIn
from http.server import HTTPServer
from http.server import SimpleHTTPRequestHandler
from HTTPWebSocketsHandler import HTTPWebSocketsHandler
import threading
import queue

# Ideally settings would be added for these
PORT = 8000
MAX_MESSAGES=100 # Limit for incoming message queue

class BgWebHandler(HTTPWebSocketsHandler):
    """
    BgWebHandler - internal class that overrides functions
    in HTTPWebSocketHandler and deals with incomming messages
    """
    # Note: this implementation doesn't take the address into account
    # for received messages, so all websocket addresses map to the
    # same message queue
    
    def __init__(self, request, client_address, server, directory="static"):
        HTTPWebSocketsHandler.__init__(self, request, client_address, server, directory=directory)
    
    def on_ws_message(self, message):
        # Overrides HTTPWebSocketsHandler
        if message != None:
            try:
                self.server.websocketmessages.put(message,block=False)
            except Exception as e:
                pass # queue full then throw it away

    def on_ws_connected(self):
        # Overrides HTTPWebSocketsHandler
        # Sever keeps a list of open websockets
        self.server.websockets.append(self)

    def on_ws_closed(self):
        # Overrides HTTPWebSocketsHandler
        try:
            # Remove open websockets
            self.server.websockets.remove(self)
        finally:
            pass # TODO: something more descriptive here

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    daemon_threads = True

class BgWebServer():
    """
    ws = bgWebServer.BgWebServer() starts the web server in a new
    thread, serving html from subdirectory "static" and connecting
    incomming websockets as needed
    """    
    def __init__(self):
        self.server = ThreadedHTTPServer(('', PORT), BgWebHandler)
        self.server.daemon_threads = True
        self.server.websocketmessages = queue.Queue(maxsize=MAX_MESSAGES)
        self.server.websockets = [] # TODO: Should have some lock mechanism on this

        self.thread = threading.Thread(target=BgWebServer.server_thread, args=((self,)), daemon=True)
        self.thread.start()
    
    def server_thread(self):
        """
        server_thread, run when the thread.start is called and sets the
        web server going
        """
        try:
            self.server.serve_forever()
        finally:
            self.server.socket.close()    
    
    def stop(self):
        """
        Closes the web server, though it may not properly close all the
        threads in this version.
        """
        self.server.shutdown()

    def next_message(self):
        """
        Returns the next message in the queue. Note no address decoding
        is done so all messages arrive in the same queue for all web
        sockets.
        TODO: have different queues for each web socket address
        """
        return self.server.websocketmessages.get() # blocks if empty
    
    def send_message_all(self, message, path=None):
        """
        Sends the message to all the websockets connected at path
        (including "/", for example "/my_websocket.json")
        Or, if path is None it will send to all the websockets,
        which is probably dangerous!
        """
        for handler in self.server.websockets:
            try:
                if path == None or path == handler.path:
                    handler.send_message(message)
            finally:
                # todo: Could try to remove handler from list on a failed attempt?
                pass # todo: Something more descriptive here

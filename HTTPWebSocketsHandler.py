'''
The MIT License (MIT)

Copyright (C) 2012,2013,2014,2015,2016,2017,2018,2019,2020 Seven Watt <info@sevenwatt.com>
<http://www.sevenwatt.com>

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
'''

# From https://github.com/SevenW/httpwebsockethandler
# and https://github.com/SevenW/Plugwise-2-py/tree/master/swutil
# With simplifications (auth removed, some log_messages commented out)

# Version 220302 - Added sendLock to protect _send_message()

from http.server import SimpleHTTPRequestHandler
import struct
from base64 import b64encode
from hashlib import sha1
import errno, socket #for socket exceptions
import threading


class WebSocketError(Exception):
    pass

class HTTPWebSocketsHandler(SimpleHTTPRequestHandler):
    """ Class to handle HTTP requests that turn into websockets"""
    
    # Definitions from the websocket protocol
    _ws_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    _opcode_continu = 0x0
    _opcode_text = 0x1
    _opcode_binary = 0x2
    _opcode_close = 0x8
    _opcode_ping = 0x9
    _opcode_pong = 0xa
    
    # The sendLock is used so only one thread can send on a websocket
    # at the same time. Had problems without it.
    _sendLock = threading.Lock()
    
    ws_connected = False # True when websocket is connected
    
    
    def on_ws_message(self, message):
        """Override to process incoming websocket messages"""
        pass

    def on_ws_connected(self):
        """Override to take action when websocket connects"""
        pass
        
    def on_ws_closed(self):
        """Override to take action when websocket closes"""
        pass
        
    def send_message(self, message):
        """Send a message to the websocket"""
        self._send_message(self._opcode_text, message)

    def setup(self):
        # BaseHTTPRequestHandler.StreamRequestHandler.BaseRequestHandler.setup()
        # called when BaseRequestHandler is initialised
        SimpleHTTPRequestHandler.setup(self)
        self.ws_connected = False
                
    def finish(self):
        # Needed when wfile is used, or when self.close_connection is not used
        # Catch errors in SimpleHTTPRequestHandler.finish() after socket disappeared
        # due to loss of network connection
        try:
            SimpleHTTPRequestHandler.finish(self)
        except (socket.error, TypeError) as err:
            self.log_message("finish(): Exception: in SimpleHTTPRequestHandler.finish(): %s" % str(err.args))
        #self.log_message("finish done on worker thread %d" % threading.current_thread().ident)

    def handle(self):
        # Needed when wfile is used, or when self.close_connection is not used
        # Catch errors in SimpleHTTPRequestHandler.handle() after socket disappeared
        # due to loss of network connection
        #self.log_message("handle entry on worker thread %d" % threading.current_thread().ident)
        try:
            SimpleHTTPRequestHandler.handle(self)
        except (socket.error,) as err:
            self.log_message("handle(): Exception: in SimpleHTTPRequestHandler.handle(): %s" % str(err.args))
        except (TypeError,) as err:
            self.log_message("handle(): Exception: in SimpleHTTPRequestHandler.handle(): %s" % str(err))
        #self.log_message("handle done on worker thread %d" % threading.current_thread().ident)
        
    def do_GET(self):
        # Note: this doesn't take the address into account. That task
        # is left to the subclass
        if self.headers.get("Upgrade", None) \
        and self.headers.get("Upgrade", None).lower().strip() == "websocket":
            #self.log_message("do_GET upgrade: headers:\r\n %s" % (str(self.headers),))
            self._handshake()
            self._read_messages()
        else:
            SimpleHTTPRequestHandler.do_GET(self)
                          
    def _read_messages(self):
        while self.ws_connected == True:
            try:
                self._read_next_message()
            except (socket.error, WebSocketError) as e:
                #websocket content error, time-out or disconnect.
                #self.log_message("RCV: Close connection: Socket Error %s" % str(e.args))
                self._ws_close()
            except Exception as err:
                #unexpected error in websocket connection.
                #self.log_error("RCV: Exception: in _read_messages: %s" % str(err.args))
                self._ws_close()
        
    def _read_next_message(self):
        #self.rfile.read(n) is blocking.
        #it returns however immediately when the socket is closed.
        try:
            self.opcode = ord(self.rfile.read(1)) & 0x0F           
            length = ord(self.rfile.read(1)) & 0x7F
            #self.log_message("_read_next_message: opcode: %02X length: %d" % (self.opcode, length))
            if length == 126:
                length = struct.unpack(">H", self.rfile.read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self.rfile.read(8))[0]
            masks = [byte for byte in self.rfile.read(4)]
            decoded = ""
            for byte in self.rfile.read(length):
                decoded += chr(byte ^ masks[len(decoded) % 4])
            self._on_message(decoded)
        except (struct.error, TypeError) as e:
            #catch exceptions from ord() and struct.unpack()
            if self.ws_connected:
                self.log_message("_read_next_message exception %s" % (str(e.args)))
                raise WebSocketError("Websocket read aborted while listening")
            else:
                #the socket was closed while waiting for input
                self.log_error("RCV: _read_next_message aborted after closed connection")
                pass
        
    def _send_message(self, opcode, message):
        with self._sendLock:
            #self.log_message("_send_message: opcode: %02X msg: %s" % (opcode, message))
            try:
                #use of self.wfile.write gives socket exception after socket is closed. Avoid.
                self.request.send((0x80 + opcode).to_bytes(1, 'big'))
                length = len(message)
                if length <= 125:
                    self.request.send(length.to_bytes(1, 'big'))
                elif length >= 126 and length <= 65535:
                    self.request.send((126).to_bytes(1, 'big'))
                    self.request.send(struct.pack(">H", length))
                else:
                    self.request.send((127).to_bytes(1, 'big'))
                    self.request.send(struct.pack(">Q", length))
                if length > 0:
                    self.request.send(message.encode('utf-8'))
            except socket.error as e:
                #websocket content error, time-out or disconnect.
                self.log_message("SND: Close connection: Socket Error %s" % str(e.args))
                self._ws_close()
            except Exception as err:
                #unexpected error in websocket connection.
                self.log_error("SND: Exception: in _send_message: %s" % str(err.args))
                self._ws_close()

    def _handshake(self):
        # self.log_message("_handshake()")
        headers=self.headers
        if self.headers.get("Upgrade", None) and self.headers.get("Upgrade", None).lower().strip() != "websocket":
            return
        key = headers['Sec-WebSocket-Key']
        digest = b64encode(sha1((key + self._ws_GUID).encode()).digest()).decode()
        self.send_response(101, 'Switching Protocols')
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', digest)
        self.end_headers()
        self.ws_connected = True
        #self.close_connection = 0
        self.on_ws_connected()
    
    def _ws_close(self):
        #avoid closing a single socket two time for send and receive.
        #self.log_message("LOCK: WAIT _was_close obj: %s thd %s" % (str(self) , threading.current_thread().ident)) 
        #self.mutex.acquire()
        #self.log_message("LOCK: ACKD _was_close obj: %s thd %s" % (str(self) , threading.current_thread().ident)) 
        try:
            if self.ws_connected:
                self.ws_connected = False
                #Terminate BaseHTTPRequestHandler.handle() loop:
                self.close_connection = 1
                #send close and ignore exceptions. An error may already have occurred.
                try: 
                    self._send_close()
                except:
                    #self.log_message("_ws_close we send a close to a broken line. Do not expect much")
                    pass
                self.on_ws_closed()
            else:
                self.log_message("_ws_close websocket in closed state. Ignore.")
                pass
        finally:
            #self.mutex.release()
            pass
        #self.log_message("LOCK: RLSD _was_close obj: %s thd %s" % (str(self) , threading.current_thread().ident)) 
            
    def _on_message(self, message):
        # self.log_message("_on_message: opcode: %02X msg: %s" % (self.opcode, message))
        
        # close
        if self.opcode == self._opcode_close:
            self.ws_connected = False
            #Terminate BaseHTTPRequestHandler.handle() loop:
            self.close_connection = 1
            try:
                self._send_close()
            except:
                #self.log_message("_on_message we send a close to a broken line. Do not expect much")
                pass
            self.on_ws_closed()
        # ping
        elif self.opcode == self._opcode_ping:
            _send_message(self._opcode_pong, message)
        # pong
        elif self.opcode == self._opcode_pong:
            pass
        # data
        elif (self.opcode == self._opcode_continu or 
                self.opcode == self._opcode_text or 
                self.opcode == self._opcode_binary):
            self.on_ws_message(message)

    def _send_close(self):
        #Dedicated _send_close allows for catch all exception handling
        msg = bytearray()
        msg.append(0x80 + self._opcode_close)
        msg.append(0x00)
        self.request.send(msg)
    

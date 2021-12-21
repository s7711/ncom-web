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
ncom-web main entry point

The ncom-web application:
* decodes NCOM ethernet data from an OxTS inertial navigation system
* serves static web pages
* serves two web sockets (nav.json, status.json) so NCOM data can be
    displayed in web pages

The basic setup that I created it for is:

"OxTS - Raspberry Pi" connected by ethernet
"Raspberry Pi - network" connected by wlan

This separates the OxTS navigation system from the main network.

Probably there should be some command line options, but I have not
implemented these. The port address for the web server is hard coded.
The NCOM decoder will receive from any OxTS on the network, so you
cannot have two at the same time. The IP address of my OxTS was
192.168.2.62 and this needs to be updated in the code if you want
to send messages to the OxTS. See below.

Usage:

python3 main.py

Then, from a web browser:

http://<ip>:8000/nav.html
http://<ip>:8000/status.html

For example: http://192.168.1.10:8000/nav.html

You will have to press Ctrl-C twice (or Ctrl-Break for Windows) because
the threads are blocked on sockets and won't quit. Another thing to fix.

You can add html pages to directory "static" to create your own
templates. My HTML is functional but it needs someone with more
skill to create beautiful pages :-)

The python http.server that the web server is based on claims not to
be secure so it is probably best not to expose this application to
the web.
"""

# Standard python imports
import time
import json
import threading
import socket

# Local modules
import ncomrx_thread
import bgWebServer


# Start the background web server
ws = bgWebServer.BgWebServer()

# Start background ncom receiver and decoder
nrx = ncomrx_thread.NcomRxThread()

# Socket for sending UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def serve_json():
	""" serve_json() loops forever serving ncom to the web sockets """
	global nrx, ws
	while(1):
		time.sleep(0.5)
		nav_json = json.dumps(nrx.nav, default=str)
		status_json = json.dumps(nrx.status, default=str)
		ws.send_message_all(nav_json, path="/nav.json")
		ws.send_message_all(status_json, path="/status.json")


# Start the program
print("Use Ctrl-C (Ctrl-Break) twice to quit")
threading.Thread(target=serve_json).start()

# receive messages from web sockets
while(1):
	message = ws.next_message()
	print(message)
	sock.sendto(bytes(message+"\n", "utf-8"), ("192.168.2.62",3001))

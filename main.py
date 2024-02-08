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
* decodes NCOM ethernet data from OxTS inertial navigation systems
* serves static web pages
* Has a websocket called message.json that sends information to the
  web pages. The websocket is organised as a dictonary where the key
  gives the type of information. For example the "nav" key sends the
  navigation information from the OxTS inertial navigation system.
* Has a websocket called devices.json, which lists the IP addresses
  of the INSs on the network

Note that this version is IP address specific and can be used with
multiple INSs on the same network. To select which INS you want the
data from you need to specify a query in the web socket address.
For example:

  ws://192.168.2.123:8000/nav.json?ip=192.168.2.62

will connect to 192.168.2.123 and open the web socket that serves
navigation data from INS on IP address 192.168.2.62

The devices.json web socket doesn't need an IP address because it lists
all of the devices/IP addresses that have been received

The basic hardware setup that I used is:

"OxTS <--> Raspberry Pi" connected by ethernet using static IP in range 192.168.2.xxx
"Raspberry Pi <--> network" connected by wlan using DHCP (192.168.1.xxx)

This separates the OxTS navigation system from the main network.

Probably there should be some command line options, but I have not
implemented these. The port address for the web server is hard coded.
The NCOM decoder will receive from all OxTS INSs on the network.

Usage:

python3 main.py

Then, from a web browser:

http://<ip of python PC>:8000/nav.html?ip=<ip of INS>
http://<ip of python PC>:8000/status.html?ip=<ip of INS>

For example: http://192.168.1.10:8000/nav.html?ip=195.0.0.20

You can add html pages to directory "static" to create your own
templates. My HTML is functional but it needs someone with more
skill to create beautiful pages :-)

The python http.server that the web server is based on claims not to
be secure so it is probably best not to expose this application to
the web.

Version 240208: Changed web-sockets so nav, status, etc. are sent
though one socket, message.ws. Changed html to use chart.js.

"""

# Standard python imports
import time
import json
import threading
import socket
import sys
import os
import re

# Local modules
import ncomrx_thread
import bgWebServer

# Start the background web server
ws = bgWebServer.BgWebServer()

# Start background ncom receiver and decoder
nrxs = ncomrx_thread.NcomRxThread()

# Socket for sending UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def serve_json():
    """
    serve_json() loops forever serving ncom to the web sockets.
    Run in a new thread
    """
    global nrx, ws
    while True:
        time.sleep(0.5) # Sets the update rate for the sockets
        
        # nrxs.nrx is a dictionary of all the INSs found on the network
        # ... and the keys are the IP addresses
        # Form a list of the IP addresses
        devices = [ nrx for nrx in nrxs.nrx ] # list of keys/ip addresses
        devices_json = json.dumps(devices)
        ws.send_message_all(devices_json, path="/devices.json")
        
        # For each INS extract the information from the decoder (NcomRx type)
        # Note that this implementation encodes everything in JSON, even if
        # it ends up that no websocket wants the data
        for addr, nrx in nrxs.nrx.items():      
            nav_json = json.dumps({"nav":nrx['decoder'].nav}, default=str)
            status_json = json.dumps({"status":nrx['decoder'].status}, default=str)
            connection_json = json.dumps({"connection":nrx['decoder'].connection}, default=str)

            ws.send_message_all(nav_json, path="/message.json?ip="+addr)
            ws.send_message_all(status_json, path="/message.json?ip="+addr)
            ws.send_message_all(connection_json, path="/message.json?ip="+addr)

# Start the program
print("Use Ctrl-C (Linux) or System Break (Windows) to quit")
threading.Thread(target=serve_json).start()


try:
    # receive messages from web sockets
    while(1):
        message,path = ws.recvpath() # Note: blocking
        print(path + ": " + message)
        
        # Many ways to split out the query, none particularly elegant
        ip1 = re.search(r'[?&]ip(=([^&#]*)|&|#|$)',path)
        if not ip1: continue      # query not found
        ip2 = ip1.group()         # ?ip=...
        if len(ip2) < 4: continue # probably not necessary
        ip = ip2[4:]              # ...
        try:                      # because might not be valid IP
            sock.sendto(bytes(message+"\n", "utf-8"), (ip,3001))
        except:
            pass

except KeyboardInterrupt as e:
    print('Stopping')
    # Needs extra code to stop threads, which may be blocked on sockets
    try:
        sys.exit(0)
    except SystemExit:
        os._exit(1)

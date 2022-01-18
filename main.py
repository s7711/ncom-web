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
ncom-web-gad main entry point

The ncom-web-gad application:
* decodes NCOM ethernet data from OxTS inertial navigation systems
* serves static web pages
* serves four web sockets so NCOM data can be displayed in web pages
  - nav.json contains the navigation information from NCOM
  - status.json contains the status information from NCOM
  - connection.json contains information about the decoding
  - devices.json lists the IP address of all the devices
* Sends gad information to INS (testing/developing/example)

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
"""

# Standard python imports
import time
import json
import threading
import socket
import sys
import os
import re
import oxts_sdk
import queue

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
            nav_json = json.dumps(nrx['decoder'].nav, default=str)
            status_json = json.dumps(nrx['decoder'].status, default=str)
            connection_json = json.dumps(nrx['decoder'].connection, default=str)
            # needs some form of ip address filter here
            ws.send_message_all(nav_json, path="/nav.json?ip="+addr)
            ws.send_message_all(status_json, path="/status.json?ip="+addr)
            ws.send_message_all(connection_json, path="/connection.json?ip="+addr)


gad_queue = queue.Queue()

def serve_gad():
    """
    Sends oxts gad (generic aiding) messages
    Runs in a new thread
    Receives commands from queue
    """
    gh = oxts_sdk.GadHandler()
    gh.set_encoder_to_bin()    

    # gadPkts is a dictionary of {'type_ip':type.ip address, 'pkt':gad_packet}
    # These are the packets that should be sent out on a regular basis
    # The type_ip field is used so the entry can be found, replaced and remove easily
    # and is formatted as "gp:192.168.2.62", where "gp" is:
    #   gp: gadPosition
    #   gv: gadVelocity
    #   etc.
    # Use split(":") to separate type and ip address
    gadPkts = {}
    
    while True:
        time.sleep(0.5) # Sets the rate for updates

        # Process the gad queue
        more = True
        while more:
            try:
                ip, command = gad_queue.get_nowait()
            except:
                # Assume that the queue is now empty
                more = False
            
            if more == True:
                # Split up the command (uses spaces as a delimiter)
                args = command.split()
                
                # Interpret the command
                # In a try block to catch user errors, and anything else
                try:
                    ### vel_neu
                    if args[0] == '#vel_neu':
                        if len(args) == 5 or len(args) == 4:
                            # #vel_neu vn ve vu [acc]
                            gv = oxts_sdk.GadVelocity(130)
                            gv.vel_neu = [ float(v) for v in args[1:4] ]
                            if len(args) == 5:
                                gv.vel_neu_var = [float(args[4]),float(args[4]),float(args[4]),0.0,0.0,0.0] # Note: using 3 terms does not appear to work
                            else:
                                # Default to a covariance of 0.1
                                gv.vel_neu_var = [0.1,0.1,0.1,0.0,0.0,0.0] # Note: using 3 terms does not appear to work
                            gv.set_time_void()
                            gv.aiding_lever_arm_fixed = [0.0,0.0,0.0]
                            gv.aiding_lever_arm_var = [0.01,0.01,0.01]
                            gadPkts["gv:"+ip] = gv
                        elif args[1] == 'stop':
                            del gadPkts["gv:"+ip]
                            
                    ### pos_geo    
                    elif args[0] == '#pos_geo':
                        if len(args) == 4:
                            # #pos_geo lat lon alt
                            gp = oxts_sdk.GadPosition(129)
                            gp.pos_geodetic = [ float(v) for v in args[1:4] ]                    
                            gp.pos_geodetic_var = [0.01,0.01,10.0,0.0,0.0,0.0] # Note: using 3 terms does not appear to work
                            gp.set_time_void()
                            gp.aiding_lever_arm_fixed = [0.0,0.0,0.0]
                            gp.aiding_lever_arm_var = [0.001,0.001,0.001]
                            gadPkts["gp:"+ip] = gp
                        elif args[1] == 'stop':
                            del gadPkts["gp:"+ip]
                    
                    ### pos_att
                    elif args[0] == '#att':
                        if len(args) == 4:
                            ga = oxts_sdk.GadAttitude(131)
                            ga.att = [ float(v) for v in args[1:4] ]                    
                            ga.att_var = [10.0,100.0,100.0]
                            ga.set_time_void()
                            ga.set_aiding_alignment_optimising()
                            ga.aiding_alignment_var = [5.0,5.0,5.0]
                            gadPkts["ga:"+ip] = ga
                        elif args[1] == 'stop':
                            del gadPkts["ga:"+ip]
                    
                except Exception as e:
                    print(f"Command error: {e}")            
        
        # Each gad packet that needs to be sent to each ip address
        # in gadPkts with keys 'type_ip' and 'pkt'
        # Set the IP address and then send the packet
        for k,pkt in gadPkts.items():
            try:
                type_ip = k.split(':')
                gh.set_output_mode_to_udp(type_ip[1]) # Should be IP address
                gh.send_packet(pkt)
            except Exception as e:
                print(e)
                del gadPkts[k]                        # Don't bother with this again
                    

# Start the program
print("Use Ctrl-C to quit")
threading.Thread(target=serve_json).start()

threading.Thread(target=serve_gad).start()


try:
    # receive messages from web sockets
    while True:
        message,path = ws.recvpath() # Note: blocking
        print(path + ": " + message)
        
        # Many ways to split out the query, none particularly elegant
        ip1 = re.search(r'[?&]ip(=([^&#]*)|&|#|$)',path)
        if not ip1: continue        # query not found
        ip2 = ip1.group()           # ?ip=...
        if len(ip2) < 4: continue   # probably not necessary
        ip = ip2[4:]                # ...
        if message.startswith('#'): # then assume it is a GAD message
            gad_queue.put((ip,message)) # put in the GAD queue
        else:   
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

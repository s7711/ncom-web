# ncom-web
ncom-web is a python program that receives NCOM data from an OxTS INS (RT3000, xNAV, etc.) and makes the real-time data available on a web page. You can view the web page on a PC, tablet or phone. No need to use OxTS software any more. Run the software by:
* Install python 3 (I was using 3.9.2 on a Raspberry Pi)
* Download the repository
* Run **python main.py**
* Go to web page http://\<*ip address*\>:8000/nav.html for navigation (e.g. http://192.168.1.123:8000/nav.html in my setup)
* Go to web page http://\<*ip address*\>:8000/status.html for status
* See example http://\<ip address\>:8000/xy.html for an XY plot of position

In my setup I had a Raspberry Pi with:
* **eth0** configured using a static IP address (192.168.2.11)
* **wlan0** configured using DHCP (192.168.1.123)

My xNAV550 had its IP address changed to 192.168.2.62. If you want to send commands to your OxTS INS then you need to change the IP address in the python code (an improvement that I have to make in a future version).

Effectively I have separated my xNAV550's network from my office network but I can still talk to the xNAV550, see its outputs and send commands to it (like the command to force initialisation).

The web page templates are pretty basic and you may want to change/improve them. You can use the pages as examples and add custom pages. The web pages are saved in the "static" directory.

The software includes:
* Socket to receive OxTS NCOM data on port 3000
* Python NCOM decoder (not fully tested)
* Basic web server
* Translation of NCOM navigation and NCOM status measurements to JSON
* Web sockets to send navigation and status measurements to the web page

There are many improvements that need to be made:
* Communication information (packets received, errors, etc.) are not transmitted
* You cannot use the program on a network with more than one OxTS INS, it will mix up all the measurements
* The update rate is hard coded at 2Hz, which is fine for text but a higher rate may be necessary if graphs are added
* The IP address for the send box is hard coded and should auto-configure itself
* Some better templates are needed
* The formatting of comments could be a little more consistent. I started one way and then changed. Sorry
* The web server claims poor security (I don't know why) so it is probably best not to use it on the internet

The licensing for the Google Chart is not clear. It uses an MIT license but there may be some usage restriction so you cannot/shouldn't use it on an intranet. You may find it doesn't work unless the browser you are using has internet access. If I have violated a license Google then I'm sorry and I will remove it.
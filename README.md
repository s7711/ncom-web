# ncom-web
ncom-web is a python program that receives NCOM data from OxTS INSs (RT3000, xNAV, etc.) and makes the real-time data available on web pages. You can view the web page on a PC, tablet or phone. No need to use OxTS software any more. Run the software by:
* Install python 3 (I was using 3.9.2 on a Raspberry Pi)
* Download the repository
* Run **python main.py**
* Go to web page http://\<*ip address*\>:8000
* Select the web page template for the INS that you want to view

This version supports multiple INSs, so can work in an RT-Range application (though it doesn't decode any RT-Range data). The following page templates are available:
* Speed - shows the speed, heading, GNSS mode, acceleration and angular rates
* Nav - shows the basic navigation messages in NCOM
* Status - shows some of the status messages in NCOM
* Connection - shows information about the NCOM decoder (useful for debugging)
* XY - shows a basic XY plot of position

Here is an example page:

![Example html template showing xNAV550 data](https://github.com/s7711/ncom-web/blob/main/images/speed-template-example.png)

Some of the pages can send commands to the INS, which is useful when initialising the INS on the bench (using !set init hea 0).

In my setup I had a Raspberry Pi with:
* **eth0** configured using a static IP address (192.168.2.11)
* **wlan0** configured using DHCP (192.168.1.123, or 'marcopolo' in the example above)

My xNAV550 had its IP address changed to 192.168.2.62.

Effectively I have separated my xNAV550's network from my office network but I can still talk to the xNAV550, see its outputs and send commands to it (like the command to force initialisation). You do not need separate networks and it will work fine on one network.

The web page templates are pretty basic and you may want to change/improve them. You can use the pages as examples and add custom pages. The web pages are saved in the "static" directory. "Speed.html" is the most comprehensive page, but that also makes it the most complex. I have documented this page more than the others. Hopefully it will all make sense.

The software includes:
* Socket to receive OxTS NCOM data on port 3000
* Python NCOM decoder (not fully tested)
* Basic web server
* Translation of NCOM navigation and NCOM status measurements to JSON
* Communication information as JSON
* Web sockets to send navigation and status measurements to the web page

There are many improvements that need to be made:
* The update rate is hard coded at 2Hz, which is fine for text but a higher rate may be necessary if graphs are added
* Some better templates are needed
* The formatting of comments could be a little more consistent. I started one way and then changed. Sorry
* The web server claims poor security (I don't know why) so it is probably best not to use it on the internet

The licensing for the Google Chart is not clear. It uses an MIT license but there may be some usage restriction so you cannot/shouldn't use it on an intranet. You may find it doesn't work unless the browser you are using has internet access. If I have violated a license Google then I'm sorry and I will remove it.

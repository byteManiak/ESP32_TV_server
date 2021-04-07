#!/usr/bin/python3

from http.server import BaseHTTPRequestHandler, HTTPServer # HTTP server
from bs4 import BeautifulSoup as XMLParser # For decoding RSS news feeds
from urllib.request import urlopen, Request # For opening external URLs
from unidecode import unidecode # For encoding data in the right format
from datetime import datetime # For weather date and time formatting
import pyowm # For weather API data querying
import os # Misc

links = open("links.txt").readlines() # Links used for Internet radio stations
names = open("names.txt").readlines() # Names of Internet radio stations

rss = open("feeds.txt").readlines() # Links to the RSS news feeds

weather = pyowm.OWM('31d70530dd154f05d387eac032320b44').weather_manager() # Handle to the weather API

# Establish the message to send back to the ESP based on the received GET values
def handleValues(request):
    # Default to sending an empty response back to the ESP
    response = ""

    # Get the type of request received from the ESP
    req = request[1:]

    # Get key and value(s) of GET request
    keyValue = req.split('=', 2)

    # Check that the GET request is made of both key *and* value(s)
    if len(keyValue) == 2:

        # Send list of radio stations
        if keyValue[0] == "radio":
            # Get requested list range of stations
            valueRanges = keyValue[1].split(',')

            # Extract the radio station names from the list
            for i in range(len(links)):
                if i >= int(valueRanges[0]) and i <= int(valueRanges[1]):
                    name = names[i]
                    # Remove carriage return as it confuses the ESP HTTP client
                    name = name[:-1]
                    response += name
                    if i < int(valueRanges[1]):
                        response += ';'

        # Send URL of selected radio station
        elif keyValue[0] == "station":
            # Get requested station index
            stationNum = int(keyValue[1])
            link = links[stationNum]
            # Remove carriage return as it confuses the ESP HTTP client
            link = link[:-1]
            response += link

        # Send list of news headlines
        elif keyValue[0] == "news":
            # Get request list range of headlines
            valueRanges = keyValue[1].split(',')

            # Get URL of currently selected RSS feed
            url = rss[int(valueRanges[0])%len(rss)]
            req = Request(url)
            # Trick the RSS server into thinking we are using a browser to avoid being denied
            req.add_header('User-agent', 'Mozilla/5.0')

            # Read the RSS feed as XML
            rssContents = urlopen(req).read()
            parser = XMLParser(rssContents, "html.parser")
            # Extract titles from read XML
            rssTitles = parser.find_all('title')

            # Establish whether to also send the first title which (seems to) represents the RSS feed's name
            requestedPage = int(valueRanges[1])
            if requestedPage == 0:
                headlinesToSend = 17
            else:
                headlinesToSend = 16

            # Extract the news headlines from the list
            for i in range(len(rssTitles)):
                if i >= requestedPage*headlinesToSend and i < (requestedPage+1)*headlinesToSend:
                    # Read only the first 256 characters
                    response += rssTitles[i].text[:256].replace(';', ',')
                    if i < (requestedPage+1)*headlinesToSend-1:
                        response += ";"

        # Send list of downloadable apps
        elif keyValue[0] == "appList":
            # Get request list range of apps
            valueRanges = keyValue[1].split(',')
            # Get a list of the apps present on the server
            fileList = os.listdir("./apps")

            # Extract the app names from the list
            for i in range(len(fileList)):
                if i >= int(valueRanges[0]) and i <= int(valueRanges[1]):
                    file = open("apps/" + fileList[i], "rb")
                    # Ignore the first 0x120 bytes
                    file.read(0x120)
                    # Read the app name from the .rodata_custom_desc header
                    appName = file.read(32)
                    # Remove "\x00" as it is redundant
                    response += appName.decode().replace('\x00', '')
                    if i < int(valueRanges[1]) and i < len(fileList)-1:
                        response += ';'

        # Send the selected app to download
        elif keyValue[0] == "app":
            # Get requested app index
            valueRanges = keyValue[1]
            fileName = os.listdir("./apps")[int(valueRanges[0])]
            return open("apps/" + fileName, "rb").read()

        # Send the selected location's weather data
        elif keyValue[0] == "weather":
            try:
                # Get requested weather location
                weatherLocation = keyValue[1]
                # Replace spaces with URL %20 spaces
                weatherLocation = weatherLocation.replace("%20", " ")
                # Get the forecast at said location for the next 5 days, in 3-hour increments
                weatherStats = weather.forecast_at_place(weatherLocation, '3h')

                # Get the date, temperature and detailed status of each returned forecast
                for i in weatherStats.forecast.weathers:
                    unixTime = i.reference_time()
                    time = datetime.utcfromtimestamp(unixTime).strftime("%d.%m %H")
                    response += time + " " + str(int(i.temperature('celsius')['temp'])) + " " + i.detailed_status + ";"
            # Triggered on invalid location or server error
            except:
                response = ""

    # Encode the returned message so it can be read by the ESP
    return unidecode(response).encode('ascii')

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse values of request
        ret = handleValues(self.path)

        # Always send OK as there is no reason why this server should fail
        self.send_response(200)
        # Send the size of the message to be sent to the ESP32
        self.send_header('Content-Length', len(ret))
        self.end_headers()
        # Send the message to the ESP32
        self.wfile.write(ret)
        # self.wfile.flush()

    def do_POST(self):
        pass

# Open a server socket on port 25565
server_address = ('', 25565)
httpd = HTTPServer(server_address, handler)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
httpd.server_close()

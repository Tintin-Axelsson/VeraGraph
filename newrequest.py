import argparse
import requests
import time

import xml.etree.ElementTree as ET
import prometheus_client as prometheus

from requests.auth import HTTPBasicAuth
from ws4py.client.threadedclient import WebSocketClient

namespace = '{http://www.w3.org/1999/xhtml}'

middleware_status_gauge = prometheus.Gauge('gauge_middleware_status', 'Always set to 1, use as running indicator')
middleware_status_gauge.set(1)

robot_operating_mode = prometheus.Gauge('robot_operating_mode_gauge',
                                        'Current robot operating mode. 0 for manual, 1 for auto')

class EventHandler:
    def __init__(self):
        self.last_routine = None
        self.connected = None
        self.last_time = 0
        self.number_built = 100
        self.temperature = 33

    #def extract_event(self, event):
    #    root = ET.fromstring(str(event))

    #    if root.findall(".//{0}span[@class='routine-name']".format(namespace)):
    #        return 1, root.find(".//{0}span[@class='routine-name']".format(namespace)).text
    #    if root.findall(".//{0}li[@class='pnl-ctrlstate-ev']".format(namespace)):
    #        return 2, root.find(".//{0}li[@class='pnl-ctrlstate-ev']/{0}span".format(namespace)).text
    #    if root.findall(".//{0}li[@class='pnl-opmode-ev']".format(namespace)):
    #        return 3, root.find(".//{0}li[@class='pnl-opmode-ev']/{0}span".format(namespace)).text

    def process_event(self, event):
        #event_num, event_text = self.extract_event(event)
        root = ET.fromstring(str(event))
        events = []

        if root.findall(".//{0}span[@class='routine-name']".format(namespace)):
            events.append(root.find(".//{0}span[@class='routine-name']".format(namespace)).text)
        if root.findall(".//{0}li[@class='pnl-ctrlstate-ev']".format(namespace)):
            events.append(root.find(".//{0}li[@class='pnl-ctrlstate-ev']/{0}span".format(namespace)).text)
        if root.findall(".//{0}li[@class='pnl-opmode-ev']".format(namespace)):
            events.append(root.find(".//{0}li[@class='pnl-opmode-ev']/{0}span".format(namespace)).text)

        for lol in events:
            print("Event: ", lol)

        #if event_num == 1:
        #    if self.last_routine == "station2" and event_text == "main":
        #        print("Station cycle complete")
        #        self.number_built += 1
        #        cycle_time = time.time() - self.last_time
        #    self.last_routine = event_text


event_handler = EventHandler()


class RobWebSocketClient(WebSocketClient):
    def opened(self):
        print("Socket connection established")

    def closed(self, code, reason=None):
        print("Socket connection closed", code, reason)

    def received_message(self, message):
        print("#########EVENT###########")
        event_handler.process_event(message)
        #print("Event number: ", event_num, "  Raw Text: ", event_text)
        # process_event(event_num, event_text)
        print("#########EVENT###########")


class RobCom:
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(self.username, self.password)
        self.sub_url = 'https://{0}/subscription'.format(self.host)
        self.session = requests.Session()
        self.event_handler = EventHandler()
        self.location = None
        self.cookie = None
        self.header = None
        self.ws = None

    def subscribe(self):
        payload = {'resources': ['1', '2', '3'],
                   '1': '/rw/rapid/tasks/T_ROB1/pcp;programpointerchange',
                   '1-p': '1',
                   '2': '/rw/panel/ctrl-state',
                   '2-p': '1',
                   '3': '/rw/panel/opmode',
                   '3-p': '1'}

        header = {'Content-Type': 'application/x-www-form-urlencoded;v=2.0'}

        try:
            resp = self.session.post(self.sub_url, auth=self.auth, headers=header, data=payload, verify=False, timeout=10)
            if resp.status_code == 201:
                print("Handle initial events:")
                event_handler.process_event(resp.text)
                self.location = resp.headers['Location']
                self.cookie = '-http-session-={0}; ABBCX={1}'.format(resp.cookies['-http-session-'], resp.cookies['ABBCX'])
                if not event_handler.connected:
                    event_handler.connected = True
                return True
            else:
                print("Error subscribing " + str(resp.status_code))
        except:
            print("Request timed out...")

        if event_handler.connected:
            event_handler.connected = False
        return False

    def start_rvec(self):
        self.header = [('Cookie', self.cookie)]
        self.ws = RobWebSocketClient(self.location, protocols=['rws_subscription'], headers=self.header)
        self.ws.connect()
        self.ws.run_forever()

    def close(self):
        self.ws.close()


def main():
    # Starting prometheus server on port 8000
    prometheus.start_http_server(8000)

    parser = argparse.ArgumentParser()
    parser.add_argument("-host", default='192.168.4.10')
    parser.add_argument("-user", default='Default User')
    parser.add_argument("-passcode", default='robotics')
    args = parser.parse_args()

    api = RobCom(args.host, args.user, args.passcode)

    while True:
        if api.subscribe():
            api.start_rvec()


if __name__ == '__main__':
    main()

import argparse
import requests
import time

import xml.etree.ElementTree as ET
import prometheus_client as prometheus

from requests.auth import HTTPBasicAuth
from ws4py.client.threadedclient import WebSocketClient

namespace = '{http://www.w3.org/1999/xhtml}'

status_middleware_gauge = prometheus.Gauge('middleware_status_gauge', 'Always set to 1, use as running indicator')
status_middleware_gauge.set(1)
status_robot_connection_gauge = prometheus.Gauge('robot_connection_gauge', '1 if a socket connection is established')

robot_operating_mode = prometheus.Gauge('robot_operating_mode_gauge',
                                        'Current robot operating mode. 0 for manual, 1 for auto')
robot_motor_mode = prometheus.Gauge('robot_motor_mode_gauge',
                                    'Current robot motor mode. 0 for motoroff, 1 for motoron')

info_number_built = prometheus.Counter('info_number_built',
                                       'Vera build count')  # TODO: Check if counter resets on process restart.

# TODO: Current station


class EventHandler:
    def __init__(self):
        self.last_routine = None
        self.connected = None
        self.last_time = 0
        self.number_built = 100
        self.temperature = 33

    def process_event(self, event):
        print(event)
        root = ET.fromstring(str(event))
        events = []

        # Find and append all interesting events to a list.
        if root.findall(".//{0}span[@class='routine-name']".format(namespace)):
            events.extend([[1, root.find(".//{0}span[@class='routine-name']".format(namespace)).text]])
        if root.findall(".//{0}li[@class='pnl-ctrlstate-ev']".format(namespace)):
            events.extend([[2, root.find(".//{0}li[@class='pnl-ctrlstate-ev']/{0}span".format(namespace)).text]])
        if root.findall(".//{0}li[@class='pnl-opmode-ev']".format(namespace)):
            events.extend([[3, root.find(".//{0}li[@class='pnl-opmode-ev']/{0}span".format(namespace)).text]])
        #if root.findall(".//{0}li[@class='sys-energy-ev']".format(namespace)):
        #    print("Visst är det kul när det inte fungerar!")

        # Iterate the created list.
        for iteration, item in enumerate(events):
            event_num, event_str = item[0], item[1]

            # Routine Change
            if event_num == 1:
                if self.last_routine == "station2" and event_str == "main":
                    print("Station cycle complete")
                    self.number_built += 1
                    info_number_built.inc(1)
                    cycle_time = time.time() - self.last_time
                    print("Cycle Time: ", round(cycle_time))
                    # TODO: Make sure only "valid" cycle times get scraped.
                self.last_routine = event_str

            # Controller state
            elif event_num == 2:
                print("Controller motor event")
                print("Event string " + event_str)
                pass

            # Controller OP-Mode
            elif event_num == 3:
                print("Controller OP-Mode event")
                print("Event string " + event_str)
                pass

            elif event_num == 4:
                pass


event_handler = EventHandler()


class RobWebSocketClient(WebSocketClient):
    def opened(self):
        print("Socket connection established")
        status_robot_connection_gauge.set(1)

    def closed(self, code, reason=None):
        status_robot_connection_gauge.set(0)
        print("Socket connection closed", code, reason)

    def received_message(self, message):
        print("#########EVENT###########")
        event_handler.process_event(message)
        # print("Event number: ", event_num, "  Raw Text: ", event_text)
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
        payload = {'resources': ['1', '2', '3', '4'],
                   '1': '/rw/rapid/tasks/T_ROB1/pcp;programpointerchange',
                   '1-p': '1',
                   '2': '/rw/panel/ctrl-state',
                   '2-p': '1',
                   '3': '/rw/panel/opmode',
                   '3-p': '1'}
                    # '4': '/rw/system/energy', # TODO: Energy not behaving as expected, poll instead of sub?
                    # '4-p': '1'}

        header = {'Content-Type': 'application/x-www-form-urlencoded;v=2.0'}

        try:
            resp = self.session.post(self.sub_url, auth=self.auth, headers=header, data=payload, verify=False,
                                     timeout=10)
            if resp.status_code == 201:
                print("Handle initial events:")
                event_handler.process_event(resp.text)
                self.location = resp.headers['Location']
                self.cookie = '-http-session-={0}; ABBCX={1}'.format(resp.cookies['-http-session-'],
                                                                     resp.cookies['ABBCX'])
                if not event_handler.connected:
                    event_handler.connected = True
                return True
            else:
                print("Error subscribing " + str(resp.status_code))
                time.sleep(1)
        except:
            print("Request timed out...")
            time.sleep(1)

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

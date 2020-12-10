import argparse
import requests

import xml.etree.ElementTree as ET

from requests.auth import HTTPBasicAuth
from ws4py.client.threadedclient import WebSocketClient

namespace = '{http://www.w3.org/1999/xhtml}'

last_routine = None
number_built = 100


class EventHandler():
    def __init__(self):
        self.last_routine = None
        self.number_built = 100

    def extract_event(self, event):
        root = ET.fromstring(str(event))
        if root.findall(".//{0}span[@class='routine-name']".format(namespace)):
            return 1, root.find(".//{0}span[@class='routine-name']".format(namespace)).text
        elif root.findall(".//{0}li[@class='pnl-ctrlstate-ev']".format(namespace)):
            return 2, root.find(".//{0}li[@class='pnl-ctrlstate-ev']/{0}span".format(namespace)).text
        elif root.findall(".//{0}li[@class='pnl-opmode-ev']".format(namespace)):
            return 3, root.find(".//{0}li[@class='pnl-opmode-ev']/{0}span".format(namespace)).text

    def process_event(self, event):
        event_num, event_text = self.extract_event(event)

        if event_num == 1:
            if self.last_routine == "station2" and event_text == "main":
                self.number_built += 1
            self.last_routine = event_text

event_handler = EventHandler()

class RobWebSocketClient(WebSocketClient):
    def opened(self):
        print("Socket connection established")

    def closed(self, code, reason=None):
        print("Socket connection closed", code, reason)

    def received_message(self, message):
        print("#########EVENT###########")
        event_num, event_text = event_handler.extract_event(message)
        print("Event number: ", event_num, "  Raw Text: ", event_text)
        #process_event(event_num, event_text)
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
        resp = self.session.post(self.sub_url, auth=self.auth, headers=header, data=payload, verify=False, timeout=10)

        if resp.status_code == 201:
            self.location = resp.headers['Location']
            self.cookie = '-http-session-={0}; ABBCX={1}'.format(resp.cookies['-http-session-'], resp.cookies['ABBCX'])
            return True
        else:
            print("Error subscribing " + str(resp.status_code))
            return False

    def start_rvec(self):
        self.header = [('Cookie', self.cookie)]
        self.ws = RobWebSocketClient(self.location, protocols=['rws_subscription'], headers=self.header)
        self.ws.connect()
        self.ws.run_forever()

    def close(self):
        self.ws.close()


def main():
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

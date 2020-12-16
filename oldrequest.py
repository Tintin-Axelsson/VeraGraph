import sys
import requests
import argparse
import xml.etree.ElementTree as ET
from ws4py.client.threadedclient import WebSocketClient
from requests.auth import HTTPBasicAuth
from prometheus_client import start_http_server, Enum, Gauge, Info

namespace = '{http://www.w3.org/1999/xhtml}'

enum_robot_mode = Enum('robot_mode', 'Current mode of the robot, Manual or Auto', states=['MANR', 'AUTO'])
enum_robot_motor_state = Enum('robot_motor_state', 'Current motor state of the robot, On or Off',
                              states=['motoroff', 'motoron'])
enum_robot_run_state = Enum('robot_run_state', 'Current run-state of the robot, running or stopped',
                            states=['running', 'stopped'])

robot_connection_gauge = Gauge('robot_connection_gauge', 'State of the Robot-API connection')
robot_connection_gauge.set(1)

info_robot_connected = Info('robot_connected', 'State of the Robot-API connection')
info_robot_connected.info({'Connection': 'Disconnected'})

#print(info_robot_connected)

enum_robot_mode.state('MANR')
enum_robot_motor_state.state('motoroff')
enum_robot_run_state.state('stopped')

connected = False


def print_event(evt):
    root = ET.fromstring(evt)
    if root.findall(".//{0}li[@class='pnl-ctrlstate-ev']".format(namespace)):
        print("\tController State : " + root.find(".//{0}li[@class='pnl-ctrlstate-ev']/{0}span".format(namespace)).text)
    if root.findall(".//{0}li[@class='pnl-opmode-ev']".format(namespace)):
      print("\tOperation Mode : " + root.find(".//{0}li[@class='pnl-opmode-ev']/{0}span".format(namespace)).text)
    if root.findall(".//{0}li[@class='pnl-speedratio-ev']".format(namespace)):
      print("\tSpeed Ratio : " + root.find(".//{0}li[@class='pnl-speedratio-ev']/{0}span".format(namespace)).text)
    if root.findall(".//{0}li[@class='pnl-custom_DO_2-ev']".format(namespace)):
      print("\tSignal State : " + root.find(".//{0}li[@class='pnl-custom_DO_2-ev']/{0}span".format(namespace)).text)
    if root.findall(".//{0}li[@class='pnl-coldetstate-ev']".format(namespace)):
        print("\tColdetstate : " + root.find(".//{0}li[@class='pnl-coldetstate-ev']/{0}span".format(namespace)).text)

#def extract_event(evt):
#    print("Extracting event")
#    root = ET.fromstring(evt)
#    if root.findall(".//{0}li[@class='pnl-ctrlstate-ev']".format(namespace)):
#        return root.find(".//{0}li[@class='pnl-ctrlstate-ev']/{0}span".format(namespace)).text
#    elif root.findall(".//{0}li[@class='pnl-opmode-ev']".format(namespace)):
#        return root.find(".//{0}li[@class='pnl-opmode-ev']/{0}span".format(namespace)).text
#    elif root.findall(".//{0}li[@class='pnl-speedratio-ev']".format(namespace)):
#        return root.find(".//{0}li[@class='pnl-speedratio-ev']/{0}span".format(namespace)).text
#    elif root.findall(".//{0}li[@class='pnl-custom_DO_2-ev']".format(namespace)):
#        return root.find(".//{0}li[@class='pnl-custom_DO_2-ev']/{0}span".format(namespace)).text
#    elif root.findall(".//{0}li[@class='pnl-coldetstate-ev']".format(namespace)):
#        return root.find(".//{0}li[@class='pnl-coldetstate-ev']/{0}span".format(namespace))
#    elif root.findall(".//{0}li[@class='rap-pcp-ev']".format(namespace)):
#        return root.find(".//{0}li[@class='rap-pcp-ev']/{0}span".format(namespace))


# This class encapsulates the Web Socket Callbacks functions.
class RobWebSocketClient(WebSocketClient):
    def opened(self):
        print("Web Sockect connection established")

    def closed(self, code, reason=None):
        print("Closed down", code, reason)

    def received_message(self, event_xml):
        print("Message recived!")
        if event_xml.is_text:
            #event = extract_event(event_xml.data.decode("utf-8"))
            print("Events : ")
            print_event(event_xml.data.decode("utf-8"))

            #if event == "MANR" or event == "AUTO":
            #    enum_robot_mode.state(event)
            #elif event == "motoron" or event == "motoroff":
            #    enum_robot_motor_state.state(event)
        else:
            print("Received Illegal Event " + str(event_xml))


# The main RobotWare Panel class
class RobCom:
    def __init__(self, host, username, password):
        self.host = host
        self.username = username
        self.password = password
        self.basic_auth = HTTPBasicAuth(self.username, self.password)
        self.subscription_url = 'https://{0}/subscription'.format(self.host)
        self.session = requests.Session()
        self.location = None
        self.cookie = None
        self.header = None
        self.ws = None

    def subscribe(self):
        # Create a payload to subscribe on RobotWare Panel Resources with high priority
        payload = {'resources': ['1', '2', '3'],
                   #'1': '/rw/panel/iosystem/signals/EtherNetIP/ManipulatorIO/custom_DO_2',
                   #'1-p': '1',
                   '1': '/rw/panel/ctrl-state',
                   '1-p': '1',
                   '2': '/rw/panel/opmode',
                   '2-p': '1',
                   '3': 'rw/rapid/tasks/T_ROB1/pcp',
                   '3-p': '1'}

        content_header = {'Content-Type': 'application/x-www-form-urlencoded;v=2.0'}
        try:
            resp = self.session.post(self.subscription_url, auth=self.basic_auth, headers=content_header, data=payload,
                                     verify=False, timeout=10)
            print("Connected set to true")
        except:
            print('Session timeout, retrying...')
            return False

        print("Initial Events : ")
        print_event(resp.text)
        if resp.status_code == 201:
            self.location = resp.headers['Location']
            self.cookie = '-http-session-={0}; ABBCX={1}'.format(resp.cookies['-http-session-'], resp.cookies['ABBCX'])
            return True
        else:
            print('Error subscribing ' + str(resp.status_code))
            return False

    def start_recv_events(self):
        self.header = [('Cookie', self.cookie)]
        self.ws = RobWebSocketClient(self.location,
                                     protocols=['rws_subscription'],
                                     headers=self.header)
        self.ws.connect()
        self.ws.run_forever()

    def close(self):
        self.ws.close()


def enable_http_debug():
    import logging
    import http.client
    http.client.HTTPConnection.debuglevel = 1
    logging.basicConfig()  # Initialize logging
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def main(argv):
    start_http_server(8000)
    parser = argparse.ArgumentParser()
    parser.add_argument("-host", help="The host to connect. Defaults to localhost on port 80",
                        default='192.168.4.10')
    parser.add_argument("-user", help="The login user name. Defaults to default user name", default='Default User')
    parser.add_argument("-passcode", help="The login password. Defaults to default password", default='robotics')
    parser.add_argument("-debug", help="Disable HTTP level debugging.", action='store_true', default='True')
    args = parser.parse_args()

    if args.debug:
        enable_http_debug()

    robcom = RobCom(args.host, args.user, args.passcode)

    while True:
        if robcom.subscribe():
            robcom.start_recv_events()


if __name__ == "__main__":
    main(sys.argv[1:])

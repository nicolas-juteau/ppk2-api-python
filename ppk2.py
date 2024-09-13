import time
import zmq

from serial.serialutil import SerialException
from ppk2_api.ppk2_api import PPK2_API

RECV_TIMEOUT_MS = 1000

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555

class MultiplePPK2FoundException(Exception):
    pass

class PPK2NotFoundException(Exception):
    pass

class PPK2AlreadyOpenException(Exception):
    pass

class PPK2TimeoutException(Exception):
    pass

class PPK2Server:
    __ppk2 = None
    __zctx = None
    __zs = None
    __silent = True

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, enable_power=True, silent=True):
        # Initialize commands and associated its handling function pointers
        # This cannot be done in static/class context otherwise class methods won't be recognized
        self.__commands = {
            'exit': self.__handle_exit,
            'measure': self.__handle_measure,
            'power on': self.__handle_power_on,
            'power off': self.__handle_power_off
        }

        self.__silent = silent

        self.__init_ppk2(enable_power)

        self.__zctx = zmq.Context()
        self.__zs = self.__zctx.socket(zmq.REP)
        self.__zs.setsockopt(zmq.RCVTIMEO, RECV_TIMEOUT_MS)
        self.__zs.bind(f"tcp://{host}:{port}")

        if not self.__silent:
            print(f"Listening for clients on {host}:{port}")

    def __init_ppk2(self, enable_power):
        ppk2s_connected = PPK2_API.list_devices()
        if len(ppk2s_connected) == 1:
            ppk2_port = ppk2s_connected[0][0]
            ppk2_serial = ppk2s_connected[0][1]
            if not self.__silent:
                print(f"Found PPK2 at {ppk2_port} with serial number {ppk2_serial}")
        elif len(ppk2s_connected) == 0:
            raise PPK2NotFoundException("ERROR: did not find any connected PPK2.")
        else:
            raise MultiplePPK2FoundException(f"ERROR: too many connected PPK2's: {ppk2s_connected}")

        try:
            self.__ppk2 = PPK2_API(ppk2_port, timeout=1, write_timeout=1, exclusive=True)
            self.__ppk2.get_modifiers()

            # In ampere meter mode, source voltage value does not seem to be considered at all.
            # However, it must be set otherwise the API won't let you starting to get measurements.
            self.__ppk2.set_source_voltage(5000)
            self.__ppk2.use_ampere_meter()  # set ampere meter mode

            if enable_power:
                self.__ppk2.toggle_DUT_power("ON")

            if not self.__silent:
                print("PPK2 initialization: OK")
        except SerialException:
            raise PPK2AlreadyOpenException("ERROR: could not open PPK2 COM port (already open?)")

    def __handle_exit(self):
        self.__zs.send_string("ok")
        return False

    def __handle_measure(self):
        self.__ppk2.start_measuring()

        # Wait until data is ready
        read_data = b'';
        while read_data == b'':
            read_data = self.__ppk2.get_data()

        samples, raw_digital = self.__ppk2.get_samples(read_data)
        json_obj = {"count": len(samples), "last": samples[-1], "average": sum(samples) / len(samples),
                    "unit": "uA"}

        if not self.__silent:
            print(f"Sending: {json_obj}")

        self.__zs.send_json(json_obj)
        
        self.__ppk2.stop_measuring()

        return True

    def __handle_power_on(self):
        self.__ppk2.toggle_DUT_power("ON")
        self.__zs.send_string("ok")

        return True

    def __handle_power_off(self):
        self.__ppk2.toggle_DUT_power("OFF")
        self.__zs.send_string("ok")

        return True

    def listen(self):
        listen = True

        while listen:
            try:
                msg = self.__zs.recv_string()

                # Try to execute command
                self.__commands[msg]()
            except KeyError:
                # Handle unrecognized command
                self.__zs.send_string("invalid")

                if not self.__silent:
                    print("Unknown request from client (ignored): " + msg)
            except KeyboardInterrupt:
                # Handle CTRL+C/CTRL+Z by user
                listen = False
            except zmq.error.Again:
                # zeromq recv timeout, just ignore and continue polling until exit or sigint is catched
                pass

        # Issuing stop_measuring() before exiting is mandatory, otherwise next session attempt will fail and the PPK
        # will have to be disconnected/reconnected
        self.__ppk2.stop_measuring()

        if not self.__silent:
            print("Exiting")

class PPK2Client:
    __zctx = None
    __zs = None

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.__zctx = zmq.Context()
        self.__zs = self.__zctx.socket(zmq.REQ)
        self.__zs.setsockopt(zmq.RCVTIMEO, RECV_TIMEOUT_MS)
        self.__zs.connect(f"tcp://{host}:{port}")

    def __send_msg(self, message):
        resp = ""
        
        try:
            self.__zs.send_string(message)
            resp = self.__zs.recv_json()
        except zmq.error.Again:
            raise PPK2TimeoutException("ERROR: did not receive response in a timely manner. Is server running?")

        return resp
    
    def measure(self):
        return self.__send_msg("measure")

    def enable_power(self, state):
        self.__send_msg("power on" if state else "power off")

    def close_server(self):
        self.__send_msg("exit")
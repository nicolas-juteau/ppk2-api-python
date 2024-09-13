import argparse
import sys
import ppk2

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555

parser = argparse.ArgumentParser(description='PPK2 server component')
parser.add_argument('--host', default=DEFAULT_HOST)
parser.add_argument('--port', type=int, default=DEFAULT_PORT)
parser.add_argument('--enable', action=argparse.BooleanOptionalAction)
parser.add_argument('--silent', action=argparse.BooleanOptionalAction)
args = parser.parse_args()

if not args.silent:
    print("*** Starting Nordic Power Profiler Kit II server component ***")

exit_code = 0

try:
    ppk2_server = ppk2.PPK2Server(host=args.host, port=args.port, enable_power=True, silent=args.silent)
    ppk2_server.listen()
except (ppk2.PPK2NotFoundException, ppk2.MultiplePPK2FoundException) as e:
    exit_code = 1
    if not args.silent:
        print(e)
except ppk2.PPK2AlreadyOpenException as e:
    if not args.silent:
        print(e)

sys.exit(exit_code)
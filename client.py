import argparse
import ppk2

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5555

parser = argparse.ArgumentParser(description='PPK2 client component')
parser.add_argument('--host', default=DEFAULT_HOST)
parser.add_argument('--port', type=int, default=DEFAULT_PORT)
parser.add_argument('--exit', action=argparse.BooleanOptionalAction)
parser.add_argument('--enable', action=argparse.BooleanOptionalAction)
args = parser.parse_args()

client = ppk2.PPK2Client(args.host, args.port)

try:
    if args.enable:
        client.enable_power(True)

    m = client.measure()
    print(m)
    print(f"Average current: {m['average']} {m['unit']}")
    
    if args.exit:
        client.close_server()
except ppk2.PPK2TimeoutException as e:
    print(e)
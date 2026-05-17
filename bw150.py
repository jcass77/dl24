#!/usr/bin/env python3
"""Read and control Atorch BW150/DL24P electronic load via Bluetooth SPP.

Connects directly via RFCOMM socket — no 'rfcomm' tool or separate terminal needed.

Usage:
    bw150.py                  # single status reading
    bw150.py --listen N       # stream N readings (1/sec)
    bw150.py --listen 0       # stream until Ctrl-C
    bw150.py --json           # output as JSON
    bw150.py --addr XX:XX:XX:XX:XX:XX  # specify MAC (default: 00:00:00:01:1C:FB)
"""

import argparse
import json
import signal
import socket
import sys
import time

DEFAULT_ADDR = '00:00:00:01:1C:FB'
RFCOMM_CHANNEL = 1
PACKET_LEN = 36
INIT_CMD = b'AT+BMDL24_BLE\r\n'


def parse_packet(pkt):
    """Parse a 36-byte ATorch DC meter status packet."""
    if len(pkt) < PACKET_LEN or pkt[0] != 0xFF or pkt[1] != 0x55 or pkt[2] != 0x01:
        return None

    voltage = int.from_bytes(pkt[4:7], 'big') / 10.0
    current = int.from_bytes(pkt[7:10], 'big') / 1000.0
    power = int.from_bytes(pkt[10:13], 'big') / 10.0
    energy_wh = int.from_bytes(pkt[13:17], 'big') / 100.0
    temp = int.from_bytes(pkt[24:26], 'big')
    hours = int.from_bytes(pkt[26:28], 'big')
    minutes = pkt[28]
    seconds = pkt[29]

    return {
        'voltage': voltage,
        'current': current,
        'power': power,
        'energy_wh': energy_wh,
        'temperature': temp,
        'duration': f'{hours}h {minutes:02d}m {seconds:02d}s',
        'duration_s': hours * 3600 + minutes * 60 + seconds,
    }


def connect(addr):
    """Open RFCOMM socket and send BW150 init command."""
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(10)
    sock.connect((addr, RFCOMM_CHANNEL))
    sock.sendall(INIT_CMD)
    time.sleep(1)
    # Drain any init response
    sock.setblocking(False)
    try:
        sock.recv(4096)
    except BlockingIOError:
        pass
    sock.setblocking(True)
    sock.settimeout(5)
    return sock


def read_packet(sock):
    """Read one complete status packet from the stream."""
    buf = b''
    while True:
        try:
            b = sock.recv(1)
        except socket.timeout:
            return None
        if not b:
            return None
        buf += b
        # Look for header in buffer
        idx = buf.find(b'\xff\x55')
        if idx >= 0:
            buf = buf[idx:]
            while len(buf) < PACKET_LEN:
                try:
                    chunk = sock.recv(PACKET_LEN - len(buf))
                except socket.timeout:
                    return None
                if not chunk:
                    return None
                buf += chunk
            return buf[:PACKET_LEN]


def format_status(status):
    """Format status as human-readable string."""
    return (
        f"V: {status['voltage']:6.1f}V  "
        f"I: {status['current']:6.3f}A  "
        f"P: {status['power']:6.1f}W  "
        f"E: {status['energy_wh']:7.2f}Wh  "
        f"T: {status['temperature']}°C  "
        f"t: {status['duration']}"
    )


def main():
    parser = argparse.ArgumentParser(description='BW150/DL24P electronic load reader')
    parser.add_argument('--addr', default=DEFAULT_ADDR, help=f'Bluetooth MAC (default: {DEFAULT_ADDR})')
    parser.add_argument('--listen', type=int, nargs='?', const=0, default=None,
                        help='Stream N readings (0=infinite)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    try:
        sock = connect(args.addr)
    except (OSError, socket.error) as e:
        print(f'Error connecting to {args.addr}: {e}', file=sys.stderr)
        sys.exit(1)

    count = 1 if args.listen is None else args.listen
    infinite = (args.listen == 0)
    read = 0

    try:
        while infinite or read < count:
            pkt = read_packet(sock)
            if pkt is None:
                print('Timeout waiting for data', file=sys.stderr)
                break
            status = parse_packet(pkt)
            if status is None:
                continue
            if args.json:
                print(json.dumps(status))
            else:
                print(format_status(status))
            read += 1
            sys.stdout.flush()
    finally:
        sock.close()


if __name__ == '__main__':
    main()

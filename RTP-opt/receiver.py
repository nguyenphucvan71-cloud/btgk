import argparse
import socket
import sys

from utils import PacketHeader, compute_checksum


def make_packet(pkt_type, seq_num, data=b''):
    header = PacketHeader(type=pkt_type, seq_num=seq_num, length=len(data), checksum=0)
    pkt_obj = header / data
    crc = compute_checksum(pkt_obj)
    header.checksum = crc
    return bytes(header / data)


def receiver(receiver_ip, receiver_port, window_size):
    """TODO: Listen on socket and print received message to sys.stdout."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    in_connection = False
    sender_addr = None
    expected_seq_num = 1
    buffer = {}

    while True:
        pkt, address = s.recvfrom(2048)
        if len(pkt) < 16:
            continue

        pkt_header = PacketHeader(pkt[:16])
        msg = pkt[16 : 16 + pkt_header.length]

        pkt_checksum = pkt_header.checksum
        pkt_header.checksum = 0
        computed_checksum = compute_checksum(pkt_header / msg)
        if pkt_checksum != computed_checksum:
            continue

        if pkt_header.type == 0:
            if not in_connection:
                in_connection = True
                sender_addr = address
                expected_seq_num = 1
                buffer.clear()
                ack_pkt = make_packet(3, 1, b'')
                s.sendto(ack_pkt, sender_addr)
            elif in_connection and address == sender_addr:
                ack_pkt = make_packet(3, 1, b'')
                s.sendto(ack_pkt, sender_addr)

        elif pkt_header.type == 2:
            if not in_connection or address != sender_addr:
                continue

            seq = pkt_header.seq_num
            if seq >= expected_seq_num + window_size:
                continue

            ack_pkt = make_packet(3, seq, b'')
            s.sendto(ack_pkt, sender_addr)

            if seq >= expected_seq_num:
                buffer[seq] = msg
                while expected_seq_num in buffer:
                    sys.stdout.buffer.write(buffer[expected_seq_num])
                    del buffer[expected_seq_num]
                    expected_seq_num += 1
                sys.stdout.buffer.flush()

        elif pkt_header.type == 1:
            if not in_connection or address != sender_addr:
                continue

            sys.stdout.buffer.flush()
            ack_pkt = make_packet(3, pkt_header.seq_num + 1, b'')
            s.sendto(ack_pkt, sender_addr)
            break

    s.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receiver_ip", help="The IP address of the host that receiver is running on"
    )
    parser.add_argument(
        "receiver_port", type=int, help="The port number on which receiver is listening"
    )
    parser.add_argument(
        "window_size", type=int, help="Maximum number of outstanding packets"
    )
    args = parser.parse_args()

    receiver(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
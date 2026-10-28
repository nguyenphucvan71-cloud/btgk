import argparse
import socket
import sys
import time

from utils import PacketHeader, compute_checksum


def make_packet(pkt_type, seq_num, data=b''):
    header = PacketHeader(type=pkt_type, seq_num=seq_num, length=len(data), checksum=0)
    pkt_obj = header / data
    crc = compute_checksum(pkt_obj)
    header.checksum = crc
    return bytes(header / data)


def sender(receiver_ip, receiver_port, window_size):
    """TODO: Open socket and send message from sys.stdin."""
    receiver_addr = (receiver_ip, receiver_port)

    raw_data = sys.stdin.buffer.read()
    max_chunk_size = 1456
    chunks = []
    for i in range(0, len(raw_data), max_chunk_size):
        chunks.append(raw_data[i:i + max_chunk_size])
    total_packets = len(chunks)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0.05)

    start_pkt = make_packet(0, 0, b'')
    s.sendto(start_pkt, receiver_addr)

    while True:
        try:
            ack_raw, _ = s.recvfrom(2048)
            ack_header = PacketHeader(ack_raw[:16])
            orig_checksum = ack_header.checksum
            ack_header.checksum = 0
            if compute_checksum(ack_header / ack_raw[16:]) == orig_checksum:
                if ack_header.type == 3 and ack_header.seq_num == 1:
                    break
        except socket.timeout:
            s.sendto(start_pkt, receiver_addr)

    base = 1
    next_to_send = 1
    timer_start = None

    while base <= total_packets:
        while next_to_send < base + window_size and next_to_send <= total_packets:
            pkt = make_packet(2, next_to_send, chunks[next_to_send - 1])
            s.sendto(pkt, receiver_addr)
            if base == next_to_send:
                timer_start = time.time()
            next_to_send += 1

        try:
            ack_raw, _ = s.recvfrom(2048)
            ack_header = PacketHeader(ack_raw[:16])
            orig_checksum = ack_header.checksum
            ack_header.checksum = 0
            if compute_checksum(ack_header / ack_raw[16:]) == orig_checksum:
                if ack_header.type == 3:
                    if ack_header.seq_num > base:
                        base = ack_header.seq_num
                        timer_start = time.time()
        except socket.timeout:
            pass

        if timer_start and (time.time() - timer_start >= 0.5):
            for seq in range(base, next_to_send):
                pkt = make_packet(2, seq, chunks[seq - 1])
                s.sendto(pkt, receiver_addr)
            timer_start = time.time()

    end_seq = total_packets + 1
    end_pkt = make_packet(1, end_seq, b'')
    s.sendto(end_pkt, receiver_addr)
    end_timer = time.time()

    while time.time() - end_timer < 0.5:
        try:
            ack_raw, _ = s.recvfrom(2048)
            ack_header = PacketHeader(ack_raw[:16])
            orig_checksum = ack_header.checksum
            ack_header.checksum = 0
            if compute_checksum(ack_header / ack_raw[16:]) == orig_checksum:
                if ack_header.type == 3 and ack_header.seq_num == end_seq + 1:
                    break
        except socket.timeout:
            continue

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

    sender(args.receiver_ip, args.receiver_port, args.window_size)


if __name__ == "__main__":
    main()
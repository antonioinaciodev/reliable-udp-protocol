import argparse
import random
import socket
import struct
import threading
import time
from collections import deque

def scramble_payload(payload: bytes, mode: str = "shuffle") -> bytes:
    if not payload: return payload
    if mode == "shuffle":
        lst = list(payload)
        random.shuffle(lst)
        return bytes(lst)
    elif mode == "xor":
        key = random.randrange(1, 256)
        return bytes([b ^ key for b in payload])
    elif mode == "bitflip":
        out = bytearray(payload)
        for _ in range(random.randint(1, 3)):
            i = random.randrange(len(out))
            bit = 1 << random.randrange(8)
            out[i] ^= bit
        return bytes(out)
    return payload

def maybe(delay_mean): 
    if delay_mean > 0: time.sleep(random.expovariate(1.0 / delay_mean))

class UDPRouter:
    def __init__(self, router_host, router_port,
                 sender_host, sender_port,
                 receiver_host, receiver_port,
                 p_corrupt_fwd, p_drop_fwd, p_dup_fwd,
                 p_reorder_fwd, delay_mean_fwd, scramble_mode_fwd,
                 p_drop_back, p_dup_back, delay_mean_back,
                 reorder_window):
        self.router_addr = (router_host, router_port)
        self.sender_addr = (sender_host, sender_port)
        self.receiver_addr = (receiver_host, receiver_port)
        self.sock_fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_back = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_fwd.bind(self.router_addr)
        self.sock_back.bind(("0.0.0.0", 9003)) # Roteador escuta ACKs na 9003
        self.p_corrupt_fwd = p_corrupt_fwd
        self.p_drop_fwd = p_drop_fwd
        self.p_dup_fwd = p_dup_fwd
        self.p_reorder_fwd = p_reorder_fwd
        self.delay_mean_fwd = delay_mean_fwd
        self.scramble_mode_fwd = scramble_mode_fwd
        self.p_drop_back = p_drop_back
        self.p_dup_back = p_dup_back
        self.delay_mean_back = delay_mean_back
        self.reorder_window = max(0, reorder_window)
        self.buffer_reorder = deque()
        self.lock = threading.Lock()
        self.running = True

    def stop(self):
        self.running = False
        self.sock_fwd.close()
        self.sock_back.close()

    def thread_forward(self):
        print(f"[Router] Escutando do emissor em {self.router_addr}, repassando para {self.receiver_addr}")
        while self.running:
            try: data, _ = self.sock_fwd.recvfrom(65535)
            except OSError: break
            if random.random() < self.p_drop_fwd:
                print("[Router→] DROP pacote")
                continue
            if random.random() < self.p_corrupt_fwd:
                data = data[:4] + scramble_payload(data[4:], self.scramble_mode_fwd)
                print("[Router→] CORRUPT payload")
            maybe(self.delay_mean_fwd)
            with self.lock:
                if self.reorder_window > 0 and random.random() < self.p_reorder_fwd:
                    self.buffer_reorder.append(data)
                    print("[Router→] HOLD pacote p/ reordenação")
                    continue
                if self.buffer_reorder and (len(self.buffer_reorder) >= self.reorder_window or random.random() < 0.5):
                    pkt = self.buffer_reorder.popleft()
                    self.sock_fwd.sendto(pkt, self.receiver_addr)
                    print("[Router→] REORDER envio de pacote antigo")
            self.sock_fwd.sendto(data, self.receiver_addr)
            if random.random() < self.p_dup_fwd:
                time.sleep(0.02)
                self.sock_fwd.sendto(data, self.receiver_addr)
                print("[Router→] DUP pacote")

    def thread_backward(self):
        print(f"[Router] Escutando ACKs do receptor na porta 9003")
        while self.running:
            try: data, _ = self.sock_back.recvfrom(65535)
            except OSError: break
            if random.random() < self.p_drop_back:
                print("[Router←] DROP ACK")
                continue
            maybe(self.delay_mean_back)
            self.sock_back.sendto(data, self.sender_addr)
            print(f"[Router←] ACK repassado: {data.decode(errors='ignore')}")
            if random.random() < self.p_dup_back:
                time.sleep(0.02)
                self.sock_back.sendto(data, self.sender_addr)
                print("[Router←] DUP ACK")

    def run(self):
        tf = threading.Thread(target=self.thread_forward, daemon=True)
        tb = threading.Thread(target=self.thread_backward, daemon=True)
        tf.start()
        tb.start()
        try:
            while self.running: time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            tf.join(1.0)
            tb.join(1.0)
            print("[Router] Encerrado.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roteador Intermediário UDP")
    parser.add_argument("--receiver-ip", required=True, help="IP do Celular/Receptor (ex: 192.168.1.10)")
    args = parser.parse_args()

    UDPRouter(
        router_host="0.0.0.0", router_port=9001,
        sender_host="127.0.0.1", sender_port=9000,
        receiver_host=args.receiver_ip, receiver_port=9002, 
        p_corrupt_fwd=0.05, p_drop_fwd=0.05, p_dup_fwd=0.05,
        p_reorder_fwd=0.2, delay_mean_fwd=0.02, scramble_mode_fwd="bitflip",
        p_drop_back=0.02, p_dup_back=0.03, delay_mean_back=0.01,
        reorder_window=3
    ).run()
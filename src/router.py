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
        lst = list(payload); random.shuffle(lst); return bytes(lst)
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

def parse_seq_list(spec: str):
    s = set()
    if not spec: return s
    for part in spec.split(','):
        part = part.strip()
        if not part: continue
        if '-' in part:
            a, b = part.split('-', 1)
            try:
                a_i = int(a); b_i = int(b)
                if a_i <= b_i: s.update(range(a_i, b_i + 1))
            except Exception: continue
        else:
            try: s.add(int(part))
            except Exception: continue
    return s

class UDPRouter:
    def __init__(self, receiver_ip, p_corrupt=0.05, p_drop=0.05, p_dup=0.05, p_reorder=0.2, 
                 reorder_window=3, delay_mean=0.02, scramble_mode="bitflip",
                 force_drop_seqs=None, force_corrupt_seqs=None, force_dup_seqs=None, force_reorder_seqs=None):
        
        self.router_addr = ("0.0.0.0", 9001)
        self.sender_addr = ("127.0.0.1", 9000)
        self.receiver_addr = (receiver_ip, 9002)
        
        self.sock_fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_back = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        self.sock_fwd.bind(self.router_addr)
        self.sock_back.bind(("0.0.0.0", 9003))
        
        self.p_corrupt = p_corrupt
        self.p_drop = p_drop
        self.p_dup = p_dup
        self.p_reorder = p_reorder
        self.reorder_window = max(0, reorder_window)
        self.delay_mean = delay_mean
        self.scramble_mode = scramble_mode
        
        self.buffer_reorder = deque()
        self.lock = threading.Lock()
        self.running = True
        self.interactive_mode = False
        
        # Sequências forçadas determinísticas
        self.force_drop_seqs = set(force_drop_seqs or [])
        self.force_corrupt_seqs = set(force_corrupt_seqs or [])
        self.force_dup_seqs = set(force_dup_seqs or [])
        self.force_reorder_seqs = set(force_reorder_seqs or [])

    # --- Controles em tempo de execução ---
    def add_forced(self, typ: str, seqs):
        if typ == 'drop': self.force_drop_seqs.update(seqs)
        elif typ == 'corrupt': self.force_corrupt_seqs.update(seqs)
        elif typ == 'dup': self.force_dup_seqs.update(seqs)
        elif typ == 'reorder': self.force_reorder_seqs.update(seqs)

    def remove_forced(self, typ: str, seqs):
        target = None
        if typ == 'drop': target = self.force_drop_seqs
        elif typ == 'corrupt': target = self.force_corrupt_seqs
        elif typ == 'dup': target = self.force_dup_seqs
        elif typ == 'reorder': target = self.force_reorder_seqs
        if target is not None:
            for s in seqs: target.discard(s)

    def clear_forced(self, typ: str = None):
        if typ is None:
            self.force_drop_seqs.clear(); self.force_corrupt_seqs.clear(); self.force_dup_seqs.clear(); self.force_reorder_seqs.clear()
        elif typ == 'drop': self.force_drop_seqs.clear()
        elif typ == 'corrupt': self.force_corrupt_seqs.clear()
        elif typ == 'dup': self.force_dup_seqs.clear()
        elif typ == 'reorder': self.force_reorder_seqs.clear()

    def show_forced(self):
        print("\nRegras Forçadas Atuais:")
        print(f"  DROP: {sorted(self.force_drop_seqs)}")
        print(f"  CORRUPT: {sorted(self.force_corrupt_seqs)}")
        print(f"  DUP: {sorted(self.force_dup_seqs)}")
        print(f"  REORDER: {sorted(self.force_reorder_seqs)}\n")

    def stop(self):
        self.running = False
        self.sock_fwd.close()
        self.sock_back.close()

    def thread_forward(self):
        print(f"[Router] Escutando pacotes, repassando para {self.receiver_addr[0]}")
        while self.running:
            try:
                data, _ = self.sock_fwd.recvfrom(65535)
            except OSError:
                break
            
            # Extrair seq num para exibição interativa
            seq = None
            if len(data) >= 2:
                try: seq = struct.unpack("!H", data[:2])[0]
                except Exception: seq = None

            if self.interactive_mode:
                print(f"\n{'='*50}")
                print(f"📦 PACOTE INTERCEPTADO: seq={seq if seq is not None else '?'}")
                print(f"{'='*50}")
                print("1 - Repassar normalmente")
                print("2 - PERDER pacote (Drop)")
                print("3 - CORROMPER bits")
                print("4 - DUPLICAR pacote")
                print("5 - Ligar Piloto Automático (Probabilidades)")
                
                escolha = input("Ação (1-5): ").strip()
                
                if escolha == '1':
                    print(f"[Router→] ENVIANDO seq={seq}")
                    self.sock_fwd.sendto(data, self.receiver_addr)
                elif escolha == '2':
                    print(f"[Router→] PERDENDO seq={seq}")
                    continue
                elif escolha == '3':
                    data_corrupted = data[:4] + scramble_payload(data[4:], self.scramble_mode)
                    print(f"[Router→] CORROMPENDO seq={seq}")
                    self.sock_fwd.sendto(data_corrupted, self.receiver_addr)
                elif escolha == '4':
                    print(f"[Router→] DUPLICANDO seq={seq}")
                    self.sock_fwd.sendto(data, self.receiver_addr)
                    time.sleep(0.02)
                    self.sock_fwd.sendto(data, self.receiver_addr)
                elif escolha == '5':
                    self.interactive_mode = False
                    print("[Router] Piloto Automático ATIVADO.")
                    self._process_packet_auto(data, seq)
                else:
                    print("Opção inválida! Enviando normalmente...")
                    self.sock_fwd.sendto(data, self.receiver_addr)
            else:
                self._process_packet_auto(data, seq)

    def _process_packet_auto(self, data, seq):
        if seq is not None and seq in self.force_drop_seqs:
            print(f"[Router→] FORCED DROP pacote seq={seq}"); return
        if random.random() < self.p_drop:
            print("[Router→] DROP pacote aleatório"); return

        if seq is not None and seq in self.force_corrupt_seqs:
            data = data[:4] + scramble_payload(data[4:], self.scramble_mode)
            print(f"[Router→] FORCED CORRUPT seq={seq}")
        elif random.random() < self.p_corrupt:
            data = data[:4] + scramble_payload(data[4:], self.scramble_mode)
            print("[Router→] CORRUPT payload aleatório")

        maybe(self.delay_mean)

        with self.lock:
            if seq is not None and seq in self.force_reorder_seqs:
                self.buffer_reorder.append(data)
                print(f"[Router→] FORCED HOLD seq={seq} para reordenar")
                return
            if self.reorder_window > 0 and random.random() < self.p_reorder:
                self.buffer_reorder.append(data)
                print("[Router→] HOLD pacote aleatório p/ reordenação")
                return
            if self.buffer_reorder and (len(self.buffer_reorder) >= self.reorder_window or random.random() < 0.5):
                pkt = self.buffer_reorder.popleft()
                self.sock_fwd.sendto(pkt, self.receiver_addr)
                print("[Router→] REORDER envio de pacote antigo")

        self.sock_fwd.sendto(data, self.receiver_addr)
        
        if seq is not None and seq in self.force_dup_seqs:
            time.sleep(0.02); self.sock_fwd.sendto(data, self.receiver_addr)
            print(f"[Router→] FORCED DUP seq={seq}")
        elif random.random() < self.p_dup:
            time.sleep(0.02); self.sock_fwd.sendto(data, self.receiver_addr)
            print("[Router→] DUP pacote aleatório")

    def thread_backward(self):
        print(f"[Router] Escutando ACKs do receptor na porta 9003")
        while self.running:
            try: data, _ = self.sock_back.recvfrom(65535)
            except OSError: break
            
            # Chance fixa pequena de perder ACK
            if random.random() < 0.02:
                print("[Router←] DROP ACK"); continue
                
            self.sock_back.sendto(data, self.sender_addr)
            print(f"[Router←] ACK repassado: {data.decode(errors='ignore')}")

    def run(self):
        tf = threading.Thread(target=self.thread_forward, daemon=True)
        tb = threading.Thread(target=self.thread_backward, daemon=True)
        tf.start(); tb.start()
        try:
            while self.running: time.sleep(0.2)
        except KeyboardInterrupt: pass
        finally:
            self.stop(); tf.join(1.0); tb.join(1.0)
            print("\n[Router] Encerrado.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Roteador UDP com Piloto Automático ou Interativo")
    parser.add_argument("--receiver-ip", required=True, help="IP do Celular/Receptor")
    parser.add_argument("--interactive", action="store_true", help="Pergunta o que fazer pacote por pacote")
    parser.add_argument("--cmd", action="store_true", help="Ativa terminal lateral para injetar erros em tempo real")
    args = parser.parse_args()

    router = UDPRouter(receiver_ip=args.receiver_ip)
    
    if args.interactive:
        router.interactive_mode = True
        print("\n" + "="*60)
        print("🎮 MODO INTERATIVO ATIVADO (Pausa a cada pacote)")
        print("="*60 + "\n")

    if args.cmd:
        def control_loop(rtr: UDPRouter):
            print("\n💻 Console de Comando (add drop 1,3-5 | remove corrupt 2 | show | clear)")
            while True:
                try: cmd = input('cmd> ').strip()
                except: break
                if not cmd: continue
                parts = cmd.split(None, 2)
                act = parts[0].lower()
                if act == 'show': rtr.show_forced(); continue
                if act == 'clear': rtr.clear_forced(parts[1] if len(parts) > 1 else None); continue
                if act in ('add', 'remove'):
                    if len(parts) < 3: print("Uso: add drop 5"); continue
                    seqs = parse_seq_list(parts[2])
                    if act == 'add': rtr.add_forced(parts[1], seqs); print(f"Adicionado!")
                    else: rtr.remove_forced(parts[1], seqs); print(f"Removido!")
                    continue
                print("Comando inválido.")

        threading.Thread(target=control_loop, args=(router,), daemon=True).start()

    router.run()
import socket
import threading
import struct
import time
import json

class GBNSender:
    def __init__(self, sender_addr=('127.0.0.1', 9000), router_addr=('127.0.0.1', 9001)):
        self.sender_addr = sender_addr
        self.router_addr = router_addr
        self.window_size = 5
        self.timeout = 0.5
        self.max_data_size = 50
        
        self.base = 0
        self.next_seq_num = 0
        self.buffer_pacotes = {}
        self.lock = threading.Lock()
        self.timer = None
        self.is_active = True
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(self.sender_addr)

    def calcular_checksum(self, dados: bytes) -> int:
        if len(dados) % 2 != 0:
            dados += b'\0'
        soma = 0
        for i in range(0, len(dados), 2):
            palavra = (dados[i] << 8) + dados[i + 1]
            soma += palavra
            while (soma >> 16) > 0: 
                soma = (soma & 0xFFFF) + (soma >> 16)
        return ~soma & 0xFFFF

    def criar_pacote(self, seq_num, dados: bytes):
        header = struct.pack("!H", seq_num) + dados
        checksum = self.calcular_checksum(header)
        return struct.pack("!HH", seq_num, checksum) + dados

    def start_timer(self):
        if self.timer: self.timer.cancel()
        self.timer = threading.Timer(self.timeout, self.handle_timeout)
        self.timer.start()

    def stop_timer(self):
        if self.timer: self.timer.cancel()
        self.timer = None

    def handle_timeout(self):
        if not self.is_active: return
        with self.lock:
            print(f"\n[Emissor] TIMEOUT! Reenviando da seq {self.base} até {self.next_seq_num - 1}")
            for i in range(self.base, self.next_seq_num):
                if i in self.buffer_pacotes:
                    self.sock.sendto(self.buffer_pacotes[i], self.router_addr)
            self.start_timer()

    def escutar_acks(self):
        while self.is_active:
            try:
                dados_ack, _ = self.sock.recvfrom(1024)
                ack_str = dados_ack.decode('utf-8', errors='ignore').replace("'", '"').strip()
                ack = json.loads(ack_str).get("ack_num")
                
                if ack is None: continue
                print(f"[Emissor] Recebeu ACK({ack})")

                with self.lock:
                    if ack >= self.base:
                        self.base = ack + 1
                        if self.base == self.next_seq_num:
                            self.stop_timer()
                        else:
                            self.start_timer()
            except Exception:
                break

    def iniciar_transmissao(self):
        print(f"[Emissor] Pronto na porta local {self.sender_addr[1]}")
        texto = input("Digite a mensagem para enviar: ")
        dados = texto.encode('utf-8')

        threading.Thread(target=self.escutar_acks, daemon=True).start()

        data_ptr = 0
        try:
            while data_ptr < len(dados) or self.base < self.next_seq_num:
                if self.next_seq_num < self.base + self.window_size and data_ptr < len(dados):
                    with self.lock:
                        bloco = dados[data_ptr:data_ptr + self.max_data_size]
                        data_ptr += len(bloco)
                        
                        pacote = self.criar_pacote(self.next_seq_num, bloco)
                        self.buffer_pacotes[self.next_seq_num] = pacote
                        self.sock.sendto(pacote, self.router_addr)
                        print(f"[Emissor] Pacote {self.next_seq_num} enviado.")
                        
                        if self.base == self.next_seq_num:
                            self.start_timer()
                        self.next_seq_num += 1
                else:
                    time.sleep(0.01)

            # Envia FIN
            with self.lock:
                pacote_fin = self.criar_pacote(self.next_seq_num, b'')
                self.buffer_pacotes[self.next_seq_num] = pacote_fin
                self.sock.sendto(pacote_fin, self.router_addr)
                print(f"[Emissor] FIN (seq {self.next_seq_num}) enviado.")
                
                if self.base == self.next_seq_num:
                    self.start_timer()
                self.next_seq_num += 1 

            while self.base < self.next_seq_num:
                time.sleep(0.01)

        finally:
            self.stop_timer()
            self.is_active = False
            self.sock.close()
            print("\n[Emissor] Envio concluído. Conexão encerrada.")

if __name__ == "__main__":
    GBNSender().iniciar_transmissao()
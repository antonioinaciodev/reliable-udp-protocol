# 📡 Reliable UDP Protocol (Go-Back-N)

## 📌 Sobre o Projeto
Este repositório contém a implementação construída do zero de um protocolo de transferência confiável de dados (RDT) utilizando o modelo **Go-Back-N (GBN)** sobre a camada de transporte **UDP** (que nativamente não oferece garantias de entrega).

O projeto foi desenvolvido como requisito prático para a disciplina de **Redes de Computadores** (Ciência da Computação - UFPI).

A arquitetura do sistema é composta por três agentes distintos:
1. **Sender (Python):** Fatia a mensagem de origem, calcula o *Checksum* de cada pacote, implementa a janela deslizante (tamanho 5) e gerencia *Timeouts* para disparar reenvios automáticos.
2. **Router (Python):** Um nó intermediário que atua como um simulador de rede hostil. Ele injeta aleatoriedade no tráfego, simulando perda de pacotes (drops), corrupção de bits, atrasos, duplicação e reordenação.
3. **Receiver (Java):** O destino final. Valida a integridade da carga (via *Checksum*), garante a ordem estrita sequencial dos pacotes e envia as confirmações (ACKs) de volta ao transmissor.

## 🛠️ Mecanismos Técnicos Implementados
* **Checksum de 16-bits:** Algoritmo matemático com tratamento de "vai-um" (carry) para detectar corrupção de payload durante o tráfego simulado.
* **Janela Deslizante (GBN):** Transmissão otimizada onde o emissor envia rajadas de pacotes antes de aguardar o ACK. Em caso de timeout, retrocede $N$ posições na janela.
* **Handshake de FIN:** Protocolo de finalização limpa e assíncrona, sinalizado por um payload de $0$ bytes.
* **Roteador Interativo:** Interface CLI que permite ao usuário injetar falhas na rede em tempo real (pacote a pacote) para testar a resiliência do protocolo.

## 🚀 Como Executar (Rede Local)

Nesta arquitetura, **nenhuma edição de código é necessária**. Os endereços de IP são passados dinamicamente via linha de comando (CLI).

### 1. Descobrindo os IPs
Para testar a comunicação entre dispositivos físicos (ex: Computador e Celular) na mesma rede Wi-Fi, você precisará de dois IPs:
* **IP do Computador (PC):** Descubra usando o comando `ipconfig` (Windows) ou `ifconfig` (Linux/Mac). *Ex: 192.168.1.10*
* **IP do Celular:** Geralmente encontrado nas configurações de Wi-Fi do aparelho. *Ex: 192.168.1.15*

---

### 🎮 Modo Demonstração / Interativo (Recomendado)
Este modo pausa o roteador a cada pacote recebido, permitindo que você escolha qual erro injetar na rede para ver o algoritmo Go-Back-N agindo para corrigir a falha.

Abra três terminais e inicie os nós nesta ordem:

**Nó 1: Roteador (No Computador)**
```bash
cd src
python router.py --receiver-ip <IP_DO_CELULAR> --interactive
```

**Nó 2: Receptor (No Celular via Jvdroid/Termux, ou em outro PC)**
```bash
cd src
javac Receiver.java
java Receiver <IP_DO_PC>
```

**Nó 3: Emissor (No Computador)**
*Nota: Usamos um timeout estendido (20s) para dar tempo de você ler e interagir com as opções do Roteador sem que a conexão caia.*
```bash
cd src
python sender.py --timeout 20
```

---

### 🤖 Modo Piloto Automático (Testes de Estresse)
Se quiser apenas ver o protocolo lidando com o caos automaticamente (probabilidades matemáticas de perda e corrupção), execute os comandos de forma padrão:

* **Roteador:** `python router.py --receiver-ip <IP_DO_CELULAR>`
* **Receptor:** `java Receiver <IP_DO_PC>`
* **Emissor:** `python sender.py`
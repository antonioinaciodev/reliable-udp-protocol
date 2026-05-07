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

## 🚀 Como Executar (Rede Local)

Nesta arquitetura, **nenhuma edição de código é necessária**. Os endereços de IP são passados dinamicamente via linha de comando (CLI).

### 1. Descobrindo os IPs
Para testar a comunicação entre dispositivos físicos (ex: Computador e Celular) na mesma rede Wi-Fi, você precisará de dois IPs:
* **IP do Computador (PC):** Descubra usando o comando `ipconfig` (Windows) ou `ifconfig` (Linux/Mac). *Ex: 192.168.1.10*
* **IP do Celular:** Geralmente encontrado nas configurações de Wi-Fi do aparelho. *Ex: 192.168.1.15*

### 2. Rodando os Nós
Abra três terminais distintos e inicie os componentes **exatamente nesta ordem**:

**Nó 1: Roteador (No Computador)**
Inicie o roteador informando para qual IP ele deve repassar os pacotes finais (o IP do celular).
```bash
cd src
python router.py --receiver-ip <IP_DO_CELULAR>
```

**Nó 2: Receptor (No Celular via Jvdroid/Termux, ou em outro PC)**
Compile o código Java e execute-o passando o IP do computador (onde o roteador está rodando) como argumento.
```bash
cd src
javac Receiver.java
java Receiver <IP_DO_PC>
```

**Nó 3: Emissor (No Computador)**
Como o emissor roda na mesma máquina que o roteador, ele utiliza a interface de loopback (`127.0.0.1`) automaticamente. Basta rodar:
```bash
cd src
python sender.py
```
*No console do Emissor, digite a string a ser transmitida e pressione Enter para iniciar o tráfego interativo.*
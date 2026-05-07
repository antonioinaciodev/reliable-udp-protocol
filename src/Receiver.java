import java.io.*;
import java.net.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public class Receiver {

    private static final int PORTA_RECEPTOR = 9002;     
    private static final int PORTA_ROTEADOR_ACK = 9003; 
    private static String ipRoteador; 

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("ERRO: Você precisa informar o IP do Roteador (PC).");
            System.out.println("Uso: java Receiver <IP_DO_PC>");
            return;
        }
        ipRoteador = args[0];

        DatagramSocket socket = null;
        ByteArrayOutputStream mensagem = new ByteArrayOutputStream();
        int expectedSeq = 0;

        try {
            socket = new DatagramSocket(PORTA_RECEPTOR);
            System.out.println("[Receptor] Aguardando pacotes na porta " + PORTA_RECEPTOR + "...");
            System.out.println("[Receptor] ACKs serão enviados para o Roteador em: " + ipRoteador + ":" + PORTA_ROTEADOR_ACK);

            byte[] buffer = new byte[1024];
            while (true) {
                DatagramPacket pacote = new DatagramPacket(buffer, buffer.length);
                socket.receive(pacote);
                byte[] dados = Arrays.copyOf(pacote.getData(), pacote.getLength());

                if (dados.length < 4) continue;

                ByteBuffer bb = ByteBuffer.wrap(dados);
                bb.order(ByteOrder.BIG_ENDIAN);

                int seqNum = bb.getShort() & 0xFFFF;
                int checksumRecebido = bb.getShort() & 0xFFFF;
                byte[] conteudo = Arrays.copyOfRange(dados, 4, dados.length);

                // Validar integridade
                byte[] checksumData = new byte[2 + conteudo.length];
                checksumData[0] = (byte) ((seqNum >> 8) & 0xFF);
                checksumData[1] = (byte) (seqNum & 0xFF);
                System.arraycopy(conteudo, 0, checksumData, 2, conteudo.length);
                
                if (checksumRecebido != calcularChecksum(checksumData)) {
                    System.out.println("[Receptor] ❌ Pacote " + seqNum + " corrompido! Enviando ACK do último confirmado.");
                    enviarAck(socket, expectedSeq - 1);
                    continue;
                }

                // Lógica de Janela (Go-Back-N)
                if (seqNum == expectedSeq) {
                    if (conteudo.length == 0) { // Pacote FIN real
                        enviarAck(socket, expectedSeq);
                        System.out.println("\n[Receptor] ✅ Fim da transmissão (FIN) recebido.");
                        break;
                    }
                    
                    mensagem.write(conteudo);
                    System.out.println("[Receptor] 📦 Pacote " + seqNum + " aceito.");
                    expectedSeq++;
                } else {
                    System.out.println("[Receptor] ⚠️ Fora de ordem (Esperado: " + expectedSeq + ", Recebido: " + seqNum + ")");
                }

                enviarAck(socket, expectedSeq - 1);
            }

            System.out.println("\n===== MENSAGEM FINALIZADA =====");
            System.out.println(new String(mensagem.toByteArray(), StandardCharsets.UTF_8));
            System.out.println("===============================");

        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            if (socket != null) socket.close();
        }
    }

    private static int calcularChecksum(byte[] dados) {
        if (dados.length % 2 != 0)
            dados = Arrays.copyOf(dados, dados.length + 1);
        int soma = 0;
        for (int i = 0; i < dados.length; i += 2) {
            int palavra = ((dados[i] & 0xFF) << 8) | (dados[i + 1] & 0xFF);
            soma += palavra;
            while ((soma >> 16) > 0) soma = (soma & 0xFFFF) + (soma >> 16);
        }
        return (~soma) & 0xFFFF;
    }

    private static void enviarAck(DatagramSocket socket, int ackNum) throws IOException {
        if (ackNum < 0) return; 
        String ackMsg = "{\"ack_num\":" + ackNum + "}";
        byte[] ackBytes = ackMsg.getBytes();
        DatagramPacket ackPacket = new DatagramPacket(
                ackBytes, ackBytes.length,
                InetAddress.getByName(ipRoteador), PORTA_ROTEADOR_ACK
        );
        socket.send(ackPacket);
        System.out.println("[Receptor] 📡 Enviou ACK(" + ackNum + ")");
    }
}
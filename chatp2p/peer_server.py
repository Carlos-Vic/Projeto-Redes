import socket
import threading
import logging
from peer_connection import PeerConnection

logger = logging.getLogger(__name__)

class PeerServer:
    def __init__(self, state):
        self.state = state  # Referência para o estado compartilhado
        self._server_socket = None  # Socket TCP do servidor
        self._rodando = threading.Event()  # Flag para indicar se o servidor está rodando
        self._server_thread = None  # Thread que aceita conexões inbound
        
    def start(self):
        # Inicia servidor TCP que aceita conexões inbound de outros peers
        porta = self.state.port  # Porta para escutar conexões P2P

        try:
            # Cria e configura socket TCP
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Cria socket TCP
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Permite reutilizar o endereço
            self._server_socket.bind(("0.0.0.0", porta))  # Liga o socket a todas as interfaces na porta especificada
            self._server_socket.listen(12)  # Começa a escutar conexões (máximo 12 conexões na fila)

            logger.info(f"[PeerServer] Servidor P2P escutando na porta {porta}")

            # Marca servidor como rodando e inicia thread de aceitação
            self._rodando.set()  # Marca o servidor como rodando
            self._server_thread = threading.Thread(target=self._aceitar_conexoes,
                                                   name="PeerServerThread",
                                                   daemon=True)

            self._server_thread.start()  # Inicia a thread de aceitação de conexões

        except Exception as e:
            logger.error(f"[PeerServer] Falha ao iniciar o servidor P2P: {e}")
            raise
        
    def stop(self): # Encerra o servidor P2P
        if not self._rodando.is_set():
            return # Já está parado
        
        logger.info("[PeerServer] Encerrando o servidor P2P...")
        self._rodando.clear() # Marca o servidor como não rodando
        
        if self._server_socket:
            try:
                self._server_socket.close() # Fecha o socket do servidor
            except Exception as e:
                pass
            
    def continua_rodando(self) -> bool: # Verifica se o servidor P2P está rodando
        return self._rodando.is_set()
    
    def _aceitar_conexoes(self):
        # Loop que aceita conexões entrantes e cria thread para cada uma
        while self._rodando.is_set():
            try:
                cliente_socket, endereco = self._server_socket.accept()  # Aceita nova conexão (bloqueante)
                logger.info(f"[PeerServer] Nova conexão recebida de {endereco}")

                # Cria thread dedicada para lidar com esta conexão
                threading.Thread(
                    target=self._handle_conexao,
                    args=(cliente_socket, endereco),
                    daemon=True
                ).start()

            except Exception as e:
                if self._rodando.is_set():
                    logger.error(f"[PeerServer] Erro ao aceitar conexão: {e}")
    
    def _handle_conexao(self, cliente_socket, endereco):
        # Lida com conexão entrante: espera HELLO, valida, faz handshake e inicia PeerConnection
        try:
            # Cria PeerConnection temporária com peer_id desconhecido (será atualizado após HELLO)
            temp_con = PeerConnection(
                sock = cliente_socket,
                peer_id_remoto = "unknown",
                state = self.state,
                foi_iniciado = False  # False = conexão inbound (você é servidor)
            )

            # Aguarda mensagem HELLO do peer remoto
            hello_msg = temp_con._recebe_msg()
            if not hello_msg or hello_msg.get("type") != "HELLO":
                logger.warning(f"[PeerServer] Mensagem HELLO inválida de {endereco}")
                cliente_socket.close()
                return

            # Extrai peer_id da mensagem HELLO
            peer_id_remoto = hello_msg.get("peer_id")
            if not peer_id_remoto:
                logger.warning(f"[PeerServer] Peer ID ausente na mensagem HELLO de {endereco}")
                cliente_socket.close()
                return

            # Atualiza peer_id na conexão temporária
            temp_con.peer_id_remoto = peer_id_remoto

            # Verifica se já existe conexão com esse peer (evita duplicatas/race conditions)
            if self.state.verifica_conexao(peer_id_remoto):
                logger.info(f"[PeerServer] Conexão já existe com {peer_id_remoto}")
                cliente_socket.close()
                return

            # Realiza handshake como receptor (envia HELLO_OK)
            if not temp_con.handshake_receptor(hello_msg):
                logger.warning(f"[PeerServer] Falha no handshake com {peer_id_remoto}")
                cliente_socket.close()
                return

            # Handshake bem-sucedido: adiciona conexão ao state e inicia threads
            self.state.adiciona_conexao(peer_id_remoto, temp_con)
            temp_con.start()  # Inicia threads de leitura/escrita

            logger.info(f"[PeerServer] Conexão estabelecida com {peer_id_remoto}")

        except Exception as e:
            logger.error(f"[PeerServer] Erro ao lidar com conexão de {endereco}: {e}")
            try:
                cliente_socket.close()
            except Exception:
                pass
            
import socket
import threading
import logging
from peer_connection import PeerConnection

logger = logging.getLogger(__name__)

class PeerServer:
    def __init__(self, state):
        self.state = state
        self._server_socket = None
        self._rodando = threading.Event()
        self._server_thread = None
        
    def start(self):
        porta = self.state.port # Porta para escutar conexões P2P
        
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Cria socket TCP
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Permite reutilizar o endereço
            self._server_socket.bind(("0.0.0.0", porta)) # Liga o socket a todas as interfaces na porta especificada
            self._server_socket.listen(12) # Começa a escutar conexões (máximo 12 conexões na fila)
            
            logger.info(f"[PeerServer] Servidor P2P escutando na porta {porta}") 
            
            self._rodando.set() # Marca o servidor como rodando
            self._server_thread = threading.Thread(target=self._aceitar_conexoes, 
                                                   name="PeerServerThread",
                                                   daemon=True)
            
            self._server_thread.start() # Inicia a thread de aceitação de conexões
            
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
    
    def _aceitar_conexoes(self): # Loop para aceitar conexões entrantes
        while self._rodando.is_set():
            try:
                cliente_socket, endereco = self._server_socket.accept() # Aceita nova conexão
                logger.info(f"[PeerServer] Nova conexão recebida de {endereco}")
                
                threading.Thread(
                    target=self._handle_conexao,
                    args=(cliente_socket, endereco),
                    daemon=True
                ).start() 
            
            except Exception as e:
                if self._rodando.is_set():
                    logger.error(f"[PeerServer] Erro ao aceitar conexão: {e}")
    
    def _handle_conexao(self, cliente_socket, endereco): # Lida com uma conexão entrante
        try:
            temp_con = PeerConnection( # Cria conexão temporária
                sock = cliente_socket,
                peer_id_remoto = "unknown",
                state = self.state,
                foi_iniciado = False
            )
            
            hello_msg = temp_con._recebe_msg() # Espera pela mensagem HELLO
            if not hello_msg or hello_msg.get("type") != "HELLO": # Verifica se é uma mensagem HELLO válida
                logger.warning(f"[PeerServer] Mensagem HELLO inválida de {endereco}")
                cliente_socket.close()
                return
            
            peer_id_remoto = hello_msg.get("peer_id") # Obtém o peer ID remoto da mensagem HELLO
            if not peer_id_remoto: # Verifica se o peer ID está presente
                logger.warning(f"[PeerServer] Peer ID ausente na mensagem HELLO de {endereco}")
                cliente_socket.close()
                return
            
            temp_con.peer_id_remoto = peer_id_remoto # Define o peer ID remoto na conexão temporária
            
            if self.state.verifica_conexao(peer_id_remoto): # Verifica se já existe conexão com esse peer ID
                logger.info(f"[PeerServer] Conexão já existe com {peer_id_remoto}")
                cliente_socket.close()
                return
            
            if not temp_con.handshake_receptor(hello_msg): # Handshake como receptor
                logger.warning(f"[PeerServer] Falha no handshake com {peer_id_remoto}")
                cliente_socket.close()
                return
            
            self.state.adiciona_conexao(peer_id_remoto, temp_con) # Adiciona a conexão no state
            
            temp_con.start() # Inicia as threads
            
            logger.info(f"[PeerServer] Conexão estabelecida com {peer_id_remoto}")
            
        except Exception as e: 
            logger.error(f"[PeerServer] Erro ao lidar com conexão de {endereco}: {e}")
            try:
                cliente_socket.close()
            except Exception:
                pass
            
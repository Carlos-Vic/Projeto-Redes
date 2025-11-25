import socket
import threading
import time
import logging
from typing import Dict, Any, List
from peer_server import PeerServer
from peer_connection import PeerConnection, PeerConnectionError
from rendezvous_connection import discover, RendezvousError
from message_router import MessageRouter

logger = logging.getLogger(__name__)

class P2PClient:
    def __init__(self, state):
        self.state = state
        self.peer_server = None
        self._rodando = threading.Event()
        self._thread_discover = None  
        
        
    def start(self):
        try:
            self.peer_server = PeerServer(self.state)
            self.peer_server.start()
            logger.debug(f"[P2PClient] PeerServer iniciado na porta {self.state.port}")
            # Instancia e registra o MessageRouter no state
            try:
                router = MessageRouter(self.state)
                self.state.set_message_router(router)
                # Registra callback padrão que imprime mensagens recebidas no console
                try:
                    router.register_receive_callback(lambda src, payload, meta: print(f"[{src}] {payload}"))
                except Exception:
                    logger.exception("[P2PClient] Erro ao registrar callback padrão do MessageRouter")

                logger.debug("[P2PClient] MessageRouter criado e registrado no state")
            except Exception:
                logger.exception("[P2PClient] Falha ao criar MessageRouter")
            
            self._rodando.set()
            
            self._thread_discover = threading.Thread(target=self._loop_discover, 
                                                    name="P2PClient_Discover",
                                                    daemon=True)
            self._thread_discover.start()
            logger.debug("[P2PClient] Loop de discover iniciada")
        
        except Exception as e:
            logger.error(f"[P2PClient] Erro ao iniciar PeerServer: {e}")
            raise
    
    def stop(self):
        if not self._rodando.is_set():
            return
        
        self._rodando.clear()
        logger.debug("[P2PClient] Parando P2PClient...")
        
        try:
            if self.peer_server:
                self.peer_server.stop()
                logger.debug("[P2PClient] PeerServer parado")
           
            thread_atual = threading.current_thread()
            
            if self._thread_discover and self._thread_discover.is_alive(): 
                if thread_atual != self._thread_discover: 
                    self._thread_discover.join(timeout=5)
                               
        except Exception as e:
            logger.error(f"[P2PClient] Erro ao parar thread de discover: {e}")
                
               
    
    def _loop_discover(self):
        intervalo = self.state.get_config("rendezvous", "discover_interval")
        
        while self._rodando.is_set():
            try:
                peers = discover(self.state)
                meu_peer_id = self.state.peer_id
                              
                for peer in peers:  
                    peer_id_remoto = f"{peer['name']}@{peer['namespace']}"
                    if peer_id_remoto == meu_peer_id:
                        continue
                    if not self.state.verifica_conexao(peer_id_remoto):
                        self.conectar_com_peer(peer)
                    
            except RendezvousError as e:
                logger.error(f"[P2PClient] Erro no discover automático {e}")

            time.sleep(intervalo)
                
    
    def conectar_com_peer(self, peer_info: Dict[str, Any]) -> bool:
        ip = peer_info.get("ip")
        porta = peer_info.get("port")
        peer_id_remoto = f"{peer_info['name']}@{peer_info['namespace']}"
        
        max_tentativas = self.state.get_config("peer_connection", "retry_attempts")
        backoff_base = self.state.get_config("peer_connection", "backoff_base")
        timeout = self.state.get_config("network", "connection_timeout")
        
        for tentativas in range(max_tentativas):
            try:
                logger.debug(f"[P2PClient] Tentando conectar com {peer_id_remoto} em {ip}:{porta} (tentativa {tentativas + 1}/{max_tentativas})")
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((ip, porta))
                conexao = PeerConnection(sock, peer_id_remoto, self.state, foi_iniciado=True)
                
                if not conexao.handshake_iniciador():
                    logger.warning(f"[P2PClient] Handshake falhou com {peer_id_remoto}")
                    sock.close()
                    continue
                
                self.state.adiciona_conexao(peer_id_remoto, conexao)     
                conexao.start()
                
                logger.info(f"[P2PClient] Conectado com sucesso a {peer_id_remoto}")    
                return True
            
            except Exception as e:
                logger.warning(f"[P2PClient] Falha ao conectar com {peer_id_remoto} (tentativa {tentativas + 1}/{max_tentativas}): {e}")
                
                if tentativas < max_tentativas - 1:
                    backoff = backoff_base ** tentativas
                    logger.info(f"[P2PClient] Aguardando {backoff}s antes de nova tentativa...")
                    time.sleep(backoff)
        logger.error(f"[P2PClient] Falha ao conectar com {peer_id_remoto} após {max_tentativas} tentativas.")
        return False                
                
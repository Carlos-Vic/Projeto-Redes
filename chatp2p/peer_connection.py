import socket
import json
import logging
import threading
import queue
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from keep_alive import KeepAlive

logger = logging.getLogger(__name__)

class PeerConnectionError(Exception): # Exceção base para erros de conexão entre peers
    pass

class PeerConnection:
    def __init__(self, sock: socket.socket, peer_id_remoto: str, state, foi_iniciado: bool):
        self.sock = sock
        self.peer_id_remoto = peer_id_remoto
        self.state = state
        self.foi_iniciado = foi_iniciado
        self.keep_alive = None
        
        # Extrair IP e porta remotos
        try:
            self.remoto_ip, self.remoto_porta = self.sock.getpeername()
        except Exception:
            self.remoto_ip, self.remoto_porta = "unknown", 0

        self._envia_queue: queue.Queue[Dict[str, Any]] = queue.Queue() # Fila para mensagens a serem enviadas (thread-safe)
        
        self._rodando = threading.Event() 
        self._rodando.set() # Flag para indicar se a conexão está ativa

        # Reserva espeço para threads de leitura e escrita
        self._thread_leitura: Optional[threading.Thread] = None
        self._thread_escrita: Optional[threading.Thread] = None
        
        self._socket_lock = threading.Lock() # Lock para operações de socket thread-safe
        
        timeout = state.get_config("network", "connection_timeout")
        sock.settimeout(timeout) # Define timeout para operações de socket
        
        logger.info(f"[PeerConnection] Criada conexão com {peer_id_remoto} ({self.remoto_ip}:{self.remoto_porta}) - Iniciador: {self.foi_iniciado}")
       
    
    def start(self): # Inicia as threads de leitura e escrita
        self._thread_leitura = threading.Thread(target=self._loop_de_leitura,
                                                name=f"PeerLeitura-{self.peer_id_remoto}",
                                                daemon=True)

        self._thread_escrita = threading.Thread(target=self._loop_de_escrita,
                                                name=f"PeerEscrita-{self.peer_id_remoto}",
                                                daemon=True)

        self._thread_leitura.start() # Inicia thread de leitura
        self._thread_escrita.start() # Inicia thread de escrita

        logger.debug(f"[PeerConnection] Threads de leitura e escrita iniciadas para {self.peer_id_remoto}")

        if self.foi_iniciado:
            self.keep_alive = KeepAlive(self, self.state)
            self.keep_alive.start() # Inicia o keep-alive se for iniciador da conexão
            logger.debug(f"[PeerConnection] KeepAlive iniciado para {self.peer_id_remoto}")
        
        
    def handshake_iniciador(self) -> bool: # Realiza o handshake como iniciador da conexão
        try:
            # Dicionário com a mensagem HELLO
            msg_hello = {
                "type": "HELLO",
                "peer_id": self.state.get_peer_info(),
                "version": "1.0",
                "features": ["ack", "metrics"],
                "ttl": 1
            }
            
            logger.debug(f"[PeerConnection] Enviando HELLO para {self.peer_id_remoto}")
            self._envia_direct_msg(msg_hello) # Envia mensagem HELLO
            
            # Aguarda resposta HELLO_OK
            resposta = self._recebe_msg()
            if not resposta: # Nenhuma resposta recebida
                logger.error(f"[PeerConnection] Nenhuma resposta recebida do peer {self.peer_id_remoto} durante handshake")
                return False
            if resposta.get("type") != "HELLO_OK": # Resposta inesperada
                logger.error(f"[PeerConnection] Resposta inesperada do peer {self.peer_id_remoto} durante handshake: {resposta}")
                return False
            
            logger.debug(f"[PeerConnection] Handshake bem sucedido com {self.peer_id_remoto}") # Handshake bem sucedido
            return True
        
        except PeerConnectionError as e:
            logger.error(f"[PeerConnection] Erro durante handshake com {self.peer_id_remoto}: {e}")
            return False
        
    def handshake_receptor(self, msg_hello: Dict[str, Any]) -> bool: # Realiza o handshake como receptor da conexão
        try:
            if msg_hello.get("type") != "HELLO":
                logger.error(f"[PeerConnection] Mensagem inválida recebida durante handshake de {self.peer_id_remoto}: {msg_hello}")
                return False
            
            msg_hello_ok = {
                "type": "HELLO_OK",
                "peer_id": self.state.get_peer_info(),	
                "version": "1.0",
                "features": ["ack", "metrics"],
                "ttl": 1
            }
            
            logger.debug(f"[PeerConnection] Enviando HELLO_OK para {self.peer_id_remoto}")
            self._envia_direct_msg(msg_hello_ok) # Envia mensagem HELLO_OK
            
            logger.info(f"[PeerConnection] Handshake bem sucedido com {self.peer_id_remoto}") # Handshake bem sucedido
            return True
        
        except PeerConnectionError as e:
            logger.error(f"[PeerConnection] Erro no handshake com {self.peer_id_remoto}: {e}")
            return False
        
    def envia_ping(self) -> str:      
        msg_id = str(uuid.uuid4()) # Gera um ID único para a mensagem
        
        msg_ping = {
            "type": "PING",
            "msg_id": msg_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "ttl": 1
        }
        
        self._envia_queue.put(msg_ping) # Coloca a mensagem na fila de envio
        logger.debug(f"[PeerConnection] Enviando PING para {self.peer_id_remoto}")
        return msg_id
    
    def _envia_pong(self, msg_ping: Dict[str, Any]): # Envia resposta PONG para um PING recebido
        msg_pong = {
            "type": "PONG",
            "msg_id": msg_ping.get("msg_id"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "ttl": 1
        }
        
        self._envia_queue.put(msg_pong)
        logger.debug(f"[PeerConnection] Enviando PONG para {self.peer_id_remoto}")
    
    def _processa_pong(self, msg_pong: Dict[str, Any]): # Processa uma mensagem PONG recebida
        if self.keep_alive:
            self.keep_alive.processa_pong(msg_pong)
        else:
            logger.debug(f"[PeerConnection] PONG recebido de {self.peer_id_remoto}: {msg_pong}")
        
    def envia_bye(self, reason: str = "Encerrando sessão"): # Envia mensagem BYE para encerrar a conexão com um peer
        # Dicionário com a mensagem BYE
        msg_bye = {
            "type": "BYE",
            "msg_id": str(uuid.uuid4()),
            "src": self.state.get_peer_info(),
            "dst": self.peer_id_remoto,
            "reason": reason,
            "ttl": 1
        }
        
        self._envia_queue.put(msg_bye)
        logger.debug(f"[PeerConnection] Enviando BYE para {self.peer_id_remoto}")
        
    def _envia_bye_ok(self, msg_bye: Dict[str, Any]): # Envia resposta BYE_OK para um BYE recebido
        logger.info(f"[PeerConnection] BYE recebido de {self.peer_id_remoto}: {msg_bye.get('reason')}")
        
        # Dicionário com a mensagem BYE_OK
        msg_bye_ok = {
            "type": "BYE_OK",
            "msg_id": msg_bye.get("msg_id"),
            "src": self.state.get_peer_info(),
            "dst": self.peer_id_remoto,
            "ttl": 1
        }
        
        try:
            self._envia_direct_msg(msg_bye_ok) # Envia mensagem BYE_OK
            logger.debug(f"[PeerConnection] Enviando BYE_OK para {self.peer_id_remoto}")
        except PeerConnectionError as e:
            logger.error(f"[PeerConnection] Erro ao enviar BYE_OK para {self.peer_id_remoto}: {e}")
        
        self.close() # Fecha a conexão após enviar BYE_OK
        
    def _processa_bye_ok(self, msg_bye_ok: Dict[str, Any]): # Processa uma mensagem BYE_OK recebida
        logger.info(f"[PeerConnection] BYE_OK recebido de {self.peer_id_remoto}")
        self.close() # Fecha a conexão após receber BYE_OK
        
    def close(self): # Fecha a conexão com o peer
        if not self._rodando.is_set():
            return # Já está fechado
        
        logger.info(f"[PeerConnection] Fechando conexão com {self.peer_id_remoto}")
        
        if self.keep_alive:
            self.keep_alive.stop() # Para o keep-alive se estiver ativo
        
        self._rodando.clear() # Marca a conexão como não rodando
        
        # Fechar o socket
        try:
            with self._socket_lock: 
                self.sock.close()
        except PeerConnectionError as e:
            logger.error(f"[PeerConnection] Erro ao fechar socket com {self.peer_id_remoto}: {e}")
        
        thread_atual = threading.current_thread() # Obtém a thread atual
        
        if self._thread_leitura and self._thread_leitura.is_alive(): #  Faz a verificação se a thread de leitura está viva antes de dar join
            if thread_atual != self._thread_leitura: # Evita deadlock se a thread atual for a de leitura
                self._thread_leitura.join(timeout=5) # Aguarda a thread de leitura encerrar
        
        if self._thread_escrita and self._thread_escrita.is_alive(): # Faz a verificação se a thread de escrita está viva antes de dar join
            if thread_atual != self._thread_escrita: # Evita deadlock se a thread atual for a de escrita
                self._thread_escrita.join(timeout=5) # Aguarda a thread de escrita encerrar
        
        self.state.remove_conexao(self.peer_id_remoto) # Remove a conexão do estado
        logger.info(f"[PeerConnection] Conexão com {self.peer_id_remoto} encerrada")
            
    def continua_ativo(self) -> bool: # Verifica se a conexão ainda está ativa
        return self._rodando.is_set()
    
    def _envia_direct_msg(self, msg: Dict[str, Any]): # Envia uma mensagem diretamente pelo socket sem fila
        try:
            msg_json = json.dumps(msg, ensure_ascii = False) # Converte o dicionário em JSON
            msg_bytes = (msg_json + "\n").encode('utf-8') # Adiciona nova linha e converte para bytes
            
            logger.debug(f"[PeerConnection] Enviando para {self.peer_id_remoto}: {msg.get('type')}") # Log de debug do envio

            tamanho_maximo = self.state.get_config("network", "max_msg_size") # Obtém o tamanho máximo permitido para mensagens
            if len(msg_bytes) > tamanho_maximo:
                raise PeerConnectionError(f"Mensagem excede tamanho máximo de {tamanho_maximo} bytes") # Verifica tamanho da mensagem
            
            with self._socket_lock: # Garante thread-safety no envio pelo socket
                self.sock.sendall(msg_bytes) # Envia os bytes pelo socket
        
        except socket.error as e: 
            raise PeerConnectionError(f"Erro ao enviar mensagem para {self.peer_id_remoto}: {e}")
        
    
    def _recebe_msg(self) -> Optional[Dict[str, Any]]: # Recebe uma mensagem do socket
        try:
            buffer = b''
            tamanho_maximo = self.state.get_config("network", "max_msg_size") # Obtém o tamanho máximo permitido para mensagens
            
            while b'\n' not in buffer:
                chunk = self.sock.recv(4096)
                if not chunk:
                    raise PeerConnectionError("Conexão fechada pelo peer")
                buffer += chunk

                if len(buffer) > tamanho_maximo:
                    raise PeerConnectionError(f"Mensagem recebida excede tamanho máximo de {tamanho_maximo} bytes")

            # Separa a primeira linha (até o \n) do resto do buffer
            primeira_linha, _, resto = buffer.partition(b'\n')
            msg_linha = primeira_linha.decode('utf-8').strip()
            msg = json.loads(msg_linha)
            
            logger.debug(f"[PeerConnection] Mensagem recebida de {self.peer_id_remoto}: {msg.get('type')}")
            
            return msg
            
        except socket.timeout:
            raise PeerConnectionError("Timeout ao receber mensagem do peer")
        except socket.error as e:
            raise PeerConnectionError(f"Erro ao receber mensagem do peer {self.peer_id_remoto}: {e}")
        except UnicodeDecodeError as e:
            raise PeerConnectionError(f"Erro ao decodificar mensagem do peer {self.peer_id_remoto}: {e}")
        
        
    def _loop_de_leitura(self): # Loop principal de leitura de mensagens do peer
        logger.debug(f"[PeerConnection] Thread de leitura iniciada para {self.peer_id_remoto}")
        
        while self._rodando.is_set():
            try:
                msg = self._recebe_msg()
                if msg:
                    self._processa_msg_recebida(msg)
                    
            except PeerConnectionError as e:
                logger.warning(f"[PeerConnection] Erro ao receber de {self.peer_id_remoto}: {e}")
                self.close()
                break
            
            except Exception as e:
                logger.error(f"[PeerConnection] Erro inesperado na leitura de {self.peer_id_remoto}: {e}")
                self.close()
                break
        
        logger.debug(f"[PeerConnection] Thread de leitura encerrada para {self.peer_id_remoto}")
        
    def _loop_de_escrita(self): # Loop principal de escrita de mensagens para o peer
        logger.debug(f"[PeerConnection] Thread de escrita iniciada para {self.peer_id_remoto}")
        
        while self._rodando.is_set():
            try:
                try:
                    msg = self._envia_queue.get(timeout=1) # Aguarda mensagem na fila com timeout
                except queue.Empty:
                    continue
                
                self._envia_direct_msg(msg) # Envia a mensagem diretamente pelo socket
            
            except PeerConnectionError as e:
                logger.warning(f"[PeerConnection] Erro ao enviar para {self.peer_id_remoto}: {e}")
                self.close()
                break
            
            except Exception as e:
                logger.error(f"[PeerConnection] Erro inesperado na escrita para {self.peer_id_remoto}: {e}")
                self.close()
                break
            
        logger.debug(f"[PeerConnection] Thread de escrita encerrada para {self.peer_id_remoto}")
        
        
    def _processa_msg_recebida(self, msg: Dict[str, Any]):
        
        msg_type = msg.get("type")
        
        try:
            if msg_type == "PING":
                self._envia_pong(msg)
            elif msg_type == "PONG":
                self._processa_pong(msg)
            elif msg_type == "BYE":
                self._envia_bye_ok(msg)
            elif msg_type == "BYE_OK":
                self._processa_bye_ok(msg)
            elif msg_type == "SEND":
                self._processa_send(msg)
            elif msg_type == "ACK":
                self._processa_ack(msg)
            elif msg_type == "PUB":
                self._processa_pub(msg)
            else:
                logger.warning(f"[PeerConnection] Mensagem desconhecida recebida de {self.peer_id_remoto}: {msg}")
                
        except Exception as e:
            logger.error(f"[PeerConnection] Erro ao processar mensagem de {self.peer_id_remoto}: {e}")


    # Public API para enfileirar mensagens (usado por MessageRouter)
    def enqueue_msg(self, msg: Dict[str, Any]):
        """Coloca mensagem na fila de envio (thread-safe)."""
        self._envia_queue.put(msg)

    def _processa_send(self, msg: Dict[str, Any]):
        """Processa uma mensagem SEND recebida: entrega ao router/app e
        envia ACK se necessário (delegando ao MessageRouter se existir)."""
        try:
            router = self.state.get_message_router()
            if router:
                router.process_incoming(msg, self)
                return

            # Fallback: entregar localmente e enviar ACK se necessário
            src = msg.get("src")
            payload = msg.get("payload")
            logger.info(f"[PeerConnection] SEND recebido de {src}: {payload}")

            if msg.get("require_ack"):
                ack = {
                    "type": "ACK",
                    "msg_id": msg.get("msg_id"),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "src": self.state.get_peer_info(),
                    "dst": src,
                    "ttl": 1,
                }
                self.enqueue_msg(ack)

        except Exception:
            logger.exception("[PeerConnection] Erro ao processar SEND")

    def _processa_ack(self, msg: Dict[str, Any]):
        try:
            router = self.state.get_message_router()
            if router:
                router.process_incoming(msg, self)
            else:
                logger.info(f"[PeerConnection] ACK recebido: {msg}")
        except Exception:
            logger.exception("[PeerConnection] Erro ao processar ACK")

    def _processa_pub(self, msg: Dict[str, Any]):
        try:
            router = self.state.get_message_router()
            if router:
                router.process_incoming(msg, self)
                return

            src = msg.get("src")
            payload = msg.get("payload")
            logger.info(f"[PeerConnection] PUB recebido de {src}: {payload}")
        except Exception:
            logger.exception("[PeerConnection] Erro ao processar PUB")
        
        
        
        
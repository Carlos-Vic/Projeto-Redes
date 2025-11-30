import threading
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class KeepAlive:
    def __init__(self, conexao, state):
        self.conexao = conexao
        self.state = state
        self._falhas = 0
        self._pings_pendentes = {}
        self._rodando = threading.Event()
        self._thread_keep_alive = None
        self._rtts = []  # Armazena os últimos RTTs (em ms)
        self._max_rtts = 10  # Mantém apenas os últimos 10 RTTs      
        
    def start(self):
        try:
            self._rodando.set()
            
            self._thread_keep_alive = threading.Thread(
                target=self._loop_ping,
                name=f"KeepAlive-{self.conexao.peer_id_remoto}",
                daemon=True
            )
            self._thread_keep_alive.start()
            
            logger.debug(f"[KeepAlive] KeepAlive iniciado para {self.conexao.peer_id_remoto}")
        
        except Exception as e:
            logger.error(f"[KeepAlive] Falha ao iniciar KeepAlive para {self.conexao.peer_id_remoto}: {e}")
            raise
        
    
    def stop(self):
        if not self._rodando.is_set():
          return # Já está parado

        self._rodando.clear() # Sinaliza para parar o loop de ping
        logger.debug(f"[KeepAlive] Encerrando KeepAlive para {self.conexao.peer_id_remoto}...")

        thread_atual = threading.current_thread() # Obtém a thread atual
 
        if self._thread_keep_alive and self._thread_keep_alive.is_alive(): # Verifica se a thread de keep-alive está ativa
            if thread_atual != self._thread_keep_alive: # Evita que uma thread tente se juntar a si mesma
                self._thread_keep_alive.join(timeout=5) # Aguarda a thread terminar com timeout
    
    
    
    def _loop_ping(self):
        ping_interval = self.state.get_config("keepalive", "ping_interval") # Pega configuração de intervalo de ping no json
        max_falhas = self.state.get_config("keepalive", "max_ping_failures") # Pega configuração de falhas máximas no json
        
   
        while self._rodando.is_set():
            try:
                msg_id = self.conexao.envia_ping() # Envia ping e obtém o ID da mensagem
                tempo_agora = time.time() # Marca o tempo do envio do ping
                self._pings_pendentes[msg_id] = tempo_agora # Armazena o ping pendente com o timestamp
                logger.debug(f"[KeepAlive] Ping enviado para {self.conexao.peer_id_remoto}") 
                
                time.sleep(ping_interval) # Aguarda o intervalo de ping antes de enviar o próximo
                
                if msg_id in self._pings_pendentes: # Verifica se o ping ainda está pendente (não respondido)
                    self._falhas += 1 # Incrementa o contador de falhas
                    logger.warning(f"[KeepAlive] Ping não respondido de {self.conexao.peer_id_remoto}. Falhas: {self._falhas}")
                    
                    if self._falhas >= max_falhas: # Verifica se o número de falhas atingiu o máximo permitido
                        logger.error(f"[KeepAlive] Máximo de falhas atingido para {self.conexao.peer_id_remoto}. Encerrando conexão.")
                        self.conexao.close() # Encerra a conexão
                        break
                else:
                    self._falhas = 0 # Reseta o contador de falhas se o ping foi respondido
            
            except Exception as e:
                logger.error(f"[KeepAlive] Erro no loop de ping para {self.conexao.peer_id_remoto}: {e}")
                
    def processa_pong(self, msg_pong):
        msg_id = msg_pong.get("msg_id") # Extrai o ID da mensagem do pong recebido

        try:
            if msg_id in self._pings_pendentes: # Verifica se o pong corresponde a um ping pendente
                tempo_envio = self._pings_pendentes[msg_id] # Obtém o tempo de envio do ping
                rtt = (time.time() - tempo_envio) * 1000  # RTT em milissegundos
                self._pings_pendentes.pop(msg_id) # Remove o ping pendente
                self._falhas = 0  # Reseta o contador de falhas

                # Armazena o RTT (mantém apenas os últimos N)
                self._rtts.append(rtt)
                if len(self._rtts) > self._max_rtts:
                    self._rtts.pop(0)

                logger.debug(f"[KeepAlive] Pong recebido de {self.conexao.peer_id_remoto}. RTT: {rtt:.2f} ms")
            else:
                # Apenas loga se o msg_id do pong não for reconhecido
                logger.info(f"[KeepAlive] Pong recebido com msg_id desconhecido de {self.conexao.peer_id_remoto}")

        except Exception as e:
            logger.error(f"[KeepAlive] Erro ao processar pong de {self.conexao.peer_id_remoto}: {e}")

    def get_rtt_medio(self):
        """Retorna o RTT médio dos últimos pings (em ms)"""
        if not self._rtts:
            return None
        return sum(self._rtts) / len(self._rtts)

    def get_quantidade_pings(self):
        """Retorna a quantidade de RTTs armazenados"""
        return len(self._rtts)   
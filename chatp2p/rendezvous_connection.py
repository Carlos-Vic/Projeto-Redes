import socket
import json
import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Exception base para erros de comunicação com o servidor
class RendezvousError(Exception):
    pass

# Erro retornado pelo servidor (para tratamento específico do tipo de erro)
class RendezvousServerErro(RendezvousError):
    def __init__(self, error_type: str, message: str = ""):
        self.error_type = error_type
        self.message = message
        super().__init__(f"Rendezvous erros: {error_type} - {message}")
        
# Erro de conexão TCP com o servidor (para permitir retry em erros de rede e não em erros lógicos)
class RendezvousConnectionError(RendezvousError):
    pass


def _envia_comando(host: str, port: int, command: Dict[str, Any], timeout: int = 10):
    sock = None
    try:
        comando_json = json.dumps(command, ensure_ascii=False) # Converte o comando de dicionário pra json
        comando_bytes = (comando_json + "\n").encode("utf-8") # Adiciona newline e converte para bytes para ser enviado pelo socket
        
        if len(comando_bytes) > 32768:
            raise RendezvousError(f"Comando excede 32 KB: {len(comando_bytes)} bytes") # Erro se o comando for muito grande
        
        logger.debug(f"[Rendezvous] Conectando a {host}:{port}") # Registra log de debug
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Cria socket TCP
        sock.settimeout(timeout) # Define timeout para operações de socket (padrão 10 segundos)
        
        try:
            sock.connect((host, port)) # Tenta conectar ao servidor
        except socket.timeout:
            raise RendezvousConnectionError("Timeout ao conectar ao servidor")
        except socket.error as e:
            raise RendezvousConnectionError(f"Erro ao conectar ao servidor: {e}")
        
        
        try:
            sock.sendall(comando_bytes) # Envia o comando completo
        except socket.timeout:
            raise RendezvousConnectionError("Timeout ao enviar comando para o servidor")
        except socket.error as e:
            raise RendezvousConnectionError(f"Erro ao enviar comando para o servidor: {e}")

        resposta_servidor = b'' # Buffer para armazenar a resposta do servidor
        try:
            while b'\n' not in resposta_servidor: # Loop para receber bytes no buffer até encontrar newline
                chunk = sock.recv(4096) # Recebe até 4096 bytes (Pode mudar no futuro, usei 4096 como valor pq vi na internet :P)
                if not chunk: # Se o chunk estiver vazio, a conexão foi fechada
                    raise RendezvousConnectionError("Conexão fechada pelo servidor antes de receber a resposta completa")
                resposta_servidor += chunk # Adiciona os bytes recebidos ao buffer
                #print(resposta_servidor) # DEBUG para ver qual resposta ta chegando (lembrar de tirar depois)
            
        except socket.timeout: # Timeout ao receber dados
            raise RendezvousConnectionError("Timeout ao receber resposta do servidor")
        except socket.error as e:
            raise RendezvousConnectionError(f"Erro ao receber resposta do servidor: {e}")
        
        try:
            resposta_linha = resposta_servidor.decode("utf-8").strip() # Passa os bytes do buffer recebidos para string e remove espaços em branco
            resposta_json = json.loads(resposta_linha) # Converte a resposta de String pra JSON
            logger.debug(f"[Rendezvous] Resposta recebida: {resposta_json}") # Registra no log a resposta recebida
            
        except json.JSONDecodeError as e:
            raise RendezvousError(f"Erro ao converter a resposta do servidor: {e}")
        
        if resposta_json.get('status') == 'ERROR': # Se o status da resposta for erro, levanta exceção específica
            # O servidor costuma retornar o detalhe do erro em 'message' (ex: "bad_namespace").
            # Alguns clientes/implementações podem usar 'error' — aceite ambos.
            error_msg = resposta_json.get('message') or resposta_json.get('error') or 'unknown'
            # Use error_msg como tipo/descrição para facilitar logs/CLI
            raise RendezvousServerErro(error_msg, resposta_json.get('details', ''))
        
        #print(resposta_json)  # DEBUG para ver a resposta JSON completa (lembrar de tirar depois)
        return resposta_json # retorna a resposta JSON do servidor
    
    # Garante que o socket será fechado no final
    finally:
        if sock:
            try:
                sock.close()
                logger.debug(f"[Rendezvous] Conexão fechada")
            except Exception:
                pass

def register(state, retry: bool = True) -> Dict[str, Any]:
    # Obtém as configurações no state
    host = state.get_config("rendezvous", "host")
    porta = state.get_config("rendezvous", "port")
    timeout = state.get_config("network", "connection_timeout")
    
    # Define o TTL padrão (7200) se usuário não especificou
    if state.ttl is None:
        ttl = 7200
    else:
        ttl = state.ttl
          
    # dicionário com o comando REGISTER
    comando = {
        "type": "REGISTER",
        "peer_id": state.get_peer_info(),
        "name": state.name,
        "namespace": state.namespace,
        "port": state.port,
        "ttl": ttl
    }
    
    # Obtém as configurações de retry
    max_tentativas = state.get_config("rendezvous", "register_retry_attempts") # Número máximo de tentativas
    backoof_base = state.get_config("rendezvous", "register_backoff_base") # Base do backoff exponencial
        
    ultima_excecao = None

    for tentativas in range(max_tentativas): # Loop de tentativas
        try:
            logger.debug(f"[Rendezvous] Tentando REGISTER (tentativa {tentativas + 1}/{max_tentativas})") # Log de debug
            resposta = _envia_comando(host, porta, comando, timeout) # Envia o comando REGISTER e espera a resposta

            # Se chegou aqui, o REGISTER foi bem sucedido
            # Atualiza o state com o TTL e timestamp confirmados pelo servidor
            state.ttl_recebido = resposta.get('ttl')
            state.timestamp_registro = time.time()

            logger.info(f"[Rendezvous] REGISTER bem sucedido {state.peer_id}")
            logger.info(f"[Rendezvous] Peer registrado em {resposta.get('ip')}:{resposta.get('port')} com TTL {resposta.get('ttl')} segundos")
            return resposta # Retorna a resposta do servidor

        except RendezvousServerErro as e:
            # Erro lógico retornado pelo servidor (por exemplo: bad_namespace, bad_name).
            # Não faz sentido retryar: informe imediatamente.
            logger.error(f"[Rendezvous] REGISTER recebeu erro do servidor: {e}")
            raise

        except RendezvousConnectionError as e:
            # Erros de rede/timeouts: aplicar retry/backoff
            ultima_excecao = e
            logger.warning(f"[Rendezvous] REGISTER falhou (tentativa {tentativas + 1}/{max_tentativas}): {e}")

            if tentativas < max_tentativas - 1: # Se não for a ultima tentativa, aguarda o backoff antes de tentar novamente
                backoff = backoof_base ** tentativas # Calcula o tempo de backoff exponencial
                logger.info(f"[Rendezvous] Aguardando {backoff}s antes de nova tentativa...")
                time.sleep(backoff) # Aguarda o tempo de backoff antes de tentar novamente

    logger.error(f"[Rendezvous] REGISTER falhou após {max_tentativas} tentativas.") # Registra erro final
    if ultima_excecao:
        raise ultima_excecao # Lança a última exceção capturada
    else:
        raise RendezvousError("REGISTER falhou: nenhuma tentativa foi executada")

def discover(state, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
    # Obtém as configurações no state
    host = state.get_config("rendezvous", "host")
    porta = state.get_config("rendezvous", "port")
    timeout = state.get_config("network", "connection_timeout")
    
    # dicionário com o comando DISCOVER
    comando = {
        "type": "DISCOVER"
    } 
    if namespace:
        comando["namespace"] = namespace # Adiciona o namespace ao comando se fornecido
        
    try:
        logger.debug(f"[Rendezvous] Executand DISCOVER (namespace = {namespace or '*'})") # Log de debug
        resposta = _envia_comando(host, porta, comando, timeout) # Envia o comando DISCOVER e espera a resposta
        
        peers = resposta.get("peers", []) # Obtém a lista de peers da resposta
        logger.info(f"[Rendezvous] DISCOVER retornou {len(peers)} peers")
        
        return peers # Retorna a lista de peers encontrados
    
    except RendezvousError as e: # Erro 
        logger.error(f"[Rendezvous] DISCOVER falhou: {e}")
        raise

def unregister(state) -> Dict[str, Any]:
    # Obtém as configurações no state
    host = state.get_config("rendezvous", "host")
    porta = state.get_config("rendezvous", "port")
    timeout = state.get_config("network", "connection_timeout")
    
    # dicionário com o comando UNREGISTER
    comando = {
        "type": "UNREGISTER",
        "namespace": state.namespace,
        "name": state.name,
        "port": state.port
    }
    
    try:
        logger.debug(f"[Rendezvous] Executando UNREGISTER") # Log de debug
        resposta = _envia_comando(host, porta, comando, timeout) # Envia o comando UNREGISTER e espera a resposta
        
        logger.info(f"[Rendezvous] UNREGISTER bem sucedido para {state.peer_id}")
        return resposta # Retorna a resposta do servidor
    
    except RendezvousError as e: # Erro
        logger.error(f"[Rendezvous] UNREGISTER falhou: {e}")
        raise
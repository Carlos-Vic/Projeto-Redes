import socket
import json
import logging
from typing import Dict, Any, Optional, Any

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
                print(resposta_servidor) # DEBUG para ver qual resposta ta chegando (lembrar de tirar depois)
            
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
            error_type = resposta_json.get('error', 'unknown') # Pega o tipo de erro retornado pelo servidor
            error_msg = resposta_json.get('message', '') # Pega a mensagem de erro retornada pelo servidor
            raise RendezvousServerErro(error_type, error_msg)
        
        print(resposta_json)  # DEBUG para ver a resposta JSON completa (lembrar de tirar depois)
        return resposta_json # retorna a resposta JSON do servidor
    
    # Garante que o socket será fechado no final
    finally:
        if sock:
            try:
                sock.close()
                logger.debug(f"[Rendezvous] Conexão fechada")
            except Exception:
                pass
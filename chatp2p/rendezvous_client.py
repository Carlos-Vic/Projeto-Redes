#-- arquivo rendezvous_client.py --
import socket
import json
import logging
from typing import Dict, Any

log = logging.getLogger(__name__)

# Classe para erros específicos do Rendezvous
class RendezvousError(Exception):
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code
class RendezvousClient:
    # Construtor que inicializa o cliente com o endereço do servidor e o tamanho máximo da mensagem
    def __init__(self, server_host: str, server_porta: int):
        self.server_endereco = (server_host, server_porta) # tupla para endereço do servidor
        self.tamanho_max  = 32768  # 32 KiB
    
    # Método privado para enviar e receber requisições
    def _envia_e_recebe_requisicao(self, requisicao: Dict[str, Any]):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(self.server_endereco) # inicia conexão 
            log.debug(f"Conexão TCP com o servidor estabelecida")
            
            mensagem = json.dumps(requisicao).encode('utf-8') + b'\n' # converte a requisição para bytes e adiciona newline
            sock.sendall(mensagem) # envia a requisição
            log.debug(f"Requisição enviada: {requisicao}")
            
            resposta = sock.recv(self.tamanho_max) # recebe a resposta com o tamanho máximo definido de 32 KiB
            if not resposta:
                raise RendezvousError("Nenhuma resposta recebida do servidor.")
            
            resposta_str = resposta.decode('utf-8').strip() # decodifica e remove espaços em branco
            resposta_json = json.loads(resposta_str) # converte para dicionário
            log.debug(f"Resposta recebida: {resposta_json}")
            
            if resposta_json.get("status") == "ERROR":
                error_msg = resposta_json.get("error")
                raise RendezvousError(f"Erro do servidor: {error_msg}", error_code=error_msg)
            
        return resposta_json
                                   
        
    """ 
    Métodos públicos para registrar, descobrir e desregistrar peers 
    """	 
    def register(self, namespace: str, name: str, port: int, ttl: int = None):
        requisicao = {
            "type": "REGISTER",
            "namespace": namespace,
            "name": name,
            "port": port
        }
        if ttl is not None:
            requisicao["ttl"] = ttl
        return self._envia_e_recebe_requisicao(requisicao)
    
    def discover(self, namespace: None):
        requisicao = {
            "type": "DISCOVER",        
        }
        if namespace is not None:
            requisicao["namespace"] = namespace
        return self._envia_e_recebe_requisicao(requisicao)
    
    def unregister(self, namespace: str, name: None, port: None):
        requisicao = {
            "type": "UNREGISTER",
            "namespace": namespace,
        }
        if name is not None:
            requisicao["name"] = name
        if port is not None:
            requisicao["port"] = port
        return self._envia_e_recebe_requisicao(requisicao)
        
#-- arquivo rendezvous_client.py --

import socket
import json
from typing import Dict, Any

class RendezvousClient:
    # Construtor que inicializa o cliente com o endereço do servidor e o tamanho máximo da mensagem
    def __init__(self, server_host: str, server_porta: int):
        self.server_endereco = (server_host, server_porta) # tupla para endereço do servidor
        self.tamanho_max  = 32768  # 32 KiB
    
    # Método privado para enviar e receber requisições
    def _envia_e_recebe_requisicao(self, requisicao: Dict[str, Any]):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(self.server_endereco) # inicia conexão 
            
            mensagem = json.dumps(requisicao).encode('utf-8') + b'\n' # converte a requisição para bytes e adiciona newline
            sock.sendall(mensagem) # envia a requisição
            
            resposta = sock.recv(self.tamanho_max) # recebe a resposta com o tamanho máximo definido de 32 KiB
            if not resposta:
                return {"status": "ERRO", "message": "Nenhuma resposta do servidor"} # mensagem de erro se não houver resposta
            
            resposta_str = resposta.decode('utf-8').strip() # decodifica e remove espaços em branco
            return json.loads(resposta_str) # converte de volta para dicionário                   
        
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
    
    def discover(self, namespace: str):
        requisicao = {
            "type": "DISCOVER",
            "namespace": namespace
        }
        return self._envia_e_recebe_requisicao(requisicao)
    
    def unregister(self, namespace: str, name: str, port: int):
        requisicao = {
            "type": "UNREGISTER",
            "namespace": namespace,
            "name": name,
            "port": port
        }
        return self._envia_e_recebe_requisicao(requisicao)
        
import socket
import json
import threading
from typing import Dict, Any
from state import State

VERSAO = "1.0"
FEATURES = ["relay", "ack", "who_as", "metrics"]
TAMANHO_MAX = 32768  # 32 KiB

class PeerConnection(threading.Thread):
    def __init__(self, sock: socket.socket, endereco_peer: tuple, my_peer_id: str, app_state: State, peer_id: str = None):
        super().__init__(daemon=True)
        self.sock = sock
        self.endereco_peer = endereco_peer
        self.my_peer_id = my_peer_id
        self.state = app_state
        self.peer_id = peer_id
        self.is_running = True
        
    def envia_mensagem(self, mensagem: Dict[str, Any]):
        if 'ttl' in mensagem: # preserva o campo ttl se existir
            ttl = mensagem.pop('ttl') # remove o campo ttl temporariamente
            mensagem['ttl'] = ttl # adiciona o campo ttl de volta no início do dicionário
            
        json_msg = json.dumps(mensagem).encode('utf-8') + b'\n'
        if len(json_msg) > TAMANHO_MAX:
            print(f"[Erro] Mensagem excede tamanho máximo de {TAMANHO_MAX} bytes. Não enviada.")
            return
        
        self.sock.sendall(json_msg)
        
    def faz_handshake(self):
        requisicao_hello = {
            "type": "HELLO",
            "peer_id": self.my_peer_id,
            "version": VERSAO,
            "features": FEATURES,
            "ttl": 1
        }      
        self.envia_mensagem(requisicao_hello)
        
        try:     
            self.sock.settimeout(10.0) # timeout de 10 segundos
            resposta = self.sock.recv(TAMANHO_MAX) # espera pela resposta
            self.sock.settimeout(None) # remove o timeout após receber a resposta
            
            if not resposta: 
                    print("[Erro Handshake] Conexão fechada antes do HELLO_OK.")
                    return False
                
            resposta_msg = json.loads(resposta.decode('utf-8').strip()) # decodifica a resposta
                
            if resposta_msg.get("type") == "HELLO_OK":
                 self.peer_id = resposta_msg.get("peer_id")
                 print(f"[Handshake] Conexão estabelecida com {self.peer_id} em {self.endereco_peer}")
                 self.state.adiciona_conexao_ativa(self.peer_id, self) # adiciona a conexão ativa ao estado
                 return True
            else:
                print(f"[Erro Handshake] Resposta inesperada recebida {resposta_msg}")
                return False
            
        except socket.timeout:
            print("[Erro Handshake] Timeout ao esperar pela resposta do handshake.")
            return False       
               
    
    def recebe_handshake(self):
        try:
            self.sock.settimeout(10.0) # timeout de 10 segundos
            data = self.sock.recv(TAMANHO_MAX) # espera pela mensagem de handshake
            self.sock.settimeout(None) # remove o timeout após receber a mensagem
            
            if not data:
                print(f"[Erro Handshake] Peer {self.endereco_peer} desconectou antes de enviar o HELLO.")
                return False
            
            mensagem = json.loads(data.decode('utf-8').strip()) # decodifica a mensagem
            
            if mensagem.get("type") == "HELLO":
                self.peer_id = mensagem.get("peer_id")
                print(f"[Handshake] Recebido HELLO de {self.peer_id} em {self.endereco_peer}")
                
                resposta_hello_ok = {
                    "type": "HELLO_OK",
                    "peer_id": self.my_peer_id,
                    "version": VERSAO,
                    "features": FEATURES,
                    "ttl": 1
                }               
                self.envia_mensagem(resposta_hello_ok)
                print(f"[Handshake] Enviado HELLO_OK para {self.peer_id}")
                self.state.adiciona_conexao_ativa(self.peer_id, self) # adiciona a conexão ativa ao estado
                return True
            else:
                print(f"[Erro Handshake] Mensagem inesperada recebida: {mensagem}")
                return False
        except socket.timeout:
            print("[Erro Handshake] Timeout ao esperar pela mensagem de handshake.")
            return False
    
    def run(self):
        buffer = ""
        while self.is_running:
            try:
                data = self.sock.recv(1024)
                if not data:
                    print(f"[Conexão] {self.peer_id} desconectou.")
                    break
                buffer += data.decode('utf-8')
                
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        mensagem = json.loads(line.strip())
                        print(f"\n[MSG < {self.peer_id}] {mensagem}\n> ", end='')
            except ConnectionResetError:
                print(f"[*] Conexão com {self.peer_id} foi resetada.")
                break
            except Exception as e:
                print(f"[Erro Inesperado] Conexão com {self.peer_id}: {e}")
                break
            
            self.stop()
            
        def stop(self):
            self.is_running = False
            if self.peer_id:
                self.state.remove_conexao_ativa(self.peer_id)
            if self.sock:
                self.sock.close()
                    
                    
                    
                    
                    
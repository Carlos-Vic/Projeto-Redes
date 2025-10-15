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
        if 'ttl' in mensagem:
            ttl = mensagem.pop('ttl')
            mensagem['ttl'] = ttl
            
        json_msg = json.dumps(mensagem).encode('utf-8') + b'\n'
        if len(json_msg) > TAMANHO_MAX:
            print(f"[Erro] Mensagem excede tamanho máximo de {TAMANHO_MAX} bytes. Não enviada.")
            return
        
        self.sock.sendall(json_msg)
        
    def handshake(self):
        requisicao = {
            "type": "HELLO",
            "peer_id": self.my_peer_id,
            "version": VERSAO,
            "features": FEATURES,
            "ttl": 1
        }
        
        self.envia_mensagem(requisicao)
        
        self.sock.settimeout(10.0)
        
        resposta_data = self.sock.recv(TAMANHO_MAX)
        if not resposta_data:
            print("[Erro] Nenhuma resposta recebida durante o handshake.")
            return False
        
        resposta = json.loads(resposta_data.decode('utf-8').strip())
        
        if resposta.get("type") == "HELLO_OK":
            self.peer_id = resposta.get("peer_id")
            print(f"[Handshake] Conexão estabelecida com {self.peer_id} em {self.endereco_peer}")
            self.state.adiciona_conexao_ativa(self.peer_id, self)
            return True
        else:
            print(f"[Erro] Handshake falhou com {self.endereco_peer}: {resposta}")
            return False
        
        self.sock.settimeout(None)
        
    
    def handshake_nova_conexao(self):
        self.sock.settimeout(10.0)
        
        data = self.sock.recv(TAMANHO_MAX)
        if not data:
            print("[Erro] Nenhuma mensagem recebida durante o handshake.")
            return False
        
        mensagem = json.loads(data.decode('utf-8').strip())
        
        if mensagem.get("type") == "HELLO":
            self.peer_id = mensagem.get("peer_id")
            print(f"[*] Recebido HELLO de {self.peer_id} em {self.endereco_peer}")
            
            resposta = {
                type: "HELLO_OK",
                "peer_id": self.my_peer_id,
                "version": VERSAO,
                "features": FEATURES,
                "ttl": 1
            }
            self.envia_mensagem(resposta)
            print(f"[Handshake] Conexão estabelecida com {self.peer_id} em {self.endereco_peer}")
            self.state.adiciona_conexao_ativa(self.peer_id, self)
            return True
        else:
            print(f"[Erro] Mensagem inesperada durante o handshake de {self.endereco_peer}: {mensagem}")
            return False
        
        self.sock.settimeout(None)
    
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
                    
                    
                    
                    
                    
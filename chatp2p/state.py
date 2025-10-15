import threading

class State:
    def __init__(self, my_peer_id: str):
        self.my_peer_id = my_peer_id
        self.peers_conhecidos = {} # dicionário para armazenar peers conhecidos
        self.conexoes_ativas = {} # dicionário para armazenar conexões ativas
        self.lock = threading.Lock() # lock para garantir acesso thread-safe
    
    def adiciona_peers_conhecidos(self, peers: list):
        with self.lock:
            for peer_info in peers:
                peer_id = f"{peer_info['name']}@{peer_info['namespace']}" # monta o peer_id
                if peer_id != self.my_peer_id: # evita adicionar ele mesmo na lista de peers conhecidos
                    self.peers_conhecidos[peer_id] = peer_info
    
    def retorna_peers_conhecidos(self, peer_id: str):
        with self.lock:
           return self.peers_conhecidos.get(peer_id) # retorna as informações do peer_id solicitado ou None se não existir
    
    def adiciona_conexao_ativa(self, peer_id: str, conexao):
        with self.lock:
            self.conexoes_ativas[peer_id] = conexao # adiciona a conexão ativa ao dicionário
            print(f"[State] Conexão com {peer_id} adicionada. Conexões ativas: {len(self.conexoes_ativas)}")

    def remove_conexao_ativa(self, peer_id: str):
        with self.lock:
            if peer_id in self.conexoes_ativas:
                del self.conexoes_ativas[peer_id] # remove a conexão ativa do dicionário
                print(f"[State] Conexão com {peer_id} removida. Conexões ativas: {len(self.conexoes_ativas)}")            
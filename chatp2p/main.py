# -- arquivo main.py --
import socket
import threading
import time
import logging

from rendezvous_client import RendezvousClient, RendezvousError
from state import State
from p2p_transport import PeerConnection
from cli import CLI
from logger import setup_logging

SERVER_HOST = "pyp2p.mfcaetano.cc"
SERVER_PORT = 8080

log = logging.getLogger(__name__)

def escutar_peers(my_port, my_peer_id, app_state):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server_socket.bind(('0.0.0.0', my_port))
    server_socket.listen()
    log.info(f"[*] Escutando por conexões na porta {my_port}...")
    
    while True:
        client_socket, client_address = server_socket.accept()
        log.info(f"[*] Conexão recebida de {client_address}")
        
        con = PeerConnection(client_socket, client_address, my_peer_id, app_state)
        if con.recebe_handshake():
            con.start()
        else:
            con.close() 

def atualizacao_automatica_peers(rdzv_cliente, app_state):
    time.sleep(10)  # Aguarda 10 segundos antes da primeira atualização
    while True:
        try:
            resposta = rdzv_cliente.discover(None)
            peers = resposta.get("peers", [])
            app_state.adiciona_peers_conhecidos(peers)
        except RendezvousError as e:
            log.warning(f"Falha ao atualizar lista de peers: {e}")
        time.sleep(60)  # Atualiza a lista de peers a cada 60 segundos

def gerencia_conexoes_ativas(my_peer_id, app_state):
    intervalo_verificacao = 30
    
    while True:
        time.sleep(intervalo_verificacao)
        
        log.debug("[Gerenciador] Verificando conexões ativas...")
        with app_state.lock:
            peers_conhecidos_copia = dict(app_state.peers_conhecidos)
            conexoes_ativas_copia = dict(app_state.conexoes_ativas)
            
        peers_para_conectar = []
        for peer_id, peer_info in peers_conhecidos_copia.items():
            if peer_id == my_peer_id:
                continue
            if peer_id in conexoes_ativas_copia:
                continue
            
            peers_para_conectar.append((peer_id, peer_info))
            
            log.debug(f"[Gerenciador] Tentando conectar automaticamente com {len(peers_para_conectar)} peers...")
            
            for peer_id, peer_info in peers_para_conectar:
                with app_state.lock:
                    if peer_id in app_state.conexoes_ativas:
                        continue
                
                peer_ip = peer_info['ip']
                peer_port = peer_info['port']
                
                cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cliente_socket.settimeout(10)
                cliente_socket.connect((peer_ip, peer_port))
                
                conn = PeerConnection(cliente_socket, (peer_ip, peer_port), my_peer_id, app_state)
                if conn.faz_handshake():
                    conn.start()
                else:
                    conn.stop()
                      
def main():
    setup_logging()
    
    nome = input("Digite seu nome: ")
    namespace = input("Digite o namespace: ")
    porta = int(input("Digite a porta para escutar (ex: 5000): "))
    ttl = None
    while True:
        ttl_string = input("Digite o TTL em segundos (ou deixe vazio para padrão): ")   
        if not ttl_string:
            ttl = None
            break
        else:
            ttl = int(ttl_string)
            break
    
    my_info = {
        "name": nome,
        "namespace": namespace,
        "port": porta,
        "ttl": ttl,
        "peer_id": f"{nome}@{namespace}"
    }
    
    app_state = State(my_info['peer_id'])
    rdzv_cliente = RendezvousClient(SERVER_HOST, SERVER_PORT)
    
    try:
        log.info("Registrando no servidor de rendezvous...")
        rdzv_cliente.register(my_info['namespace'], my_info['name'], my_info['port'], my_info['ttl'])
        log.info(f"Registrado como {my_info['peer_id']} na porta {my_info['port']}.")
    except RendezvousError as e:
        log.error(f"Falha ao registrar no servidor de rendezvous: {e}")
        return
    
    threads = [
        threading.Thread(target=escutar_peers, args=(my_info['port'], my_info['peer_id'], app_state), daemon=True),
        threading.Thread(target=atualizacao_automatica_peers, args=(rdzv_cliente, app_state), daemon=True),
        threading.Thread(target=gerencia_conexoes_ativas, args=(my_info['peer_id'], app_state), daemon=True, name="AutoConnector")
    ]
    for t in threads:
        t.start()
    
    cli = CLI(rdzv_cliente, app_state, my_info)
    cli.run()
    
if __name__ == "__main__":
    main()
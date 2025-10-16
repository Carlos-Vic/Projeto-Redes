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

SERVER_HOST = "192.168.1.2"
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


def registro_periodico(rdzv_cliente, my_namespace, my_name, my_port):
    while True:
        log.info("Mantendo registro no servidor de rendezvous...")
        rdzv_cliente.register(my_namespace, my_name, my_port, ttl=360)
        time.sleep(300)

def atualizacao_automatica_peers(rdzv_cliente, my_namespace, app_state):
    time.sleep(10)  # Aguarda 10 segundos antes da primeira atualização
    while True:
        try:
            resposta = rdzv_cliente.discover(my_namespace)
            peers = resposta.get("peers", [])
            app_state.adiciona_peers_conhecidos(peers)
        except RendezvousError as e:
            print(f"[Erro Debug] Falha ao atualizar peers automaticamente: {e}")
        time.sleep(60)  # Atualiza a lista de peers a cada 60 segundos

def main():
    setup_logging()
    
    nome = input("Digite seu nome: ")
    namespace = input("Digite o namespace: ")
    porta = int(input("Digite a porta para escutar (ex: 5000): "))
    
    my_info = {
        "name": nome,
        "namespace": namespace,
        "port": porta,
        "peer_id": f"{nome}@{namespace}"
    }
    
    app_state = State(my_info['peer_id'])
    rdzv_cliente = RendezvousClient(SERVER_HOST, SERVER_PORT)
    
    try:
        log.info("Registrando no servidor de rendezvous...")
        rdzv_cliente.register(my_info['namespace'], my_info['name'], my_info['port'], ttl=360)
        log.info(f"Registrado como {my_info['peer_id']} na porta {my_info['port']}.")
    except RendezvousError as e:
        log.error(f"Falha ao registrar no servidor de rendezvous: {e}")
        return
    
    threads = [
        threading.Thread(target=escutar_peers, args=(my_info['port'], my_info['peer_id'], app_state), daemon=True),
        threading.Thread(target=registro_periodico, args=(rdzv_cliente, my_info['namespace'], my_info['name'], my_info['port']), daemon=True),
        threading.Thread(target=atualizacao_automatica_peers, args=(rdzv_cliente, my_info['namespace'], app_state), daemon=True)
    ]
    for t in threads:
        t.start()
    
    cli = CLI(rdzv_cliente, app_state, my_info)
    cli.run()
    
if __name__ == "__main__":
    main()
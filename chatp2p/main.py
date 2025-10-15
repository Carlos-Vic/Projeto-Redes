# -- arquivo main.py --

import socket
import threading
import time
from rendezvous_client import RendezvousClient
from state import State
from p2p_transport import PeerConnection

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080

MY_NAMESPACE = "UnB"
MY_NAME = "carlos"
MY_PORT = 5555
MY_PEER_ID = f"{MY_NAME}@{MY_NAMESPACE}"

app_state = State(MY_PEER_ID)
rdzv_cliente = RendezvousClient(SERVER_HOST, SERVER_PORT)

def escutar_peers():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server_socket.bind(('0.0.0.0', MY_PORT))
    server_socket.listen()
    print(f"[*] Cliente escutando conexões na porta {MY_PORT}...")
    
    while True:
        client_socket, client_address = server_socket.accept()
        print(f"[+] Conexão recebida de {client_address}")
        
        con = PeerConnection(client_socket, client_address, MY_PEER_ID, app_state)
        if con.handshake_nova_conexao():
            con.start()
        else:
            con.close() 


def registro_periodico():
    while True:
        print("Registrando no servidor de rendezvous...")
        rdzv_cliente.register(MY_NAMESPACE, MY_NAME, MY_PORT)
        time.sleep(300)

def main():
    print(f"[*] Cliente P2P iniciado como {MY_PEER_ID}")
    listener_thread = threading.Thread(target=escutar_peers, daemon=True)
    listener_thread.start()
    
    registro_thread = threading.Thread(target=registro_periodico, daemon=True)
    registro_thread.start()
    
    time.sleep(1)  # Aguarda o listener iniciar
    
    while True:
        linha_cmd = input("> ").strip()
        if not linha_cmd:
            continue
        
        partes = linha_cmd.split(" ", 1)
        comando = partes[0].lower()
        
        if comando == "/quit":
            resposta = rdzv_cliente.unregister(MY_NAMESPACE, MY_NAME)
            print("Saindo...")
            break
        
        elif comando == "/peers":
            if not app_state.peers_conhecidos:
                print("Nenhum peer conhecido. Use /discover para encontrar peers.")
            for peer_id, info in app_state.peers_conhecidos.items():
                print(f"- {peer_id} (Visto em: {info['ip']}:{info['port']})")
                
        elif comando == "/discover":
            print("Descobrindo peers no namespace {MY_NAMESPACE}...")
            resposta = rdzv_cliente.discover(MY_NAMESPACE)
            if resposta.get("status") == "OK":
                peers = resposta.get("peers", [])
                app_state.adiciona_peers_conhecidos(peers)
                print("Descobertos {len(peers)} peers.")
            else:
                print("Erro ao descobrir peers: {resposta.get('message')}")
            
        elif comando == "/connect":
            if len(partes) < 2:
                print("Uso: /connect <peer_id>")
                continue
            
            peer_id = partes[1]
            if peer_id == MY_PEER_ID:
                print("Não é possível conectar a si mesmo.")
                continue
            
            peer_info = app_state.retorna_peers_conhecidos(peer_id)
            if not peer_info:
                print("Peer {peer_id} não encontrado nos conhecidos. Use /discover primeiro.")
                continue
            
            peer_ip = peer_info['ip']
            peer_port = peer_info['port']
            
            print(f"Conectando a {peer_id} em {peer_ip}:{peer_port}...")
            
            cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cliente_socket.connect((peer_ip, peer_port))
            
            conn = PeerConnection(cliente_socket, (peer_ip, peer_port), MY_PEER_ID, app_state)
            
            if conn.handshake():
                conn.start()
            else:
                conn.stop()
        
        else:
            print("Comando desconhecido.")

if __name__ == "__main__":
    main()
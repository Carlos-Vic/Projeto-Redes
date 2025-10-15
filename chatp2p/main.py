# -- arquivo main.py --

import socket
import threading
from rendezvous_client import RendezvousClient

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080

MY_NAMESPACE = "UnB"
MY_NAME = "carlos"
MY_PORT = 5555
MY_PEER_ID = f"{MY_NAME}@{MY_NAMESPACE}"

cliente = RendezvousClient(SERVER_HOST, SERVER_PORT)

def escutar_peers():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    server_socket.bind(('0.0.0.0', MY_PORT))
    server_socket.listen()
    print(f"[*] Cliente escutando conexões na porta {MY_PORT}...")
    
    while True:
        client_socket, client_address = server_socket.accept()
        print(f"[+] Conexão recebida de {client_address}")
        client_socket.close()    


def main():
    print(f"[*] Cliente P2P iniciado como {MY_PEER_ID}")
    listener_thread = threading.Thread(target=escutar_peers, daemon=True)
    listener_thread.start()
    
    try:
        print(f"Registrando {MY_NAME} no namespace {MY_NAMESPACE} na porta {MY_PORT}...")
        resposta = cliente.register(MY_NAMESPACE, MY_NAME, MY_PORT)
        print("Resposta do registro:", resposta)
        
        if resposta.get("status") != "OK":
            print("Erro ao registrar. Encerrando.")
            return
     
        print("\n--- Cliente P2P ativo. Pressione Enter para sair")
        input()   
    
    finally:
        print(f"Desregistrando {MY_NAME} do namespace {MY_NAMESPACE} na porta {MY_PORT}...")
        cliente.unregister(MY_NAMESPACE, MY_NAME, MY_PORT)
        resposta = cliente.discover(MY_NAMESPACE)
        print("Resposta desregistro:", resposta)

if __name__ == "__main__":
    main()
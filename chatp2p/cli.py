import logging
import socket
from rendezvous_client import RendezvousError
from p2p_transport import PeerConnection

log = logging.getLogger(__name__)

class CLI:
    def __init__(self, rdzv_cliente, app_state, my_info):
        self.rdzv_cliente = rdzv_cliente
        self.app_state = app_state
        self.my_info = my_info
        
    def run(self):
        
        
        while True:
            linha_cmd = input("> ").strip()
            if not linha_cmd:
                continue
                
            partes = linha_cmd.split(" ", 1)
            comando = partes[0].lower()
                
            if comando == "/quit":
                self._handle_disconnect()
                break
            elif comando == "/peers":
                self._handle_peers(partes)
            else:
                log.warning(f"Comando desconhecido: {comando}")

    def _handle_disconnect(self):
        log.info("Desconectando...")
        info = self.my_info
        self.rdzv_cliente.unregister(info['namespace'], info['name'], info['port'])
        log.info(f"Desconectado {info['peer_id']}.")
    
    def _handle_peers(self, partes):
        namespace = None
        log_message = ""
        
        if len(partes) == 1:
            namespace = None
            log_message = "Buscando peers em todos os namespaces..."
        else:
            namespace = partes[1]
            log_message = f"Buscando peers no namespace '{namespace}'..."
        log.info(log_message)
        
        resposta = self.rdzv_cliente.discover(namespace)
        peers = resposta.get("peers", [])
        
        self.app_state.adiciona_peers_conhecidos(peers)
        
        if not peers:
            log.info("Nenhum peer encontrado.")
        else:
            for peer in peers:
                peer_id = f"{peer['name']}@{peer['namespace']}"
                log.info(f"Peer encontrado: {peer_id} em {peer['ip']}:{peer['port']}")
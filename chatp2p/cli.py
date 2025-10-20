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
            elif comando == "/connect":
                self._handle_connect(partes)
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
                if peer_id != self.my_info['peer_id']:
                    log.info(f"Peer encontrado: {peer_id} em {peer['ip']}:{peer['port']}")
    
    def _handle_connect(self, partes):
        if len(partes) < 2:
            log.warning("Uso: /connect <peer_id>")
            return
        
        peer_id = partes[1]
        if peer_id == self.my_info['peer_id']:
            log.warning("Não é possível conectar a si mesmo.")
            return
        
        peer_info = self.app_state.retorna_peers_conhecidos(peer_id)
        if not peer_info:
            log.error()(f"Peer {peer_id} não encontrado nos conhecidos. Use /peers para atualizar a lista.")

        
        peer_ip = peer_info['ip']
        peer_port = peer_info['port']
            
        log.info(f"Conectando a {peer_id} em {peer_ip}:{peer_port}...")
            
        cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente_socket.connect((peer_ip, peer_port))
        
        con = PeerConnection(cliente_socket, (peer_ip, peer_port), self.my_info['peer_id'], self.app_state)
        
        if con.faz_handshake():
            con.start()
        else:
            log.error(f"Falha no handshake com {peer_id}.")
            con.stop()       
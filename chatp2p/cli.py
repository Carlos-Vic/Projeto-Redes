from state import State
from rendezvous_client import *


class CLI:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.state = None
        self.registrado = False
    
    
    def cmd_setup(self):
        try:
            self.state = State(self.config_path)
            
            namespace = input("Digite o namespace: ").strip()
            if not namespace:
                print("Namespace não pode ser vazio.")
                return
            
            name = input("Digite seu nome: ").strip()
            if not name:
                print("Nome não pode ser vazio.")
                return
            
            porta = int(input("Digite a porta para escutar (ex: 5000): "))

            ttl = input("Digite o TTL em segundos (ou deixe vazio para padrão 7200): ").strip()
            if ttl:
                ttl = int(ttl)
            else:
                ttl = 7200 
        
                
            self.state.set_peer_info(name, namespace, porta, ttl)
            
            print(f"Peer ID definido como: {self.state.get_peer_info()}")
            print(f"Porta definida como: {self.state.port}")
            print(f"TTL definida como: {self.state.ttl} segundos")
        
        except Exception as e:
            print(f"Falha ao configurar o estado: {e}")
        
    
    def cmd_registrar(self):
        if not self.state:
            print("Estado não inicializado. Execute setup() primeiro.")
            return
        
        print("Registrando no servidor de rendezvous...")
        
        try:
            resposta = register(self.state)
            self.registrado = True
            print(f"Registrado com sucesso")
            print(f"Status: {resposta.get('status')}")
            
        except RendezvousError as e:
            print(f"Falha ao registrar no servidor de rendezvous: {e}")
            
    
    def cmd_discover(self, args):
        if not self.state:
            print("Estado não inicializado. Execute setup primeiro.")
            return

        # args é uma lista: [] se sem argumentos, ['namespace'] se com argumento
        namespace = args[0] if args else None

        if namespace:
            print(f"Descobrindo peers no namespace '{namespace}'...")
        else:
            print("Descobrindo peers em todos os namespaces...")
            
        try:
            peers = discover(self.state, namespace=namespace)
            
            if not peers:
                print("Nenhum peer encontrado.")
                return
            
            print(f"Total de peers encontrados ({len(peers)}):")
            
            por_namespace = {}
            for peer in peers:
                ns = peer.get("namespace", "unknown")
                if ns not in por_namespace:
                    por_namespace[ns] = []
                por_namespace[ns].append(peer)
                
            for ns in sorted(por_namespace.keys()):
                print(f"[{ns}]")
                for peer in por_namespace[ns]:
                    peer_id = f"{peer.get('name')}@{peer.get('namespace')}"
                    ip = peer.get("ip")
                    porta = peer.get("port")
                    print(f" - {peer_id} ({ip}:{porta})")
                print()
                
        except RendezvousError as e:
            print(f"Falha ao descobrir peers: {e}")
    
    def cmd_unregister(self):
        if not self.state:
            print("Estado não inicializado. Execute setup primeiro.")
            return
        
        if not self.registrado:
            print("Peer não registrado. Execute registrar() primeiro.")
            return
        
        print("Desregistrando do servidor de rendezvous...")
        
        try:
            resposta = unregister(self.state)
            self.registrado = False
            print(f"Desregistrado com sucesso")
            print(f"Status: {resposta.get('status')}")
            print()
            
        except RendezvousError as e:
            print(f"Falha ao desregistrar do servidor de rendezvous: {e}")
            
    def processa_comando(self, comando):

        if not comando.strip():
            return True

        partes = comando.strip().split()
        cmd = partes[0].lower()
        args = partes[1:]

        if cmd in ['quit', 'exit']:
            return False
        elif cmd == 'setup':
            self.cmd_setup()
        elif cmd == 'registrar':
            self.cmd_registrar()
        elif cmd == 'discover':
            self.cmd_discover(args)
        elif cmd == 'unregister':
            self.cmd_unregister()

        else:
            print(f"Comando desconhecido: {cmd}")

        return True
        
    def limpar(self):
        if self.registrado and self.state:
            print("Removendo registro antes de sair...")
            try:
                unregister(self.state)
                print("Registro removido com sucesso.")
            except Exception as e:
                print(f"Falha ao remover registro: {e}")
    
    def run(self):
        print("Bem-vindo ao chat P2P!")
        print("Digite 'setup' para começar.")
        
        try:
            while True:
               try:
                    comando = input("rendezvous> ")
                    if not self.processa_comando(comando):
                        break
               except EOFError:
                   print("\n")
                   break
               
        except (KeyboardInterrupt, EOFError):
            print("\nSaindo...")
        
        finally:
            self.limpar()
            print("Até logo!")
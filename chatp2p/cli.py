from state import State
from rendezvous_connection import *


class CLI:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path # Caminho para o arquivo de configuração
        self.state = None # Estado inicializado como None
        self.registrado = False # Flag para indicar se o peer está registrado no servidor rendezvous
    
    
    
    def cmd_help(self):
        print("\n" + "="*60)
        print("Comandos disponíveis".center(60))
        print("="*60)
        
        comandos = [
          ("peers [namespace]", "Descobrir peers ativos"),
          ("", "  - peers          : Lista todos os peers"),
          ("", "  - peers CIC      : Lista peers do namespace CIC"),
          ("", ""),
          ("unregister", "Desregistrar do servidor rendezvous"),
          ("", ""),
          ("quit ou exit", "Sair do programa"),
          ("", ""),
          ("help", "Mostrar esta ajuda"),
      ]

        for cmd, desc in comandos:
            if cmd:
                print(f"{cmd:20s} - {desc}")
            else:
                print(f" {desc}")
        
        print("="*60)
        print()
            
    def cmd_setup(self): # Configura o estado inicial
        try:
            # Inicializa o estado
            self.state = State(self.config_path)
            
            # Pede ao usuário as informações do peer
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
        
                
            self.state.set_peer_info(name, namespace, porta, ttl) # Define as informações do peer no estado
            
            # Mostra as informações definidas
            print(f"Peer ID definido como: {self.state.get_peer_info()}")
            print(f"Porta definida como: {self.state.port}")
            print(f"TTL definida como: {self.state.ttl} segundos")
        
        except Exception as e:
            print(f"Falha ao configurar o estado: {e}")
        
    
    def cmd_registrar(self): # Registra o peer no servidor rendezvous
        if not self.state:
            print("Estado não inicializado. Execute setup() primeiro.")
            return
        
        print("Registrando no servidor de rendezvous...")
        
        try:
            resposta = register(self.state) # Tenta registrar o peer no servidor rendezvous	
            self.registrado = True # Marca flag como registrado
            print(f"Registrado com sucesso")
            print(f"Status: {resposta.get('status')}")
            
        except RendezvousError as e:
            print(f"Falha ao registrar no servidor de rendezvous: {e}")
            
    
    def cmd_discover(self, args): # Descobre peers no servidor rendezvous
        if not self.state:
            print("Estado não inicializado. Execute setup primeiro.")
            return

        # Verifica se o usuário passou um namespace como argumento
        if args:
            namespace = args[0] 
        else:
            namespace = None

        if namespace: # Imprime mensagem diferente se namespace foi especificado	
            print(f"Descobrindo peers no namespace '{namespace}'...")
        else:
            print("Descobrindo peers em todos os namespaces...")
            
        try:
            peers = discover(self.state, namespace=namespace) # Tenta descobrir peers no servidor rendezvous
            
            if not peers:
                print("Nenhum peer encontrado.")
                return
            
            print(f"Total de peers encontrados ({len(peers)}):")
            
            por_namespace = {} # Dicionário para agrupar peers por namespace
            for peer in peers:
                ns = peer.get("namespace", "unknown") # Obtém o namespace do peer
                if ns not in por_namespace: 
                    por_namespace[ns] = []
                por_namespace[ns].append(peer) # Adiciona o peer ao namespace correspondente
                
            for ns in sorted(por_namespace.keys()): # Imprime os peers agrupados por namespace
                print(f"[{ns}]")
                for peer in por_namespace[ns]:
                    peer_id = f"{peer.get('name')}@{peer.get('namespace')}"
                    ip = peer.get("ip")
                    porta = peer.get("port")
                    print(f" - {peer_id} ({ip}:{porta})") # Imprime as informações do peer
                print()
                
        except RendezvousError as e:
            print(f"Falha ao descobrir peers: {e}")
    
    def cmd_unregister(self): # Desregistra o peer do servidor rendezvous
        if not self.state:
            print("Estado não inicializado. Execute setup primeiro.")
            return
        
        if not self.registrado:
            print("Peer não registrado. Execute registrar() primeiro.")
            return
        
        print("Desregistrando do servidor de rendezvous...")
        
        try:
            resposta = unregister(self.state) # Tenta desregistrar o peer do servidor rendezvous
            self.registrado = False # Marca flag como desregistrado
            print(f"Desregistrado com sucesso")
            print(f"Status: {resposta.get('status')}")
            print()
            
        except RendezvousError as e:
            print(f"Falha ao desregistrar do servidor de rendezvous: {e}")
            
    def processa_comando(self, comando): # Processa o comando digitado pelo usuário

        if not comando.strip():
            return True

        partes = comando.strip().split() # Divide o comando em partes
        cmd = partes[0].lower() # Obtém o comando principal
        args = partes[1:] # Obtém os argumentos do comando

        if cmd in ['quit', 'exit']:
            return False
        elif cmd in ['help']:
            self.cmd_help()
        elif cmd in ['peers']:
            self.cmd_discover(args)
        elif cmd in ['unregister']:
            self.cmd_unregister()
        else:
            print(f"Comando desconhecido: {cmd}")

        return True
        
    def limpar(self): # Limpa o estado antes de sair para conexão não ficar registrada
        if self.registrado and self.state: # Se estiver registrado, tenta desregistrar
            print("Removendo registro antes de sair...")
            try:
                unregister(self.state) # Tenta desregistrar o peer do servidor rendezvous
                print("Registro removido com sucesso.")
            except Exception as e:
                print(f"Falha ao remover registro: {e}")
    
    def run(self):
        print("Bem-vindo ao chat P2P!")
        self.cmd_setup()
        if not self.state:
            print("Estado não configurado. Saindo...")
            return
        
        self.cmd_registrar()
        if not self.registrado:
            print("Não foi possível registrar. Saindo...")
            return
        print()
        print("Digite 'help' para ver os comandos disponíveis.")
        print()
        
        
        try:
            while True: # Loop principal do CLI
               try:
                    comando = input("chatp2p> ") # Pede o comando ao usuário
                    if not self.processa_comando(comando): # Processa o comando
                        break
               except EOFError: # Trata EOF (Ctrl+D)
                   print("\n")
                   break
               
        except (KeyboardInterrupt, EOFError): # Trata Ctrl+C e EOF
            print("\nSaindo...")
        
        finally: # Limpa o estado antes de sair
            self.limpar()
            print("Até logo!")
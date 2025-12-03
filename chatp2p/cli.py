from state import State
from rendezvous_connection import *
from p2p_client import P2PClient
import logging
import time


class CLI:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path # Caminho para o arquivo de configuração
        self.state = None # Estado inicializado como None
        self.registrado = False # Flag para indicar se o peer está registrado no servidor rendezvous
        self.p2p_client = None # Cliente P2P inicializado como None
    
    
    
    def cmd_help(self):
        # Exibe a lista de comandos disponíveis no CLI
        print("\n" + "="*60)
        print("Comandos disponíveis".center(60))
        print("="*60)
        
        comandos = [
          ("peers [namespace]", "Descobrir peers ativos"),
          ("", "  - peers          : Lista todos os peers"),
          ("", "  - peers CIC      : Lista peers do namespace CIC"),
          ("", ""),
          ("msg <peer_id> <mensagem>", "Envia uma mensagem para um peer específico"),
          ("", "  - msg bob@geral Oi!  : Envia 'Oi!' para o peer bob@geral"),
          ("", ""),
          ("pub <destino> <mensagem>", "Publica mensagem para múltiplos peers"),
          ("", "  - pub * Olá a todos      : Broadcast para TODOS os peers"),
          ("", "  - pub #CIC Atenção grupo : Mensagem para namespace CIC"),
          ("", ""),
          ("conn", "Mostrar conexões ativas (inbound/outbound)"),
          ("", ""),
          ("status", "Mostrar status de peers (conectados e com falha)"),
          ("", ""),
          ("rtt", "Exibir RTT (Round Trip Time) de cada peer conectado"),
          ("", ""),
          ("reconnect", "Forçar reconciliação de peers (limpa falhas e redescobre)"),
          ("", ""),
          ("log <nível>", "Ajustar nível de log em runtime"),
          ("", "  - log DEBUG      : Logs detalhados"),
          ("", "  - log INFO       : Logs informativos (padrão)"),
          ("", "  - log WARNING    : Apenas avisos e erros"),
          ("", ""),
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

            # Validação do namespace (até 64 caracteres, não pode ser vazio)
            while True:
                namespace = input("Digite o namespace (max 64 caracteres): ").strip()
                if not namespace:
                    print("ERRO: Namespace não pode ser vazio.")
                    continue
                if len(namespace) > 64:
                    print("ERRO: Namespace deve ter no máximo 64 caracteres.")
                    continue
                break  # Namespace válido

            # Validação do name (até 64 caracteres, não pode ser vazio)
            while True:
                name = input("Digite seu nome (max 64 caracteres): ").strip()
                if not name:
                    print("ERRO: Nome não pode ser vazio.")
                    continue
                if len(name) > 64:
                    print("ERRO: Nome deve ter no máximo 64 caracteres.")
                    continue
                break  # Nome válido

            # Validação da porta (1-65535)
            while True:
                try:
                    porta_input = input("Digite a porta para escutar (1 - 65535): ").strip()
                    porta = int(porta_input)
                    if porta < 1 or porta > 65535:
                        print("ERRO: Porta deve estar entre 1 e 65535.")
                        continue
                    break  # Porta válida
                except ValueError:
                    print("ERRO: Porta deve ser um número inteiro.")
                    continue

            # Validação do TTL (1-86400 segundos, padrão 7200)
            threshold = self.state.get_config("rendezvous", "ttl_warning_treshold")
            ttl_minimo = threshold * 2

            while True:
                ttl_input = input("Digite o TTL em segundos (ou deixe vazio para padrão 7200): ").strip()

                if not ttl_input:
                    ttl = 7200  # Padrão
                    break

                try:
                    ttl = int(ttl_input)
                except ValueError:
                    print("ERRO: TTL deve ser um número inteiro.")
                    continue

                # Validação da especificação: TTL deve estar entre 1 e 86400
                if ttl < 1 or ttl > 86400:
                    print("ERRO: TTL deve estar entre 1 e 86400 segundos.")
                    continue

                # Validação adicional: TTL deve ser maior que 2x o threshold para evitar loop de re-registro
                if ttl <= ttl_minimo:
                    print(f"AVISO: TTL deve ser maior que {ttl_minimo} segundos (2x o threshold de re-registro)")
                    print(f"Por favor, escolha TTL > {ttl_minimo}s ou deixe vazio para padrão (7200s)")
                    continue

                break  # TTL válido

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
    
    def cmd_status(self):
        # Exibe status de peers conectados e peers com falha de conexão (com backoff countdown)
        if not self.state:
            print("Estado não inicializado. Execute setup primeiro.")
            return

        if not self.p2p_client:
            print("P2PClient não está rodando.")
            return

        print("\n" + "="*60)
        print("Status de Peers".center(60))
        print("="*60)

        # Lista peers conectados com sucesso
        conexoes = self.state.get_todas_conexoes()
        print(f"\nPeers conectados ({len(conexoes)}):")
        if conexoes:
            for peer_id in sorted(conexoes.keys()):
                print(f"  ✓ {peer_id}")
        else:
            print("  (nenhum)")

        # Lista peers com falha de conexão e tempo restante para próxima tentativa
        with self.p2p_client._lock_falhas:
            falhas = self.p2p_client._peers_com_falha.copy()

        print(f"\nPeers com falha de conexão ({len(falhas)}):")
        if falhas:
            import time
            for peer_id, info in sorted(falhas.items()):
                tentativas = info['tentativas']
                backoff_min = min(2 ** (tentativas - 1), 30)  # Backoff exponencial
                tempo_desde = int(time.time() - info['timestamp'])
                tempo_restante = max(0, (backoff_min * 60) - tempo_desde)

                # Converte tempo restante para minutos e segundos
                mins = tempo_restante // 60
                secs = tempo_restante % 60

                print(f"  ✗ {peer_id} - Próxima tentativa em {mins}m{secs}s (tentativa #{tentativas})")
        else:
            print("  (nenhum)")

        print("="*60 + "\n")

    def cmd_rtt(self):
        # Exibe o RTT (Round Trip Time) de cada peer conectado
        if not self.state:
            print("Estado não inicializado. Execute setup primeiro.")
            return

        conexoes = self.state.get_todas_conexoes()

        print("\n" + "="*60)
        print("RTT (Round Trip Time) por Peer".center(60))
        print("="*60)

        if not conexoes:
            print("\nNenhum peer conectado.")
            print("="*60 + "\n")
            return

        print(f"\n{'Peer ID':<25} {'RTT Médio':<15} {'Amostras':<10}")
        print("-"*60)

        # Itera sobre conexões e exibe RTT se KeepAlive estiver ativo
        for peer_id, conn in sorted(conexoes.items()):
            if hasattr(conn, 'keep_alive') and conn.keep_alive:
                rtt_medio = conn.keep_alive.get_rtt_medio()  # RTT médio em ms
                quantidade = conn.keep_alive.get_quantidade_pings()  # Quantidade de amostras

                if rtt_medio is not None:
                    print(f"{peer_id:<25} {rtt_medio:>8.2f} ms     {quantidade:<10}")
                else:
                    print(f"{peer_id:<25} {'N/A':<15} {0:<10}")
            else:
                # Conexões inbound não têm KeepAlive (apenas outbound envia PING)
                print(f"{peer_id:<25} {'N/A':<15} {0:<10}")

        print("="*60 + "\n")

    def cmd_reconnect(self):
        # Força reconciliação de peers (limpa falhas e redescobre)
        if not self.p2p_client:
            print("P2PClient não está rodando.")
            return

        print("Forçando reconciliação de peers...")

        # Limpa lista de peers com falha (reseta backoff)
        count_falhas = self.p2p_client.limpar_todas_falhas()
        print(f"- {count_falhas} peer(s) removido(s) da lista de falhas")

        # Força discover imediato e tenta conectar com todos
        count_tentativas = self.p2p_client.forcar_discover()
        print(f"- {count_tentativas} tentativa(s) de conexão iniciada(s)")

        print("Reconciliação concluída!")

    def cmd_log(self, args):
        # Ajusta o nível de log em runtime (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        if not args:
            print("Uso: log <NÍVEL>")
            print("Níveis disponíveis: DEBUG, INFO, WARNING, ERROR, CRITICAL")
            return

        nivel_str = args[0].upper()
        niveis_validos = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

        # Valida se o nível fornecido é válido
        if nivel_str not in niveis_validos:
            print(f"Nível inválido: {nivel_str}")
            print("Níveis disponíveis: DEBUG, INFO, WARNING, ERROR, CRITICAL")
            return

        # Ajusta o nível do logger raiz (afeta todos os módulos do projeto)
        logging.getLogger().setLevel(niveis_validos[nivel_str])
        print(f"Nível de log ajustado para: {nivel_str}")

    def cmd_conn(self):
        # Mostra conexões ativas separadas por outbound (você iniciou) e inbound (outros iniciaram)
        if not self.state:
            print("Estado não inicializado. Use o comando 'setup' primeiro.")
            return

        conexoes = self.state.get_todas_conexoes()  # Obtém todas as conexões ativas do estado

        print("Conexões ativas:")
        outbounds = {}
        inbounds = {}

        # Separa conexões por direção (outbound vs inbound)
        for peer_id, conexao in conexoes.items():
            if conexao.foi_iniciado:
                outbounds[peer_id] = conexao  # Você conectou ao peer (você é cliente)
            else:
                inbounds[peer_id] = conexao  # Peer conectou a você (você é servidor)

        # Lista conexões outbound
        print("Outbound connections:")
        if outbounds:
            for peer_id, conexao in outbounds.items():
                print(f"  - {peer_id} (Conectado a {conexao.sock.getpeername()})")
        else:
            print("  (nenhuma)")

        # Lista conexões inbound
        print("Inbound connections:")
        if inbounds:
            for peer_id, conexao in inbounds.items():
                print(f"  - {peer_id} (Conectado de {conexao.sock.getpeername()})")
        else:
            print("  (nenhuma)")
            
    def cmd_msg(self, args):
        # Envia mensagem unicast (SEND) para um peer específico e aguarda ACK
        if not self.state:
            print("Estado não inicializado. Use o comando 'setup' primeiro.")
            return

        # Valida argumentos (precisa de peer_id e mensagem)
        if len(args) < 2:
            print("Uso: msg <peer_id> <mensagem>")
            return

        peer_id = args[0]  # Primeiro argumento é o peer_id (ex: alice@CIC)
        message = " ".join(args[1:])  # Resto é a mensagem

        # Obtém o MessageRouter do state
        router = self.state.get_message_router()
        if not router:
            print("Erro: Roteador de mensagens não está disponível.")
            return

        # Envia mensagem SEND e aguarda ACK (com retry e timeout)
        print(f"Enviando mensagem para {peer_id}...")
        if router.send(peer_id, message):
            print("Mensagem enviada e confirmada (ACK recebido).")
        else:
            print("Falha ao enviar mensagem. O peer pode estar offline ou não respondeu.")

    def cmd_pub(self, args):
        # Envia mensagem broadcast (*) ou namespace-cast (#namespace) sem ACK
        if not self.state:
            print("Estado não inicializado. Use o comando 'setup' primeiro.")
            return

        # Valida argumentos (precisa de destino e mensagem)
        if len(args) < 2:
            print("Uso: pub <destino> <mensagem>")
            print("  pub * <mensagem>          - Broadcast para todos os peers")
            print("  pub #namespace <mensagem> - Enviar para todos do namespace")
            return

        destino = args[0]  # Primeiro argumento é o destino (* ou #namespace)
        message = " ".join(args[1:])  # Resto é a mensagem

        # Valida o formato do destino (deve ser * ou começar com #)
        if destino != "*" and not destino.startswith("#"):
            print("ERRO: Destino deve ser '*' (broadcast) ou '#namespace' (namespace-cast)")
            print("Exemplos:")
            print("  pub * Olá a todos!")
            print("  pub #CIC Mensagem para o namespace CIC")
            return

        # Obtém o MessageRouter do state
        router = self.state.get_message_router()
        if not router:
            print("Erro: Roteador de mensagens não está disponível.")
            return

        # Exibe mensagem apropriada dependendo do tipo de publicação
        if destino == "*":
            print("Publicando mensagem para TODOS os peers...")
        else:
            namespace = destino[1:]  # Remove o '#'
            print(f"Publicando mensagem para peers do namespace '{namespace}'...")

        # Envia a mensagem PUB e recebe quantidade de peers que receberam
        count = router.publish(destino, message)

        # Feedback para o usuário baseado na quantidade de peers alcançados
        if count == 0:
            if destino == "*":
                print("Nenhum peer conectado para receber a mensagem.")
            else:
                namespace = destino[1:]
                print(f"Nenhum peer do namespace '{namespace}' está conectado.")
                print(f"O namespace pode não existir ou não há peers conectados nele.")
        elif count == 1:
            print(f"Mensagem enviada para {count} peer.")
        else:
            print(f"Mensagem enviada para {count} peers.")
            
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
        elif cmd in ['conn']:
            self.cmd_conn()
        elif cmd in ['status']:
            self.cmd_status()
        elif cmd in ['rtt']:
            self.cmd_rtt()
        elif cmd in ['reconnect']:
            self.cmd_reconnect()
        elif cmd in ['log']:
            self.cmd_log(args)
        elif cmd in ['msg']:
            self.cmd_msg(args)
        elif cmd in ['pub']:
            self.cmd_pub(args)
        else:
            print(f"Comando desconhecido: {cmd}")

        return True
        
    def limpar(self): # Limpa o estado antes de sair para conexão não ficar registrada
        print("Encerrando...")
        if self.p2p_client:
            self.p2p_client.stop()
            
        if self.registrado:
            try:
                unregister(self.state)
                print("Desregistrado com sucesso.")
            except RendezvousError as e:
                print(f"Erro ao desregistrar: {e}")
        
        if self.state:
            self.state.set_encerrado()
            
        print("Programa encerrado.")
    
    def run(self):
        # Ponto de entrada principal do CLI: setup, registro, inicialização e loop de comandos
        print("Bem-vindo ao chat P2P!")

        # Etapa 1: Configura estado inicial (namespace, nome, porta, TTL)
        self.cmd_setup()
        if not self.state:
            print("Estado não configurado. Saindo...")
            return

        # Etapa 2: Registra no servidor Rendezvous
        self.cmd_registrar()
        if not self.registrado:
            print("Não foi possível registrar. Saindo...")
            return

        # Etapa 3: Inicia cliente P2P (servidor TCP, discover automático, re-registro)
        print("Iniciando servidor P2P e conexões automáticas...")
        try:
            self.p2p_client = P2PClient(self.state)
            self.p2p_client.start()
            print("Servidor P2P iniciado com sucesso!")
        except Exception as e:
            print(f"Falha ao iniciar servidor P2P: {e}")
            return

        print()
        print("Digite 'help' para ver os comandos disponíveis.")
        print()

        # Loop principal do CLI: lê comandos do usuário e executa
        try:
            while True:
               try:
                    comando = input("chatp2p> ")  # Prompt para comando do usuário
                    if not self.processa_comando(comando):  # Processa comando (retorna False se quit/exit)
                        break
               except EOFError:  # Trata EOF (Ctrl+D)
                   print("\n")
                   break

        except (KeyboardInterrupt, EOFError):  # Trata Ctrl+C e EOF
            print("\nSaindo...")

        finally:  # Cleanup: para P2P client, desregistra do Rendezvous
            self.limpar()
            print("Até logo!")
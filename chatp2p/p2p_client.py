import socket
import threading
import time
import logging
from typing import Dict, Any, List
from peer_server import PeerServer
from peer_connection import PeerConnection, PeerConnectionError
from message_router import MessageRouter
from rendezvous_connection import discover, register, unregister, RendezvousError

logger = logging.getLogger(__name__)

class P2PClient:
    def __init__(self, state):
        self.state = state
        self.peer_server = None
        self._rodando = threading.Event()
        self._thread_discover = None
        self._thread_reregister = None

        # Rastreamento de peers com falha de conexão
        self._peers_com_falha = {}  # {peer_id: {'timestamp': float, 'tentativas': int}}
        self._lock_falhas = threading.Lock()


    def start(self):
        try:
            self.peer_server = PeerServer(self.state)
            self.peer_server.start()
            logger.debug(f"[P2PClient] PeerServer iniciado na porta {self.state.port}")
            # Instancia e registra o MessageRouter no state
            try:
                router = MessageRouter(self.state)
                self.state.set_message_router(router)
                # Registra callback padrão que imprime mensagens recebidas no console
                try:
                    router.register_receive_callback(lambda src, payload, meta: print(f"[{src}] {payload}"))
                except Exception:
                    logger.exception("[P2PClient] Erro ao registrar callback padrão do MessageRouter")

                logger.debug("[P2PClient] MessageRouter criado e registrado no state")
            except Exception:
                logger.exception("[P2PClient] Falha ao criar MessageRouter")

            self._rodando.set()

            self._thread_discover = threading.Thread(target=self._loop_discover,
                                                    name="P2PClient_Discover",
                                                    daemon=True)
            self._thread_discover.start()
            logger.debug("[P2PClient] Loop de discover iniciado")

            self._thread_reregister = threading.Thread(target=self._loop_reregister,
                                                      name="P2PClient_Reregister",
                                                      daemon=True)
            self._thread_reregister.start()
            logger.debug("[P2PClient] Loop de re-registro iniciado")

        except Exception as e:
            logger.error(f"[P2PClient] Erro ao iniciar PeerServer: {e}")
            raise

    def stop(self):
        if not self._rodando.is_set():
            return

        self._rodando.clear()
        logger.debug("[P2PClient] Parando P2PClient...")

        try:
            # Envia BYE para todos os peers conectados antes de fechar
            conexoes = self.state.get_todas_conexoes()
            if conexoes:
                logger.info(f"[P2PClient] Enviando BYE para {len(conexoes)} peer(s)...")
                for peer_id, conexao in conexoes.items():
                    try:
                        conexao.envia_bye(reason="Encerrando aplicação")
                    except Exception as e:
                        logger.debug(f"[P2PClient] Erro ao enviar BYE para {peer_id}: {e}")

                # Aguarda brevemente para dar tempo dos BYEs serem enviados
                # e dos BYE_OKs serem recebidos (timeout de 2 segundos)
                logger.debug("[P2PClient] Aguardando envio de BYEs...")
                time.sleep(2)

            if self.peer_server:
                self.peer_server.stop()
                logger.debug("[P2PClient] PeerServer parado")

            thread_atual = threading.current_thread()

            if self._thread_discover and self._thread_discover.is_alive():
                if thread_atual != self._thread_discover:
                    self._thread_discover.join(timeout=5)

            if self._thread_reregister and self._thread_reregister.is_alive():
                if thread_atual != self._thread_reregister:
                    self._thread_reregister.join(timeout=5)

        except Exception as e:
            logger.error(f"[P2PClient] Erro ao parar threads: {e}")



    def _deve_tentar_conectar(self, peer_id: str) -> bool:
        with self._lock_falhas:
            if peer_id not in self._peers_com_falha:
                return True  # Nunca tentou antes, pode tentar

            info_falha = self._peers_com_falha[peer_id]
            tempo_desde_falha = time.time() - info_falha['timestamp']
            tentativas = info_falha['tentativas']

            # Backoff exponencial: 2^(tentativas-1) minutos, máximo 30 minutos
            backoff_minutos = min(2 ** (tentativas - 1), 30)
            backoff_segundos = backoff_minutos * 60

            if tempo_desde_falha >= backoff_segundos:
                logger.debug(f"[P2PClient] Peer {peer_id} pode ser tentado novamente (backoff de {backoff_minutos}min expirou)")
                return True

            logger.debug(f"[P2PClient] Aguardando backoff para {peer_id} (faltam {int(backoff_segundos - tempo_desde_falha)}s)")
            return False

    def _registra_falha_conexao(self, peer_id: str):
        with self._lock_falhas:
            if peer_id in self._peers_com_falha:
                self._peers_com_falha[peer_id]['tentativas'] += 1
                self._peers_com_falha[peer_id]['timestamp'] = time.time()
            else:
                self._peers_com_falha[peer_id] = {'timestamp': time.time(), 'tentativas': 1}

            tentativas = self._peers_com_falha[peer_id]['tentativas']
            backoff_minutos = min(2 ** (tentativas - 1), 30)
            logger.info(f"[P2PClient] Peer {peer_id} marcado como falho. Próxima tentativa em {backoff_minutos} minuto(s)")

    def _limpa_falha_conexao(self, peer_id: str):
        with self._lock_falhas:
            if peer_id in self._peers_com_falha:
                del self._peers_com_falha[peer_id]
                logger.debug(f"[P2PClient] Peer {peer_id} removido da lista de falhas")

    def limpar_todas_falhas(self):
        """Limpa a lista de peers com falha (usado pelo comando /reconnect)"""
        with self._lock_falhas:
            count = len(self._peers_com_falha)
            self._peers_com_falha.clear()
            logger.info(f"[P2PClient] Lista de falhas limpa ({count} peers removidos)")
            return count

    def forcar_discover(self):
        """Força um discover imediato e tenta conectar com os peers (usado pelo comando /reconnect)"""
        try:
            logger.info("[P2PClient] Forçando discover imediato...")
            peers = discover(self.state)
            meu_peer_id = self.state.peer_id

            count_tentativas = 0

            for peer in peers:
                peer_id_remoto = f"{peer['name']}@{peer['namespace']}"

                if peer_id_remoto == meu_peer_id:
                    continue

                if self.state.verifica_conexao(peer_id_remoto):
                    continue

                # Tenta conectar em paralelo (não aguarda término)
                thread = threading.Thread(
                    target=self._tentar_conectar_thread,
                    args=(peer,),
                    daemon=True
                )
                thread.start()
                count_tentativas += 1

            logger.info(f"[P2PClient] Discover forçado concluído. {count_tentativas} tentativas de conexão iniciadas em background.")
            return count_tentativas

        except RendezvousError as e:
            logger.error(f"[P2PClient] Erro ao forçar discover: {e}")
            return 0

    def _tentar_conectar_thread(self, peer: Dict[str, Any]):
        """Thread auxiliar para tentar conectar com um peer em paralelo"""
        peer_id_remoto = f"{peer['name']}@{peer['namespace']}"
        sucesso = self.conectar_com_peer(peer)
        if not sucesso:
            self._registra_falha_conexao(peer_id_remoto)

    def _loop_discover(self):
        intervalo = self.state.get_config("rendezvous", "discover_interval")
        max_threads_simultaneas = 10  # Limite de threads simultâneas

        while self._rodando.is_set():
            try:
                peers = discover(self.state)
                meu_peer_id = self.state.peer_id

                # Lista de threads para conexões em paralelo
                threads_conexao = []

                for peer in peers:
                    peer_id_remoto = f"{peer['name']}@{peer['namespace']}"

                    # Pula se for o próprio peer
                    if peer_id_remoto == meu_peer_id:
                        continue

                    # Pula se já está conectado
                    if self.state.verifica_conexao(peer_id_remoto):
                        continue

                    # Verifica backoff antes de tentar conectar
                    if not self._deve_tentar_conectar(peer_id_remoto):
                        continue

                    # Cria thread para conectar em paralelo
                    thread = threading.Thread(
                        target=self._tentar_conectar_thread,
                        args=(peer,),
                        daemon=True
                    )
                    threads_conexao.append(thread)
                    thread.start()

                    # Limita threads simultâneas
                    if len(threads_conexao) >= max_threads_simultaneas:
                        # Aguarda algumas threads terminarem antes de criar novas
                        for t in threads_conexao[:5]:
                            t.join(timeout=1)
                        # Remove threads que já terminaram
                        threads_conexao = [t for t in threads_conexao if t.is_alive()]

                # Aguarda todas as threads restantes terminarem (com timeout)
                for thread in threads_conexao:
                    thread.join(timeout=30)

            except RendezvousError as e:
                logger.error(f"[P2PClient] Erro no discover automático {e}")

            time.sleep(intervalo)

    def _loop_reregister(self):
        intervalo_verificacao = 30  # Verifica a cada 30 segundos

        while self._rodando.is_set():
            try:
                # Pega o TTL recebido e o timestamp do último registro
                ttl_recebido = self.state.ttl_recebido
                timestamp_registro = self.state.timestamp_registro

                # Se ainda não registrou, espera e continua
                if ttl_recebido is None or timestamp_registro is None:
                    time.sleep(intervalo_verificacao)
                    continue

                # Calcula quanto tempo falta para expirar
                tempo_decorrido = time.time() - timestamp_registro
                tempo_restante = ttl_recebido - tempo_decorrido

                # Threshold dinâmico: 10% do TTL ou threshold do config, o que for MENOR
                threshold_config = self.state.get_config("rendezvous", "ttl_warning_treshold")
                threshold = min(threshold_config, ttl_recebido * 0.1)

                # Se está próximo de expirar, re-registra
                if tempo_restante <= threshold:
                    logger.info(f"[P2PClient] TTL expirando em {tempo_restante:.0f}s. Iniciando re-registro...")
                    try:
                        register(self.state)
                        logger.info(f"[P2PClient] Re-registro bem-sucedido! Novo TTL: {self.state.ttl_recebido}s")
                    except RendezvousError as e:
                        logger.error(f"[P2PClient] Erro ao re-registrar: {e}")

            except Exception as e:
                logger.error(f"[P2PClient] Erro no loop de re-registro: {e}")

            time.sleep(intervalo_verificacao)


    def conectar_com_peer(self, peer_info: Dict[str, Any]) -> bool:
        ip_remoto = peer_info.get("ip")
        porta = peer_info.get("port")
        peer_id_remoto = f"{peer_info['name']}@{peer_info['namespace']}"

        ip_conexao = ip_remoto

        max_tentativas = self.state.get_config("peer_connection", "retry_attempts")
        backoff_base = self.state.get_config("peer_connection", "backoff_base")
        timeout = self.state.get_config("network", "connection_timeout")

        for tentativas in range(max_tentativas):
            try:
                logger.debug(f"[P2PClient] Tentando conectar com {peer_id_remoto} em {ip_conexao}:{porta} (tentativa {tentativas + 1}/{max_tentativas})")

                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((ip_conexao, porta))
                conexao = PeerConnection(sock, peer_id_remoto, self.state, foi_iniciado=True)

                if not conexao.handshake_iniciador():
                    logger.warning(f"[P2PClient] Handshake falhou com {peer_id_remoto}")
                    sock.close()
                    continue

                self.state.adiciona_conexao(peer_id_remoto, conexao)
                conexao.start()

                logger.info(f"[P2PClient] Conectado com sucesso a {peer_id_remoto}")
                self._limpa_falha_conexao(peer_id_remoto)  # Remove da lista de falhas
                return True

            except Exception as e:
                # Usa DEBUG em vez de WARNING para não poluir o terminal
                logger.debug(f"[P2PClient] Falha ao conectar com {peer_id_remoto} (tentativa {tentativas + 1}/{max_tentativas}): {e}")

                if tentativas < max_tentativas - 1:
                    backoff = backoff_base ** tentativas
                    logger.debug(f"[P2PClient] Aguardando {backoff}s antes de nova tentativa...")
                    time.sleep(backoff)

        # Log final apenas em DEBUG para não poluir terminal
        logger.debug(f"[P2PClient] Falha ao conectar com {peer_id_remoto} após {max_tentativas} tentativas.")
        return False
import threading
import uuid
import time
import logging
from datetime import datetime
from typing import Callable, Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, state):
        self.state = state
        self._pending_acks: Dict[str, Dict[str, Any]] = {}  # Dicionário que guarda ACKs esperados {msg_id: {"event": Event, "response": dict}}
        self._lock = threading.Lock()  # Lock para acesso thread-safe ao dicionário de pending_acks
        self._callbacks: List[Callable[[str, str, Dict[str, Any]], None]] = []  # Lista de funções callback chamadas quando mensagem é recebida

    def register_receive_callback(self, cb: Callable[[str, str, Dict[str, Any]], None]):
        # Adiciona função callback que será chamada quando uma mensagem (SEND/PUB) for recebida
        self._callbacks.append(cb)

    def _notify_receive(self, src: str, payload: str, meta: Dict[str, Any]):
        # Chama todos os callbacks registrados para notificar recebimento de mensagem
        for cb in self._callbacks:
            try:
                cb(src, payload, meta)  # Executa callback com source, payload e metadados
            except Exception:
                # Captura exceções dos callbacks para evitar que erro em um callback afete outros
                logger.exception("Erro no callback de recebimento de mensagem")

    def send(
        self,
        dst: str,
        payload: str,
        require_ack: bool = True,
        ttl: int = 1,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        # Obtém configurações de timeout e retries do config.json (com fallbacks)
        cfg_timeout = self.state.get_config("network", "ack_timeout") or 5
        cfg_retries = self.state.get_config("message_router", "max_retries") or 2

        # Usa valores passados como parâmetro ou valores do config
        timeout = timeout or cfg_timeout
        retries = retries if retries is not None else cfg_retries

        # Verifica se o peer está conectado
        peer_conn = self.state.get_conexao(dst)
        if not peer_conn:
            logger.warning(f"[MessageRouter] Peer {dst} não conectado")
            return False, None

        # Gera ID único para a mensagem
        msg_id = str(uuid.uuid4())
        msg = {
            "type": "SEND",
            "msg_id": msg_id,
            "src": self.state.get_peer_info(),
            "dst": dst,
            "payload": payload,
            "require_ack": require_ack,
            "ttl": ttl,
        }

        # Cria estrutura para aguardar ACK com Event (para sincronização entre threads)
        pending = {"event": threading.Event(), "response": None}

        # Registra ACK pendente no dicionário (thread-safe)
        with self._lock:
            self._pending_acks[msg_id] = pending

        # Loop de retry com backoff exponencial
        attempt = 0
        while attempt <= retries:
            try:
                logger.debug(f"[MessageRouter] Enviando SEND {msg_id} para {dst} (tentativa {attempt + 1})")
                peer_conn.enqueue_msg(msg)  # Envia mensagem para fila de envio

                # Aguarda ACK com timeout (Event.wait() bloqueia até set() ser chamado ou timeout)
                ok = pending["event"].wait(timeout)
                if ok:
                    # ACK recebido: desbloqueia Event e retorna resposta
                    logger.debug(f"[MessageRouter] ACK recebido para {msg_id}")
                    with self._lock:
                        resp = self._pending_acks.pop(msg_id, {}).get("response")
                    return True, resp
                else:
                    # Timeout: tenta novamente com backoff exponencial
                    attempt += 1
                    if attempt <= retries:
                        backoff = 2 ** (attempt - 1)  # Backoff: 1s, 2s, 4s, 8s...
                        logger.info(f"[MessageRouter] Timeout aguardando ACK, retry em {backoff}s")
                        time.sleep(backoff)
                    else:
                        logger.warning(
                            f"[MessageRouter] Falha: ACK não recebido para {msg_id} após {retries + 1} tentativas"
                        )
                        break
            except Exception as e:
                logger.exception(f"[MessageRouter] Erro ao enviar SEND para {dst}: {e}")
                break

        # Remove pending ACK do dicionário (não recebeu resposta)
        with self._lock:
            self._pending_acks.pop(msg_id, None)

        return False, None

    def publish(self, dst: str, payload: str, ttl: int = 1) -> int:
        # Obtém todas as conexões ativas
        conexoes = self.state.get_todas_conexoes()
        count = 0  # Contador de mensagens enviadas

        # Itera sobre todas as conexões para enviar PUB
        for peer_id, conn in conexoes.items():
            if dst == "*":
                # Broadcast: envia para TODOS os peers conectados
                msg = {
                    "type": "PUB",
                    "msg_id": str(uuid.uuid4()),
                    "src": self.state.get_peer_info(),
                    "dst": dst,
                    "payload": payload,
                    "ttl": ttl,
                }
                conn.enqueue_msg(msg)
                logger.debug(f"[MessageRouter] PUB enviado para {peer_id} (broadcast)")
                count += 1
            elif dst.startswith("#"):
                # Namespace-cast: envia apenas para peers do namespace especificado
                ns = dst.lstrip("#")  # Remove o # do início (ex: "#CIC" -> "CIC")
                parts = peer_id.split("@")  # Separa nome e namespace (ex: "alice@CIC" -> ["alice", "CIC"])
                if len(parts) == 2 and parts[1] == ns:  # Verifica se o namespace do peer corresponde
                    msg = {
                        "type": "PUB",
                        "msg_id": str(uuid.uuid4()),
                        "src": self.state.get_peer_info(),
                        "dst": dst,
                        "payload": payload,
                        "ttl": ttl,
                    }
                    conn.enqueue_msg(msg)
                    logger.debug(f"[MessageRouter] PUB enviado para {peer_id} (namespace #{ns})")
                    count += 1

        # Log do resultado final baseado na quantidade de peers que receberam
        if count == 0:
            if dst == "*":
                logger.warning(f"[MessageRouter] PUB broadcast: nenhum peer conectado")
            else:
                ns = dst.lstrip("#")
                logger.warning(f"[MessageRouter] PUB #{ns}: nenhum peer do namespace encontrado")
        else:
            logger.info(f"[MessageRouter] PUB {dst}: mensagem enviada para {count} peer(s)")

        return count

    def process_incoming(self, msg: Dict[str, Any], peer_conn) -> None:
        # Processa mensagens recebidas (ACK/SEND/PUB) e roteia para tratamento adequado
        t = msg.get("type")
        try:
            if t == "ACK":
                # ACK recebido: desbloqueia thread que está aguardando no send()
                orig_id = msg.get("msg_id")
                with self._lock:
                    pending = self._pending_acks.get(orig_id)
                    if pending:
                        pending["response"] = msg  # Armazena resposta ACK
                        pending["event"].set()  # Desbloqueia Event.wait() no método send()
                    else:
                        logger.debug(f"[MessageRouter] ACK para mensagem desconhecida {orig_id}")

            elif t == "SEND":
                # SEND recebido: notifica callbacks e envia ACK se necessário
                src = msg.get("src")
                payload = msg.get("payload")
                require_ack = msg.get("require_ack", False)

                # Notifica todos os callbacks registrados (ex: imprime mensagem no console)
                self._notify_receive(src, payload, {"type": "SEND", "msg": msg})

                # Envia ACK de volta se a mensagem requer confirmação
                if require_ack:
                    ack = {
                        "type": "ACK",
                        "msg_id": msg.get("msg_id"),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "src": self.state.get_peer_info(),
                        "dst": src,
                        "ttl": 1,
                    }
                    try:
                        peer_conn.enqueue_msg(ack)  # Enfileira ACK para envio
                    except Exception:
                        logger.exception("Erro ao enviar ACK")

            elif t == "PUB":
                # PUB recebido: notifica callbacks (não requer ACK)
                src = msg.get("src")
                payload = msg.get("payload")
                self._notify_receive(src, payload, {"type": "PUB", "msg": msg})

            else:
                # Tipo de mensagem desconhecido (ignora)
                logger.debug(f"[MessageRouter] Ignorando tipo de mensagem desconhecida: {t}")

        except Exception:
            logger.exception("[MessageRouter] Erro ao processar mensagem recebida")

    def shutdown(self):
        # Desbloqueia todas as threads aguardando ACKs e limpa o dicionário
        with self._lock:
            for k, v in list(self._pending_acks.items()):
                try:
                    v["response"] = None  # Marca resposta como None (não recebida)
                    v["event"].set()  # Desbloqueia Event.wait() para liberar threads travadas
                except Exception:
                    pass
            self._pending_acks.clear()  # Limpa dicionário de ACKs pendentes

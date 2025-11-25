import threading
import uuid
import time
import logging
from datetime import datetime
from typing import Callable, Dict, Any, Optional, Tuple, List

logger = logging.getLogger(__name__)


class MessageRouter:
    """Gerencia SEND/ACK/PUB de alto nível.

    - send() envia SEND e espera ACK (opcional) com timeout/retries
    - publish() envia PUB para peers conectados
    - process_incoming() deve ser chamado por PeerConnection ao receber SEND/ACK/PUB
    - callbacks: lista de funções (src, payload, meta)
    """
    def __init__(self, state):
        self.state = state
        self._pending_acks: Dict[str, Dict[str, Any]] = {}
    self._lock = threading.Lock()
    self._callbacks: List[Callable[[str, str, Dict[str, Any]], None]] = []

    def register_receive_callback(self, cb: Callable[[str, str, Dict[str, Any]], None]):
        self._callbacks.append(cb)

    def _notify_receive(self, src: str, payload: str, meta: Dict[str, Any]):
        for cb in self._callbacks:
            try:
                cb(src, payload, meta)
            except Exception:
                logger.exception("Erro no callback de recebimento de mensagem")

    def send(self, dst: str, payload: str, require_ack: bool = True, ttl: int = 1,
             timeout: Optional[float] = None, retries: Optional[int] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        cfg_timeout = self.state.get_config("network", "ack_timeout") or 5
        cfg_retries = self.state.get_config("message_router", "max_retries") or 2

        timeout = timeout or cfg_timeout
        retries = retries if retries is not None else cfg_retries

        peer_conn = self.state.get_conexao(dst)
        if not peer_conn:
            logger.warning(f"[MessageRouter] Peer {dst} não conectado")
            return False, None

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

        pending = {
            "event": threading.Event(),
            "response": None,
        }

        with self._lock:
            self._pending_acks[msg_id] = pending

        attempt = 0
        while attempt <= retries:
            try:
                logger.debug(f"[MessageRouter] Enviando SEND {msg_id} para {dst} (attempt {attempt + 1})")
                peer_conn.enqueue_msg(msg)

                ok = pending["event"].wait(timeout)
                if ok:
                    logger.debug(f"[MessageRouter] ACK recebido para {msg_id}")
                    with self._lock:
                        resp = self._pending_acks.pop(msg_id, {}).get("response")
                    return True, resp
                else:
                    attempt += 1
                    if attempt <= retries:
                        backoff = 2 ** (attempt - 1)
                        logger.info(f"[MessageRouter] Timeout aguardando ACK, retry em {backoff}s")
                        time.sleep(backoff)
                    else:
                        logger.warning(f"[MessageRouter] Falha: ACK não recebido para {msg_id} após {retries + 1} tentativas")
                        break

            except Exception as e:
                logger.exception(f"[MessageRouter] Erro ao enviar SEND para {dst}: {e}")
                break

        with self._lock:
            self._pending_acks.pop(msg_id, None)

        return False, None

    def publish(self, dst: str, payload: str, ttl: int = 1):
        # dst: '*' para todos, '#NAMESPACE' para namespace
        conexoes = self.state.get_todas_conexoes()
        for peer_id, conn in conexoes.items():
            if dst == '*':
                msg = {
                    "type": "PUB",
                    "msg_id": str(uuid.uuid4()),
                    "src": self.state.get_peer_info(),
                    "dst": dst,
                    "payload": payload,
                    "ttl": ttl,
                }
                conn.enqueue_msg(msg)
            elif dst.startswith('#'):
                ns = dst.lstrip('#')
                # peer_id format: name@namespace
                parts = peer_id.split('@')
                if len(parts) == 2 and parts[1] == ns:
                    msg = {
                        "type": "PUB",
                        "msg_id": str(uuid.uuid4()),
                        "src": self.state.get_peer_info(),
                        "dst": dst,
                        "payload": payload,
                        "ttl": ttl,
                    }
                    conn.enqueue_msg(msg)

    def process_incoming(self, msg: Dict[str, Any], peer_conn) -> None:
        t = msg.get("type")
        try:
            if t == "ACK":
                orig_id = msg.get("msg_id")
                with self._lock:
                    pending = self._pending_acks.get(orig_id)
                    if pending:
                        pending["response"] = msg
                        pending["event"].set()
                    else:
                        logger.debug(f"[MessageRouter] ACK para mensagem desconhecida {orig_id}")

            elif t == "SEND":
                src = msg.get("src")
                payload = msg.get("payload")
                require_ack = msg.get("require_ack", False)

                # entregar ao aplicativo
                self._notify_receive(src, payload, {"type": "SEND", "msg": msg})

                # enviar ACK se necessário
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
                        peer_conn.enqueue_msg(ack)
                    except Exception:
                        logger.exception("Erro ao enviar ACK")

            elif t == "PUB":
                src = msg.get("src")
                payload = msg.get("payload")
                # entregar ao aplicativo
                self._notify_receive(src, payload, {"type": "PUB", "msg": msg})

            else:
                logger.debug(f"[MessageRouter] Ignorando tipo de mensagem desconhecida: {t}")

        except Exception:
            logger.exception("[MessageRouter] Erro ao processar mensagem recebida")

    def shutdown(self):
        with self._lock:
            for k, v in list(self._pending_acks.items()):
                try:
                    v["response"] = None
                    v["event"].set()
                except Exception:
                    pass
            self._pending_acks.clear()

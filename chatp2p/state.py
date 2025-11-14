import threading
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class State:
    def __init__(self, config_path: str = "config.json"):
        self._lock = threading.RLock() # Lock principal para proteger o estado compartilhado
        self.config =  self._load_config(config_path) # Carrega a configuração inicial do arquivo JSON
        
        # Informações do peer local (iniciar com None, pois o usuário irá definir pelo CLI as informações)
        self.name: Optional[str] = None
        self.namespace: Optional[str] = None
        self.port: Optional[int] = None
        self.ttl: Optional[int] = None
        self.peer_id: Optional[str] = None
        self.tempo_ultimo_registro: Optional[datetime] = None # Último horário de registro no servidor (para controlar o TTL no servidor rdzv)
        
        self._conexoes: Dict[str, Any] = {} # Dicionário de conexões ativas {peer_id: PeerConnection}
        
        self._flag_encerrado = threading.Event() # Flag para indicar se o programa está sendo encerrado
        
    # Função para acessar as configurações json
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        path = Path(config_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
        
        with open (path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config
    
    # Função set para definir as informações do peer local	
    def set_peer_info(self, name: str, namespace: str, port: int, ttl: int):
        with self._lock:
            self.name = name
            self.namespace = namespace
            self.port = port
            self.ttl = ttl
            self.peer_id = f"{name}@{namespace}"
            self.tempo_ultimo_registro = datetime.now()
        
    # Função get para obter as informações do peer local
    def get_peer_info(self) -> Optional[str]:
        with self._lock:
            return self.peer_id
    
    # Função para calcular quanto tempo resta do TTL no servidor rdzv
    def get_ttl_restante(self) -> Optional[int]:
        with self._lock:
            if self.tempo_ultimo_registro is None or self.ttl is None:
                return None
            
            tempo_passado = (datetime.now() - self.tempo_ultimo_registro).total_seconds()
            tempo_restante = self.ttl - tempo_passado
            return max(0, int(tempo_restante))
    
    def adiciona_conexao(self, peer_id: str, conexao):
        with self._lock:
            self._conexoes[peer_id] = conexao
            logger.info(f"[State] Conexão adicionada: {peer_id}")
    
    # Função para remover uma conexão do dicionário de conexões ativas
    def remove_conexao(self, peer_id: str):
        with self._lock:
            if peer_id in self._conexoes:
                del self._conexoes[peer_id]
                logger.info(f"[State] Conexão removida: {peer_id}")
    
    # Função get para obter conexão com um peer específico 
    def get_conexao(self, peer_id: str):
        with self._lock:
            return self._conexoes.get(peer_id)
    
    # Função get para obter todas as conexões ativas
    def get_todas_conexoes(self) -> Dict[str, Any]:
        with self._lock:
            return self._conexoes.copy()
        
    # Função get para peer_ids com conexões ativas
    def get_peer_ids_conectados(self) -> list:
        with self._lock:
            return list(self._conexoes.keys())
    
    # Função para verificar se existe conexão ativa com um peer específico
    def verifica_conexao(self, peer_id: str) -> bool:
        with self._lock:
            return peer_id in self._conexoes
    
    # Função set para sinalizar que o programa deve ser encerrado
    def set_encerrado(self):
        return self._flag_encerrado.is_set()
    
    # Função que verifica se foi sinalizado o encerramento
    def foi_encerrado(self) -> bool:
        return self._flag_encerrado.is_set()
    
    def get_config(self, *keys) -> Any:
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

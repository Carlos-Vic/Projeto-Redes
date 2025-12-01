import logging
import json
import sys

def configurar_logging(config_path="config.json"):
    # Carregar configurações do JSON
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Pegar configurações
    nivel = config.get("logging", {}).get("level", "INFO").upper()
    log_arquivo = config.get("logging", {}).get("log_to_file", False)
    arquivo = config.get("logging", {}).get("file", "chatp2p.log")

    # Converter string para nível do logging
    nivel_logging = getattr(logging, nivel, logging.INFO)

    # Formato das mensagens
    formato = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    data_formato = '%H:%M:%S'

    # Criar lista de handlers
    handlers = []

    # Handler para console (terminal)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(nivel_logging)
    console_handler.setFormatter(logging.Formatter(formato, datefmt=data_formato))
    handlers.append(console_handler)

    # Handler para arquivo (se configurado)
    if log_arquivo:
        file_handler = logging.FileHandler(arquivo, encoding='utf-8')
        file_handler.setLevel(nivel_logging)
        file_handler.setFormatter(logging.Formatter(formato, datefmt=data_formato))
        handlers.append(file_handler)

    # Configurar logging root
    logging.basicConfig(
        level=nivel_logging,
        handlers=handlers,
        force=True  # Sobrescreve configuração anterior se existir
    )

"""
Chat P2P - Sistema de Chat Peer-to-Peer
Disciplina: Redes de Computadores
Universidade de Brasília (UnB)

Grupo 7:
    - Carlos Victor Albuquerque Oliveira - 232009558
    - Lucas Sena de Almeida - 190112310
    - Wilianne Quaresma Paixão - 190134127
"""

from cli import CLI
import os
import sys
from logger import configurar_logging

def main():
    # Ponto de entrada principal: configura logging e inicia CLI
    config_path = "config.json"  # Caminho padrão para o arquivo de configuração

    # Verifica se o arquivo de configuração existe antes de prosseguir
    if not os.path.exists(config_path):
        print(f"Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)  # Sai com código de erro 1

    # Configura sistema de logging baseado no config.json
    configurar_logging(config_path)

    try:
        cli = CLI(config_path)  # Inicializa a interface de linha de comando
        cli.run()  # Inicia loop principal do CLI
    except KeyboardInterrupt:  # Captura interrupção do usuário (Ctrl+C)
        print("\nPrograma encerrado pelo usuário.")
        sys.exit(0)
    except Exception as e:  # Captura qualquer outra exceção inesperada
        print(f"Erro inesperado: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
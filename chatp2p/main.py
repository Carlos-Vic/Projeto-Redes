from cli import CLI
import os
import sys
from logger import configurar_logging

def main():
    config_path = "config.json"  # Caminho padrão para o arquivo de configuração
    
    if not os.path.exists(config_path): # Verifica se o arquivo de configuração existe
        print(f"Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1) # Sai com código de erro 1
        
    configurar_logging(config_path)
        
    try:
        cli = CLI(config_path) # Inicializa a interface de linha de comando
        cli.run()
    except KeyboardInterrupt: # Captura interrupção do usuário (Ctrl+C)
        print("\nPrograma encerrado pelo usuário.")
        sys.exit(0)
    except Exception as e: # Captura qualquer outra exceção inesperada
        print(f"Erro inesperado: {e}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()
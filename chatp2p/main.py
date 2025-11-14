from cli import CLI
import os
import sys

def main():
    config_path = "config.json"  # Caminho padrão para o arquivo de configuração
    
    if not os.path.exists(config_path):
        print(f"Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)
        
    try:
        cli = CLI(config_path)
        cli.run()
    except KeyboardInterrupt:
        print("\nPrograma encerrado pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
if __name__ == "__main__":
    main()
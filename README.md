# Chat P2P - Sistema de Chat Peer-to-Peer

Sistema de chat P2P desenvolvido em Python que permite comunicação direta entre usuários. Utiliza um Servidor Rendezvous para descoberta de peers, mas toda a comunicação ocorre diretamente peer-to-peer.

**Projeto Final de Redes de Computadores - UnB (2025.2)**

Este projeto foi desenvolvido como trabalho final da disciplina de Redes de Computadores da Universidade de Brasília (UnB) no semestre 2025.2. O Servidor Rendezvous foi implementado pelo professor da disciplina e está disponível em: https://github.com/mfcaetano/pyp2p-rdv

## Grupo 7
- Carlos Victor Albuquerque Oliveira
- Lucas Sena de Almeida
- Wilianne Quaresma Paixão

---

##  Funcionalidades

Este cliente P2P implementa o protocolo completo de comunicação peer-to-peer:

- **HELLO/HELLO_OK** - Handshake inicial entre peers
- **PING/PONG** - Keep-alive automático (a cada 30s) com cálculo de RTT
- **SEND/ACK** - Mensagens diretas com confirmação de recebimento
- **PUB** - Broadcast global (`*`) ou por namespace (`#namespace`)
- **BYE/BYE_OK** - Encerramento gracioso de conexões
- **Reconexão automática** - Tentativas com backoff exponencial em caso de falha
- **Descoberta periódica** - Atualização automática da lista de peers a cada 60s

---

##  Como Funciona

1. **Registro**: Peer se registra no Servidor Rendezvous com seu `peer_id` (`nome@namespace`), IP, porta e TTL
2. **Descoberta**: Peer solicita periodicamente a lista de peers ativos no Rendezvous
3. **Conexão**: Estabelece conexões TCP diretas com cada peer descoberto (handshake HELLO/HELLO_OK)
4. **Comunicação**: Troca mensagens diretamente com outros peers (sem passar pelo Rendezvous)
5. **Keep-alive**: Mantém conexões ativas enviando PING/PONG a cada 30 segundos
6. **Encerramento**: Ao sair, envia BYE para todos os peers e desregistra do Rendezvous

---

##  Como Usar

### 1. Clonar o Repositório

```bash
git clone https://github.com/Carlos-Vic/Projeto-Redes.git
cd Projeto-Redes
```

### 2. Rodar o Servidor Rendezvous (Terminal 1)

O **Servidor Rendezvous** funciona como um "ponto de encontro" centralizado que permite aos peers:
- **Registrarem-se** ao entrar na rede
- **Descobrirem outros peers** ativos (comando `DISCOVER`)
- **Desregistrarem-se** ao sair da rede

**Importante:** O Rendezvous **não** participa da comunicação entre peers. Ele apenas mantém uma lista de peers ativos. Toda a troca de mensagens ocorre **diretamente** entre os peers via conexões TCP peer-to-peer.

```bash
cd pyp2p-rdv-main/src/rendezvous
python main.py
```

O servidor iniciará na porta **8080**.

### 3. Rodar o Chat P2P (Terminal 2)

Em outro terminal, inicie o primeiro peer:

```bash
cd chatp2p
python main.py
```

Você será solicitado a fornecer os seguintes parâmetros:

#### Parâmetros de Inicialização

| Parâmetro | Descrição | Validação | Exemplo |
|-----------|-----------|-----------|---------|
| **Namespace** | Agrupador lógico que define o "grupo" ou "sala" do peer. Peers em namespaces diferentes podem se comunicar, mas o namespace é usado para mensagens direcionadas (`pub #namespace`). | Máximo 64 caracteres, não pode ser vazio | `CIC`, `UnB`, `grupo7` |
| **Nome** | Identificador único do peer dentro do namespace. Forma o `peer_id` como `nome@namespace`. | Máximo 64 caracteres, não pode ser vazio | `alice`, `bob`, `carlos` |
| **Porta** | Porta TCP na qual o peer irá escutar conexões de outros peers (inbound). Cada peer precisa de uma porta única. | Deve estar entre 1 e 65535 | `5000`, `5001` |
| **TTL** | Tempo de vida (Time-To-Live) do registro no servidor Rendezvous, em segundos. Após esse tempo, o peer precisa renovar seu registro. | Deve estar entre 1 e 86400 segundos. Padrão: 7200s (2 horas) | Pressione Enter para usar 7200, ou digite valor desejado |

### 4. Rodar Outro Peer (Terminal 3)

Para testar localmente, abra um terceiro terminal e repita o passo 3 com **nome e porta diferentes**:

```bash
cd chatp2p
python main.py
```

Use, por exemplo:
- Nome: `bob`
- Porta: `5001`

---

##  Comandos Disponíveis

| Comando | Descrição |
|---------|-----------|
| `peers` | Lista todos os peers descobertos |
| `msg <peer_id> <mensagem>` | Envia mensagem direta (ex: `msg bob@CIC Oi!`) |
| `pub * <mensagem>` | Broadcast para todos os peers conectados |
| `pub #<namespace> <mensagem>` | Envia mensagem para namespace específico |
| `conn` | Mostra conexões ativas |
| `status` | Mostra status de peers (conectados e falhos) |
| `rtt` | Exibe RTT (Round Trip Time) médio |
| `reconnect` | Força reconexão com peers |
| `log <LEVEL>` | Ajusta nível de log (DEBUG, INFO, WARNING) |
| `help` | Exibe ajuda |
| `quit` | Sai do programa |

---

##  Configuração

O arquivo `chatp2p/config.json` contém as configurações do sistema.

**Para testes locais** (múltiplos terminais na mesma máquina), o host está configurado como `127.0.0.1`:

```json
{
    "rendezvous": {
        "host": "127.0.0.1",
        "port": 8080
    }
}
```

**Para uso em rede**, altere `host` para o IP do servidor Rendezvous.

---

##  Arquitetura do Código

```
chatp2p/
├── main.py                     # Inicialização da aplicação
├── cli.py                      # Interface de linha de comando
├── p2p_client.py               # Orquestração do cliente P2P
├── rendezvous_connection.py    # Comunicação com servidor Rendezvous
├── peer_server.py              # Servidor TCP para conexões inbound
├── peer_connection.py          # Gerenciamento de conexões TCP peer-to-peer
├── message_router.py           # Roteamento de mensagens SEND/PUB
├── keep_alive.py               # Keep-alive (PING/PONG) e cálculo de RTT
├── state.py                    # Estado compartilhado entre threads
├── logger.py                   # Configuração de logging
└── config.json                 # Configurações do sistema
```

---

##  Exemplo de Uso

### Terminal 1 - Servidor Rendezvous
```bash
$ python main.py
Servidor rodando na porta 8080...
```

### Terminal 2 - Alice
```bash
$ python main.py
Namespace: CIC
Nome: alice
Porta: 5000
TTL: [Enter]

chatp2p> peers
- bob@CIC (127.0.0.1:5001)

chatp2p> msg bob@CIC Olá Bob!
Mensagem enviada (ACK recebido)
```

### Terminal 3 - Bob
```bash
$ python main.py
Namespace: CIC
Nome: bob
Porta: 5001
TTL: [Enter]

chatp2p> [alice@CIC] Olá Bob!
```

---

##  Requisitos

- Python 3.8+
- Sistema operacional: Linux/Windows (testado em WSL)
- Bibliotecas: apenas biblioteca padrão do Python (sem dependências externas)

---

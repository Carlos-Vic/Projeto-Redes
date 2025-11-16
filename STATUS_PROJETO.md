# Status do Projeto - Chat P2P

**Disciplina:** CIC0124 - Redes de Computadores
**Projeto:** Cliente de Chat P2P
**Última atualização:** 2025-01-16

---

## 📋 Índice
- [Visão Geral](#visão-geral)
- [Arquivos Implementados](#arquivos-implementados)
- [Funcionalidades Implementadas](#funcionalidades-implementadas)
- [Funcionalidades Pendentes](#funcionalidades-pendentes)
- [Como Executar](#como-executar)
- [Configurações](#configurações)

---

## 🎯 Visão Geral

Este projeto implementa um **cliente de Chat P2P** que se conecta a um servidor Rendezvous, descobre outros peers automaticamente e estabelece conexões TCP diretas para troca de mensagens.

### Status Atual: **~60% Completo**

✅ **Implementado:**
- Registro e descoberta de peers (REGISTER, DISCOVER, UNREGISTER)
- Conexões TCP persistentes entre peers (HELLO/HELLO_OK)
- Keep-alive automático (PING/PONG com cálculo de RTT)
- Discovery e conexão automática periódica
- Prevenção de conexões duplicadas
- Encerramento de conexões (BYE/BYE_OK)
- CLI básico com comandos `peers`, `conn`, `unregister`, `help`, `quit`
- Sistema de logs configurável

❌ **Pendente:**
- Mensageria entre peers (SEND/ACK e PUB)
- Comandos CLI `/msg`, `/pub`, `/rtt`, `/reconnect`, `/log`
- Reconexão automática de peers desconectados
- Módulos `message_router.py` e `peer_table.py`

---

## 📁 Arquivos Implementados

### 1. **main.py**
**Descrição:** Ponto de entrada da aplicação.

**Funções:**
- `main()`: Inicializa o sistema de logging, verifica se o config.json existe e inicia o CLI.

---

### 2. **config.json**
**Descrição:** Arquivo de configuração do projeto.

**Estrutura:**
```json
{
  "rendezvous": {
    "host": "pyp2p.mfcaetano.cc",
    "port": 8080,
    "discover_interval": 60,
    "register_retry_attempts": 3,
    "register_backoff_base": 2,
    "ttl_warning_treshold": 60
  },
  "network": {
    "ack_timeout": 20,
    "max_msg_size": 32768,
    "connection_timeout": 90
  },
  "peer_connection": {
    "retry_attempts": 3,
    "backoff_base": 2
  },
  "reconnection": {
    "max_attempts": 5,
    "backoff_base": 2,
    "backoff_max": 32,
    "check_interval": 10
  },
  "keepalive": {
    "ping_interval": 30,
    "ping_timeout": 10,
    "max_ping_failures": 3
  },
  "logging": {
    "level": "DEBUG",
    "log_to_file": true,
    "file": "chatp2p.log"
  }
}
```

**Parâmetros importantes:**
- `logging.level`: Altere de `"DEBUG"` para `"INFO"` para reduzir verbosidade dos logs
- `discover_interval`: Intervalo em segundos entre descobertas automáticas (padrão: 60s)
- `keepalive.ping_interval`: Intervalo entre PINGs (padrão: 30s)
- `network.connection_timeout`: Timeout do socket TCP em segundos (padrão: 90s)
  - **IMPORTANTE:** Deve ser **3x maior** que `ping_interval` para evitar timeouts durante keep-alive
  - Se muito baixo, conexões são fechadas antes do próximo PING chegar
  - Valor recomendado: 90s (permite até 2 PINGs perdidos)

---

### 3. **logger.py**
**Descrição:** Configuração do sistema de logging.

**Funções:**
- `configurar_logging(config_path)`: Configura o logging baseado no config.json. Cria handlers para console (stdout) e arquivo (se habilitado).

---

### 4. **state.py**
**Descrição:** Gerenciamento do estado compartilhado do peer (thread-safe).

**Classe:** `State`

**Atributos:**
- `name`, `namespace`, `port`, `ttl`: Informações do peer local
- `peer_id`: Identificador formatado como `name@namespace`
- `_conexoes`: Dicionário de conexões ativas {peer_id: PeerConnection}

**Métodos principais:**
- `set_peer_info(name, namespace, port, ttl)`: Define as informações do peer local
- `get_peer_info()`: Retorna o peer_id
- `adiciona_conexao(peer_id, conexao)`: Adiciona uma conexão ao dicionário
- `remove_conexao(peer_id)`: Remove uma conexão do dicionário
- `verifica_conexao(peer_id)`: Verifica se existe conexão ativa com um peer
- `get_todas_conexoes()`: Retorna cópia de todas as conexões ativas
- `get_config(*keys)`: Acessa valores do config.json de forma segura

---

### 5. **rendezvous_connection.py**
**Descrição:** Comunicação com o servidor Rendezvous.

**Classes de Exceção:**
- `RendezvousError`: Exceção base
- `RendezvousServerErro`: Erro retornado pelo servidor
- `RendezvousConnectionError`: Erro de conexão TCP

**Funções:**
- `_envia_comando(host, port, command, timeout)`: Envia comando JSON ao servidor e retorna resposta
- `register(state, retry)`: Registra o peer no servidor com retry automático e backoff exponencial
- `discover(state, namespace)`: Descobre peers registrados (todos ou de um namespace específico)
- `unregister(state)`: Remove o registro do peer do servidor

**Protocolo:**
- Mensagens JSON delimitadas por `\n`
- Tamanho máximo: 32KB
- Retry com backoff exponencial (1s, 2s, 4s...)

---

### 6. **peer_connection.py**
**Descrição:** Gerenciamento de uma conexão TCP com um peer remoto.

**Classe:** `PeerConnection`

**Atributos principais:**
- `sock`: Socket TCP da conexão
- `peer_id_remoto`: ID do peer remoto
- `foi_iniciado`: Flag indicando se este peer iniciou a conexão (True = outbound, False = inbound)
- `keep_alive`: Instância do KeepAlive (somente para conexões outbound)
- `_envia_queue`: Fila thread-safe para mensagens a enviar
- `_rodando`: Event para controlar threads

**Métodos principais:**
- `start()`: Inicia threads de leitura, escrita e keep-alive (se outbound)
- `stop()`: Para threads e encerra conexão
- `handshake_iniciador()`: Realiza handshake HELLO/HELLO_OK como iniciador
- `handshake_receptor(msg_hello)`: Realiza handshake como receptor
- `envia_ping()`: Envia mensagem PING
- `envia_bye(reason)`: Envia mensagem BYE para encerrar conexão
- `_loop_de_leitura()`: Thread que recebe mensagens do peer
- `_loop_de_escrita()`: Thread que envia mensagens da fila
- `_processa_msg_recebida(msg)`: Processa mensagens recebidas (PING, PONG, BYE, BYE_OK)

**Protocolo implementado:**
- ✅ HELLO / HELLO_OK
- ✅ PING / PONG
- ✅ BYE / BYE_OK
- ❌ SEND / ACK (pendente)
- ❌ PUB (pendente)

---

### 7. **keep_alive.py**
**Descrição:** Gerenciamento de PING/PONG para manter conexões ativas.

**Classe:** `KeepAlive`

**Atributos:**
- `conexao`: Referência para PeerConnection
- `_falhas`: Contador de PINGs consecutivos sem resposta
- `_pings_pendentes`: Dicionário {msg_id: timestamp} para cálculo de RTT

**Métodos:**
- `start()`: Inicia thread de envio periódico de PINGs
- `stop()`: Para thread de keep-alive
- `_loop_ping()`: Envia PING a cada 30s, verifica falhas consecutivas (máx 3)
- `processa_pong(msg_pong)`: Processa PONG recebido, calcula RTT em ms, reseta contador de falhas

**Comportamento:**
- Envia PING a cada 30 segundos (configurável)
- Calcula RTT (Round Trip Time) em milissegundos
- Fecha conexão após 3 falhas consecutivas

---

### 8. **peer_server.py**
**Descrição:** Servidor TCP que aceita conexões de outros peers (inbound).

**Classe:** `PeerServer`

**Métodos:**
- `start()`: Inicia servidor TCP na porta configurada e thread de aceitação
- `stop()`: Para servidor e fecha socket
- `_aceitar_conexoes()`: Loop que aceita novas conexões TCP
- `_handle_conexao(cliente_socket, endereco)`: Processa nova conexão: recebe HELLO, verifica duplicata, realiza handshake, adiciona ao state

**Funcionamento:**
1. Aceita conexão TCP
2. Recebe mensagem HELLO
3. Verifica se já existe conexão com esse peer_id (prevenção de duplicatas)
4. Realiza handshake como receptor (HELLO_OK)
5. Adiciona conexão ao state
6. Inicia threads de leitura/escrita

---

### 9. **p2p_client.py**
**Descrição:** Coordenador principal do sistema P2P.

**Classe:** `P2PClient`

**Métodos:**
- `start()`: Inicia PeerServer e thread de discovery periódico
- `stop()`: Para PeerServer e thread de discovery
- `_loop_discover()`: Loop que executa discover a cada 60s e conecta automaticamente com peers descobertos
- `conectar_com_peer(peer_info)`: Tenta conectar com um peer usando retry e backoff exponencial (3 tentativas)

**Funcionamento:**
1. Inicia PeerServer (aceita conexões inbound)
2. A cada 60 segundos:
   - Faz DISCOVER no servidor Rendezvous
   - Filtra o próprio peer_id
   - Para cada peer descoberto:
     - Verifica se já existe conexão
     - Se não existe, tenta conectar (com retry)

**Prevenção de duplicatas:**
- Verifica antes de conectar se já existe conexão ativa
- PeerServer também verifica antes de aceitar

---

### 10. **cli.py**
**Descrição:** Interface de linha de comando (CLI).

**Classe:** `CLI`

**Métodos de comandos:**
- `cmd_setup()`: Pede informações do peer (namespace, name, porta, TTL)
- `cmd_registrar()`: Registra no servidor Rendezvous
- `cmd_discover(args)`: Descobre e lista peers manualmente
- `cmd_unregister()`: Remove registro do servidor
- `cmd_conn()`: Mostra conexões ativas (separadas em inbound/outbound)
- `cmd_help()`: Mostra comandos disponíveis

**Método principal:**
- `run()`: Fluxo automático:
  1. Setup (pede informações)
  2. Registro no Rendezvous
  3. Inicia P2PClient (servidor + discovery automático)
  4. Loop de comandos
  5. Cleanup ao sair (para P2PClient, desregistra)

**Comandos implementados:**
- ✅ `peers [namespace]` - Descobre peers
- ✅ `conn` - Mostra conexões ativas
- ✅ `unregister` - Desregistra do servidor
- ✅ `help` - Mostra ajuda
- ✅ `quit` / `exit` - Sai do programa

---

## ✅ Funcionalidades Implementadas

### 1. Integração com Servidor Rendezvous
- ✅ REGISTER com retry automático e backoff exponencial
- ✅ DISCOVER periódico (a cada 60s)
- ✅ UNREGISTER ao sair

### 2. Conexões TCP entre Peers
- ✅ Handshake HELLO/HELLO_OK
- ✅ Servidor aceita conexões inbound
- ✅ Cliente conecta automaticamente (outbound)
- ✅ Prevenção de conexões duplicadas
- ✅ Threads separadas para leitura e escrita

### 3. Keep-Alive
- ✅ PING/PONG a cada 30 segundos
- ✅ Cálculo de RTT em milissegundos
- ✅ Detecção de falhas (3 consecutivas)
- ✅ Fechamento automático de conexões inativas

### 4. Encerramento de Conexões
- ✅ BYE/BYE_OK
- ✅ Cleanup de threads e sockets
- ✅ Remoção do state

### 5. CLI Básico
- ✅ Setup e registro automáticos
- ✅ Comandos: peers, conn, unregister, help, quit
- ✅ Tratamento de Ctrl+C

### 6. Logging
- ✅ Sistema configurável (DEBUG/INFO/WARNING/ERROR)
- ✅ Output para console e arquivo
- ✅ Timestamps e módulo de origem

---

## ❌ Funcionalidades Pendentes

### 1. Mensageria (SEND/ACK)
**Arquivo a criar:** `message_router.py`

**Funcionalidades:**
- Enviar mensagem direta para um peer (`/msg <peer_id> <mensagem>`)
- Aguardar ACK (timeout de 5 segundos)
- Receber mensagens SEND de outros peers
- Enviar ACK automaticamente
- Exibir mensagens recebidas no terminal

**Protocolo SEND:**
```json
{
  "type": "SEND",
  "msg_id": "uuid",
  "src": "alice@CIC",
  "dst": "bob@CIC",
  "payload": "Olá!",
  "require_ack": true,
  "ttl": 1
}
```

**Protocolo ACK:**
```json
{
  "type": "ACK",
  "msg_id": "uuid",
  "timestamp": "2025-01-16T10:00:01Z",
  "ttl": 1
}
```

---

### 2. Mensageria Broadcast (PUB)
**Arquivo:** `message_router.py` (mesmo que SEND)

**Funcionalidades:**
- Broadcast global: `/pub * <mensagem>`
- Namespace-cast: `/pub #CIC <mensagem>`
- Enviar para todos os peers conectados (filtrar por namespace se necessário)
- Receber e exibir mensagens PUB

**Protocolo PUB:**
```json
{
  "type": "PUB",
  "msg_id": "uuid",
  "src": "alice@CIC",
  "dst": "*",
  "payload": "Mensagem para todos",
  "require_ack": false,
  "ttl": 1
}
```

---

### 3. Reconexão Automática
**Arquivo a criar:** `peer_table.py`

**Por que criar este módulo?**

Atualmente, o `state.py` guarda apenas peers **conectados no momento**. Quando uma conexão cai, o peer é removido e **esquecido**. O `peer_table.py` resolveria isso mantendo um **histórico de todos os peers já descobertos**, mesmo após desconectar.

**Estados dos peers:**
- `ACTIVE`: Peer conectado e funcionando
- `STALE`: Peer conhecido mas conexão caiu (candidato a reconexão)
- `UNKNOWN`: Peer descoberto mas nunca conectou com sucesso

**Cenário ATUAL (sem peer_table.py):**
1. Peer A conecta com Peer B
2. Conexão cai (B desligou ou rede falhou)
3. Peer A remove B do `state.py` e **esquece dele**
4. Peer B volta online
5. Peer A só redescobre B no **próximo discovery (até 60 segundos depois)**

**Cenário COM peer_table.py:**
1. Peer A conecta com Peer B
2. Conexão cai
3. Peer A **lembra** de B na tabela, marca como `STALE`
4. Thread de reconexão verifica a cada 10s (`reconnection.check_interval`)
5. Tenta reconectar automaticamente com backoff (2s, 4s, 8s, 16s, 32s)
6. Reconexão em **segundos** ao invés de até 60s
7. Após 5 falhas (`reconnection.max_attempts`), desiste e espera próximo discovery

**Funcionalidades a implementar:**
- Manter tabela de peers conhecidos com estados
- Marcar peers como STALE quando conexão cai
- Thread de reconexão periódica (a cada 10s)
- Tentativas automáticas de reconexão com backoff exponencial
- Limite configurável de tentativas (`max_reconnect_attempts`)
- Estatísticas: última vez visto, total de desconexões, taxa de sucesso

---

### 4. Comandos CLI Adicionais

**Pendentes:**
- ❌ `/msg <peer_id> <mensagem>` - Enviar mensagem direta
- ❌ `/pub * <mensagem>` - Broadcast global
- ❌ `/pub #<namespace> <mensagem>` - Namespace-cast
- ❌ `/rtt` - Exibir RTT médio por peer
- ❌ `/reconnect` - Forçar reconexão com todos os peers
- ❌ `/log <nivel>` - Ajustar nível de log em runtime

---

### 5. Integração de Mensageria no PeerConnection

**Alterações necessárias em `peer_connection.py`:**

No método `_processa_msg_recebida()`, adicionar:
```python
elif msg_type == "SEND":
    self._processa_send(msg)
elif msg_type == "ACK":
    self._processa_ack(msg)
elif msg_type == "PUB":
    self._processa_pub(msg)
```

Novos métodos a implementar:
- `envia_send(dst, payload, require_ack)`: Envia mensagem SEND
- `_processa_send(msg)`: Recebe SEND, exibe mensagem, envia ACK se necessário
- `_processa_ack(msg)`: Processa ACK recebido
- `envia_pub(dst, payload)`: Envia mensagem PUB
- `_processa_pub(msg)`: Recebe e exibe mensagem PUB

---

### 6. Exibição de RTT Médio

**Alterações em `keep_alive.py`:**
- Adicionar atributo `_rtts = []` para armazenar histórico
- No `processa_pong()`, adicionar RTT à lista
- Método `get_rtt_medio()` que retorna a média

**Alterações em `cli.py`:**
- Comando `cmd_rtt()` que itera sobre todas as conexões e exibe RTT médio de cada

---

## 🚀 Como Executar

### 1. Iniciar o programa
```bash
python main.py
```

### 2. Fornecer informações
- **Namespace:** Grupo lógico (ex: `CIC`, `UnB`)
- **Nome:** Seu identificador único (ex: `alice`)
- **Porta:** Porta para escutar conexões (ex: `5000`)
- **TTL:** Tempo de vida do registro em segundos (padrão: 7200 = 2 horas)

### 3. Comandos disponíveis
```
chatp2p> help                  # Mostra ajuda
chatp2p> peers                 # Lista todos os peers
chatp2p> peers CIC             # Lista peers do namespace CIC
chatp2p> conn                  # Mostra conexões ativas
chatp2p> unregister            # Remove registro do servidor
chatp2p> quit                  # Sai do programa
```

---

## ⚙️ Configurações

### Alterar nível de log

Edite `config.json`:
```json
"logging": {
  "level": "INFO",       // Mude de "DEBUG" para "INFO"
  "log_to_file": true,
  "file": "chatp2p.log"
}
```

**Níveis disponíveis:**
- `DEBUG`: Logs muito detalhados (enviando PING, recebendo PONG, etc.)
- `INFO`: Logs informativos (conexão estabelecida, peer registrado)
- `WARNING`: Avisos (falha ao conectar, tentativa de retry)
- `ERROR`: Erros (falha após todas as tentativas)

### Ajustar intervalos

```json
"rendezvous": {
  "discover_interval": 60    // Descoberta automática a cada X segundos
},
"keepalive": {
  "ping_interval": 30,       // PING a cada X segundos
  "max_ping_failures": 3     // Fechar após X falhas consecutivas
}
```

---

## 📊 Cenários de Teste

### Cenário 1: Descoberta Automática ✅
**Status:** Funcionando

1. Inicie peer A (namespace: CIC, porta: 5000)
2. Inicie peer B (namespace: CIC, porta: 5001)
3. Aguarde ~60 segundos
4. Peers se descobrem automaticamente e conectam

### Cenário 2: Keep-Alive ✅
**Status:** Funcionando

1. Conecte dois peers
2. Observe logs: PING a cada 30s, PONG respondido, RTT calculado
3. Logs exemplo:
   ```
   [KeepAlive] Pong recebido de bob@CIC. RTT: 4.72 ms
   ```

### Cenário 3: Comando /conn ✅
**Status:** Funcionando

```
chatp2p> conn
Conexões ativas:
Outbound connections:
 - vm_giga@CIC (45.171.101.167:8081)
Inbound connections:
 - Nenhuma conexão inbound ativa.
```

### Cenário 4: Mensageria ❌
**Status:** Não implementado

1. Peer A: `/msg bob@CIC Olá!`
2. Peer B deve receber e exibir: `[bob@CIC] Olá!`
3. Peer A recebe ACK em até 5s

### Cenário 5: Broadcast ❌
**Status:** Não implementado

1. Peer A: `/pub * Aviso geral`
2. Todos os peers conectados recebem a mensagem

### Cenário 6: Encerramento ✅
**Status:** Funcionando

1. Peer A: `quit`
2. Envia BYE para todos os peers conectados
3. Aguarda BYE_OK
4. Desregistra do servidor
5. Encerra

---

## 🎯 Próximos Passos

### Prioridade Alta
1. **Implementar message_router.py**
   - Funções: send_message(), send_pub(), process_send(), process_ack(), process_pub()
   - Integrar com PeerConnection

2. **Adicionar comandos CLI de mensageria**
   - `/msg <peer_id> <mensagem>`
   - `/pub * <mensagem>`
   - `/pub #<namespace> <mensagem>`

### Prioridade Média
3. **Implementar peer_table.py**
   - Tabela de peers conhecidos
   - Reconexão automática

4. **Comando `/rtt`**
   - Exibir RTT médio de cada conexão

### Prioridade Baixa
5. **Comando `/reconnect`**
   - Forçar reconexão manual

6. **Comando `/log <nivel>`**
   - Ajustar log em runtime

---

## 📝 Observações

- O sistema atual já funciona para **descoberta automática** e **manutenção de conexões**
- A base está sólida para adicionar mensageria
- Todos os módulos usam **threading** e são **thread-safe**
- Logs podem ser ajustados via config.json

---

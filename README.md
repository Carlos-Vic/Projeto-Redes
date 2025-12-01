# Documentação Técnica - Chat P2P

## Sumário
1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Módulos e Componentes](#módulos-e-componentes)
4. [Fluxo de Execução](#fluxo-de-execução)
5. [Protocolo de Comunicação](#protocolo-de-comunicação)
6. [Decisões de Design](#decisões-de-design)
7. [Configuração](#configuração)

---

## Visão Geral

Este é um **sistema de chat Peer-to-Peer (P2P)** desenvolvido em Python que permite comunicação direta entre usuários sem um servidor central de mensagens. O sistema utiliza um **Servidor Rendezvous** apenas para descoberta de peers, mas toda a comunicação de mensagens ocorre diretamente entre os peers conectados.

### Características Principais
- **Descoberta automática** de peers via Servidor Rendezvous
- **Conexões TCP persistentes** entre peers
- **Mensagens diretas** (unicast) via comando SEND
- **Broadcast** e **namespace-cast** via comando PUB
- **Keep-alive** automático com PING/PONG e medição de RTT
- **Re-registro automático** antes do TTL expirar
- **Reconexão inteligente** com backoff exponencial
- **Encerramento gracioso** com BYE/BYE_OK
- **Interface CLI** interativa
- **Sistema de logging** configurável

### Comandos CLI Disponíveis

| Comando | Descrição |
|---------|-----------|
| `/peers [* \| #namespace]` | Descobrir e listar peers registrados |
| `/msg <peer_id> <mensagem>` | Enviar mensagem direta (unicast) |
| `/pub * <mensagem>` | Broadcast para todos os peers conectados |
| `/pub #<namespace> <mensagem>` | Enviar para todos do namespace |
| `/conn` | Mostrar conexões ativas (inbound/outbound) |
| `/status` | Mostrar peers conectados e peers com falha |
| `/rtt` | Exibir RTT médio de cada conexão |
| `/reconnect` | Limpar falhas e forçar reconexão |
| `/log <LEVEL>` | Ajustar nível de log em runtime (DEBUG, INFO, etc) |
| `/help` | Exibir ajuda dos comandos |
| `/quit` | Encerrar aplicação graciosamente |

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│                     Servidor Rendezvous                      │
│          (pyp2p.mfcaetano.cc:8080)                          │
│   REGISTER │ DISCOVER │ UNREGISTER                          │
└──────────┬──────────────────────────────────────┬───────────┘
           │                                       │
           │ Descoberta                 Descoberta │
           ▼                                       ▼
    ┌─────────────┐                         ┌─────────────┐
    │   Peer A    │◄──────── TCP ──────────►│   Peer B    │
    │ carlos@CIC  │     HELLO/PING/SEND     │  alice@CIC  │
    │  Port 9076  │                         │  Port 7070  │
    └─────────────┘                         └─────────────┘
```

### Componentes Principais

1. **main.py** - Ponto de entrada da aplicação
2. **cli.py** - Interface de linha de comando
3. **state.py** - Gerenciamento de estado compartilhado
4. **rendezvous_connection.py** - Comunicação com servidor Rendezvous
5. **p2p_client.py** - Orquestração P2P (discover, reconexão)
6. **peer_server.py** - Servidor TCP para aceitar conexões
7. **peer_connection.py** - Gerenciamento de conexão TCP individual
8. **message_router.py** - Roteamento de mensagens SEND/PUB/ACK
9. **keep_alive.py** - Manutenção de conexões com PING/PONG
10. **logger.py** - Configuração de logging
11. **config.json** - Arquivo de configuração

---

## Módulos e Componentes

### 1. **main.py** - Inicializador

**Por que existe:**
- Ponto de entrada único da aplicação
- Valida existência do config.json antes de iniciar
- Configura sistema de logging
- Trata interrupções do usuário (Ctrl+C)

**O que faz:**
```python
def main():
    1. Verifica se config.json existe
    2. Configura sistema de logging
    3. Inicializa CLI
    4. Captura KeyboardInterrupt para saída limpa
```

**Decisão de design:** Separar a inicialização do CLI permite testes unitários e reutilização do código.

---

### 2. **logger.py** - Sistema de Logging

**Por que existe:**
- Centraliza configuração de logging
- Permite logs no console e arquivo simultaneamente
- Facilita debug com níveis ajustáveis (DEBUG, INFO, WARNING, ERROR)

**O que faz:**
```python
def configurar_logging(config_path):
    1. Lê configurações do config.json
    2. Define nível de log (DEBUG, INFO, etc)
    3. Cria handler para console (stdout)
    4. Cria handler para arquivo (se log_to_file = true)
    5. Define formato: "HH:MM:SS [module] LEVEL: message"
```

**Formato de saída:**
```
13:22:49 [rendezvous_connection] DEBUG: [Rendezvous] Conectando a pyp2p.mfcaetano.cc:8080
13:22:49 [peer_connection] INFO: [PeerConnection] Conectado com vm_giga@CIC
```

**Por que esse formato:**
- Timestamp facilita análise temporal de eventos
- Nome do módulo ajuda a rastrear origem do log
- Nível (DEBUG/INFO/WARNING/ERROR) permite filtrar logs importantes

---

### 3. **config.json** - Configuração

**Por que existe:**
- Centraliza parâmetros configuráveis sem alterar código
- Permite ajuste de timeouts, intervalos e limites
- Facilita testes com diferentes configurações

**Seções:**

#### **rendezvous**
```json
"rendezvous": {
    "host": "pyp2p.mfcaetano.cc",
    "port": 8080,
    "discover_interval": 60,         // Redescobre peers a cada 60s
    "register_retry_attempts": 3,    // Tenta 3x antes de desistir
    "register_backoff_base": 2,      // Backoff exponencial (2^n)
    "ttl_warning_treshold": 60       // Re-registra 60s antes de expirar
}
```

**Por que `discover_interval = 60`:**
- Muito curto (ex: 5s) sobrecarrega servidor
- Muito longo (ex: 5min) demora para descobrir novos peers
- 60s é equilíbrio entre descoberta rápida e carga moderada

**Por que `ttl_warning_treshold = 60`:**
- Margem de segurança para re-registro antes do TTL expirar
- Previne desregistro acidental por latência de rede

#### **network**
```json
"network": {
    "ack_timeout": 20,           // Espera 20s por ACK antes de retry
    "max_msg_size": 32768,       // 32 KiB (conforme especificação)
    "connection_timeout": 90     // Timeout TCP de 90s
}
```

**Por que `max_msg_size = 32768`:**
- Limite da especificação do protocolo
- Previne ataques de memória com mensagens gigantes

#### **peer_connection**
```json
"peer_connection": {
    "retry_attempts": 3,         // 3 tentativas de conexão
    "backoff_base": 2            // Aguarda 1s, 2s, 4s entre tentativas
}
```

#### **keepalive**
```json
"keepalive": {
    "ping_interval": 30,         // Envia PING a cada 30s
    "ping_timeout": 10,          // Aguarda PONG por 10s
    "max_ping_failures": 3       // Fecha conexão após 3 falhas
}
```

**Por que `max_ping_failures = 3`:**
- 1 falha pode ser perda de pacote temporária
- 3 falhas consecutivas (90s sem resposta) indica peer offline

---

### 4. **state.py** - Gerenciamento de Estado

**Por que existe:**
- **Thread-safety:** Múltiplas threads (discover, keep-alive, CLI) acessam dados compartilhados
- **Centralização:** Evita passar state por toda a aplicação
- **Encapsulamento:** Protege dados sensíveis com locks

**O que armazena:**
```python
class State:
    # Identificação do peer local
    name: str              # "carlos"
    namespace: str         # "CIC"
    port: int              # 9076
    ttl: int               # 121
    peer_id: str           # "carlos@CIC"
    public_ip: str         # "187.84.186.59"

    # Controle de TTL
    ttl_recebido: int      # TTL confirmado pelo servidor
    timestamp_registro: float  # Timestamp Unix do último REGISTER

    # Conexões ativas
    _conexoes: Dict[str, PeerConnection]  # {"alice@CIC": <PeerConnection>}

    # Router de mensagens
    _message_router: MessageRouter
```

**Métodos Thread-Safe (com RLock):**

```python
def adiciona_conexao(peer_id, conexao):
    with self._lock:
        self._conexoes[peer_id] = conexao
```

**Por que RLock (Reentrant Lock):**
- Thread pode adquirir o mesmo lock múltiplas vezes
- Evita deadlock quando método locked chama outro método locked
- Exemplo: `adiciona_conexao()` pode chamar `get_todas_conexoes()`

**Método crítico - get_config():**
```python
def get_config(self, *keys) -> Any:
    # Acesso hierárquico: get_config("rendezvous", "host")
    # Retorna None se chave não existir
```

**Por que esse design:**
- Previne KeyError se configuração estiver faltando
- Permite valores default no código: `timeout = config or 10`

---

### 5. **rendezvous_connection.py** - Comunicação com Servidor

**Por que existe:**
- Abstrai protocolo do Servidor Rendezvous
- Implementa retry com backoff exponencial
- Separa erros de rede (retry) de erros lógicos (sem retry)

**Hierarquia de Exceções:**
```
RendezvousError (base)
├─ RendezvousServerErro (erro lógico - sem retry)
│   Ex: "bad_namespace", "invalid_peer_id"
└─ RendezvousConnectionError (erro de rede - com retry)
    Ex: timeout, connection refused
```

**Por que 3 exceções diferentes:**
- `RendezvousServerErro`: Namespace inválido → NÃO adianta retry
- `RendezvousConnectionError`: Timeout de rede → DEVE fazer retry
- Separação permite tratamento inteligente de erros

#### **Função _envia_comando()**
```python
def _envia_comando(host, port, command, timeout=10):
    1. Serializa comando para JSON + '\n'
    2. Valida tamanho < 32 KiB
    3. Conecta via TCP
    4. Envia comando com sendall()
    5. Recebe resposta até encontrar '\n'
    6. Desserializa JSON
    7. Verifica status == ERROR
    8. Retorna resposta ou levanta exceção
```

**Por que `sendall()` em vez de `send()`:**
- `send()` pode enviar parcialmente
- `sendall()` garante envio completo ou exceção

**Por que aguardar até `\n`:**
- Protocolo define mensagens delimitadas por newline
- Permite enviar/receber múltiplas mensagens na mesma conexão

#### **Função register()**
```python
def register(state, retry=True):
    1. Monta comando REGISTER com name, namespace, port, ttl
    2. Loop de até 3 tentativas
    3. Em caso de RendezvousConnectionError:
       - Aplica backoff exponencial (1s, 2s, 4s)
       - Tenta novamente
    4. Em caso de RendezvousServerErro:
       - Levanta exceção imediatamente (sem retry)
    5. Se sucesso:
       - Salva ttl_recebido e timestamp_registro no state
       - Retorna resposta do servidor
```

**Por que salvar `ttl_recebido` e `timestamp_registro`:**
- Servidor pode ajustar o TTL solicitado
- Timestamp permite calcular quando re-registrar
- Usado pelo loop de re-registro automático

#### **Função discover()**
```python
def discover(state, namespace=None):
    1. Monta comando DISCOVER
    2. Opcional: adiciona filtro de namespace
    3. Envia comando
    4. Retorna lista de peers:
       [
         {"ip": "45.171.101.167", "port": 8081,
          "name": "vm_giga", "namespace": "CIC",
          "ttl": 7200, "expires_in": 5192}
       ]
```

**Por que `namespace` é opcional:**
- `discover()` sem namespace → retorna TODOS os peers
- `discover("CIC")` → retorna apenas peers do namespace CIC
- Usado pelo comando CLI `peers` vs `peers CIC`

#### **Função unregister()**
```python
def unregister(state):
    1. Monta comando UNREGISTER com namespace, name, port
    2. Envia comando
    3. Remove peer do servidor Rendezvous
```

**Por que enviar namespace, name, port (não peer_id):**
- Bug histórico: versão antiga enviava `peer_id`
- Servidor exige campos separados conforme especificação
- Corrigido em commit `e78e22d`

**Quando é chamado:**
- **NÃO existe comando manual `/unregister`** (foi removido)
- Chamado **automaticamente** no método `cli.limpar()` quando programa encerra
- Boa prática: avisa servidor que peer está saindo
- Se não chamar, servidor remove peer após TTL expirar naturalmente

---

### 6. **peer_server.py** - Servidor TCP Inbound

**Por que existe:**
- Aceita conexões **entrantes** de outros peers
- Funciona como "servidor" na arquitetura peer-to-peer
- Cada peer é simultaneamente cliente (outbound) e servidor (inbound)

**Arquitetura:**
```
PeerServer
  ├─ Thread principal: accept() em loop
  └─ Thread por conexão: handle_conexao()
```

**Fluxo de aceitação:**
```python
def _aceitar_conexoes(self):
    while rodando:
        1. socket.accept() → bloqueia até chegar conexão
        2. Cria thread para _handle_conexao()
        3. Thread processa handshake em paralelo
```

**Por que thread por conexão:**
- `accept()` retorna imediatamente após aceitar
- Handshake pode demorar (timeout de 90s)
- Thread dedicada evita bloquear próximas conexões

**Fluxo de handshake receptor:**
```python
def _handle_conexao(cliente_socket, endereco):
    1. Cria PeerConnection temporária (peer_id = "unknown")
    2. Aguarda mensagem HELLO
    3. Extrai peer_id do HELLO
    4. Verifica se já existe conexão com esse peer_id
       → Se sim: fecha conexão (evita duplicatas)
    5. Executa handshake_receptor()
       → Envia HELLO_OK
    6. Adiciona conexão no state
    7. Inicia threads de leitura/escrita
```

**Por que verificar conexão duplicada:**
- Peers podem tentar conectar simultaneamente (race condition)
- Exemplo: A→B e B→A ao mesmo tempo
- Mantém apenas uma conexão por peer_id
- Evita loops de mensagens

**Por que NÃO iniciar keep-alive:**
- Keep-alive só é iniciado pelo **iniciador** da conexão
- Receptor aguarda receber PINGs
- Previne duplicação de PINGs (ambos enviando)

**IMPORTANTE - Heterogeneidade em redes P2P:**
- Implementação acima é a correta **neste projeto**
- Em redes P2P heterogêneas, peers podem ter implementações diferentes
- Alguns peers podem enviar PING mesmo sendo receptores
- **Resultado:** Você pode receber PING mesmo em conexões outbound
- **Solução:** Sempre responder PONG quando receber PING (já implementado)
- Não é um bug - é característica de redes P2P com implementações variadas

**Decisão: listen(12)**
```python
self._server_socket.listen(12)
```
- Backlog de 12 conexões pendentes
- Suficiente para rajadas de conexões simultâneas
- Não exagera em memória

---

### 7. **peer_connection.py** - Conexão TCP Individual

**Por que existe:**
- Gerencia uma conexão TCP bidirecional com um peer
- Implementa protocolo de mensagens (HELLO, PING, SEND, PUB, BYE)
- Thread-safe com filas para envio assíncrono

**Arquitetura de Threads:**
```
PeerConnection
  ├─ Thread de Leitura: _loop_de_leitura()
  ├─ Thread de Escrita: _loop_de_escrita()
  └─ KeepAlive Thread (se foi_iniciado = True)
```

**Por que 2 threads separadas (leitura + escrita):**
- **Envio e recebimento simultâneos:** Pode receber PING enquanto envia SEND
- **Evita bloqueio:** `recv()` bloqueia, mas não impede envio
- **Fila thread-safe:** Escrita consome de `queue.Queue`

#### **Handshake Iniciador**
```python
def handshake_iniciador(self):
    1. Envia HELLO com peer_id, version, features
    2. Aguarda HELLO_OK
    3. Valida resposta
    4. Retorna True/False
```

**Mensagem HELLO:**
```json
{
  "type": "HELLO",
  "peer_id": "carlos@CIC",
  "version": "1.0",
  "features": ["ack", "metrics"],
  "ttl": 1
}
```

**Por que campo `features`:**
- Permite negociação de capacidades
- Exemplo: peer que não suporta ACK pode omitir "ack"
- Extensível para futuras funcionalidades

#### **Handshake Receptor**
```python
def handshake_receptor(self, msg_hello):
    1. Valida que type == "HELLO"
    2. Envia HELLO_OK
    3. Retorna True/False
```

#### **Mensagens PING/PONG**

**envia_ping():**
```python
def envia_ping(self):
    1. Gera UUID único para msg_id
    2. Cria mensagem PING com timestamp UTC
    3. Coloca na fila de envio
    4. Retorna msg_id (usado pelo keep_alive para calcular RTT)
```

**Por que UUID:**
- Identifica unicamente cada PING
- PONG referencia o msg_id do PING correspondente
- Permite calcular RTT: tempo_envio[msg_id] → tempo_recebimento

**_envia_pong():**
```python
def _envia_pong(self, msg_ping):
    1. Extrai msg_id do PING recebido
    2. Cria PONG com mesmo msg_id
    3. Coloca na fila de envio
```

**_processa_pong():**
```python
def _processa_pong(self, msg_pong):
    1. Delega para keep_alive.processa_pong()
    2. KeepAlive calcula RTT e remove ping pendente
```

#### **Mensagens BYE/BYE_OK**

**envia_bye():**
```python
def envia_bye(self, reason="Encerrando sessão"):
    1. Cria mensagem BYE com reason
    2. Coloca na fila de envio
    3. NÃO aguarda BYE_OK (envio assíncrono)
    4. BYE_OK será processado pela thread de leitura
```

**_envia_bye_ok():**
```python
def _envia_bye_ok(self, msg_bye):
    1. Loga razão do encerramento
    2. Envia BYE_OK
    3. Fecha conexão imediatamente
```

**_processa_bye_ok():**
```python
def _processa_bye_ok(self, msg_bye_ok):
    1. Loga que BYE_OK foi recebido
    2. Fecha conexão imediatamente
```

**Por que fechar após BYE_OK:**
- BYE é finalização graceful
- Ambos os lados sabem que conexão vai fechar
- Evita erros de "connection reset" nos logs

**Quando envia_bye() é chamado:**
- **Principal:** `p2p_client.stop()` quando programa encerra via `/quit`
- Envia BYE para **todos** os peers conectados
- Aguarda 2 segundos para dar tempo de BYE_OKs chegarem
- Depois fecha conexões normalmente

**Por que NÃO chamar envia_bye() em peer_connection.close():**
- Causaria loop infinito:
  ```
  Peer A: envia_bye()
    → Peer B: recebe BYE, chama close()
      → Peer B: close() chama envia_bye()
        → Peer A: recebe BYE, chama close()
          → Peer A: close() chama envia_bye()
            → LOOP INFINITO!
  ```
- Solução: BYE apenas enviado explicitamente no stop(), nunca no close()

#### **Loop de Leitura**
```python
def _loop_de_leitura(self):
    while conexão_ativa:
        1. _recebe_msg() → bloqueia até receber mensagem
        2. _processa_msg_recebida() → roteamento por tipo
        3. Em caso de erro: close() e break
```

**Por que try/except Exception:**
- `socket.timeout` → erro esperado, fecha conexão
- `socket.error` → rede caiu, fecha conexão
- Qualquer outra exceção → bug no código, loga e fecha

#### **Loop de Escrita**
```python
def _loop_de_escrita(self):
    while conexão_ativa:
        1. Aguarda mensagem na fila (timeout 1s)
        2. Se chegou mensagem: _envia_direct_msg()
        3. Se fila vazia: continua loop
        4. Em caso de erro: close() e break
```

**Por que timeout=1s na fila:**
- Permite verificar `_rodando` periodicamente
- Sem timeout, thread ficaria bloqueada indefinidamente
- Com timeout, pode detectar close() e encerrar

#### **_recebe_msg() - Parsing JSON**

**Versão corrigida (Commit 1d2f22d):**
```python
def _recebe_msg(self):
    buffer = b''
    while b'\n' not in buffer:
        chunk = sock.recv(4096)
        buffer += chunk
        if len(buffer) > 32768:
            raise PeerConnectionError("Tamanho excedido")

    # CORREÇÃO: Separa primeira linha do resto
    primeira_linha, _, resto = buffer.partition(b'\n')
    msg_linha = primeira_linha.decode('utf-8').strip()
    msg = json.loads(msg_linha)
    return msg
```

**Bug anterior:**
```python
# ERRADO: decodificava buffer inteiro
msg_linha = buffer.decode('utf-8').strip()
# Se buffer = '{"type":"PING"}\n{"type":"PONG"}\n'
# JSON parser falha com "Extra data: line 2 column 1"
```

**Por que `partition(b'\n')`:**
- Separa exatamente a primeira mensagem
- `resto` contém mensagens adicionais (ignoradas por ora)
- Futura melhoria: processar `resto` também

#### **Processamento de Mensagens**
```python
def _processa_msg_recebida(self, msg):
    msg_type = msg.get("type")

    if msg_type == "PING":
        self._envia_pong(msg)
    elif msg_type == "PONG":
        self._processa_pong(msg)
    elif msg_type == "BYE":
        self._envia_bye_ok(msg)
    elif msg_type == "BYE_OK":
        self._processa_bye_ok(msg)
    elif msg_type == "SEND":
        self._processa_send(msg)
    elif msg_type == "ACK":
        self._processa_ack(msg)
    elif msg_type == "PUB":
        self._processa_pub(msg)
    else:
        logger.warning(f"Tipo desconhecido: {msg}")
```

**Por que delegação:**
- SEND/ACK/PUB → delegados para MessageRouter
- PING/PONG → tratados localmente
- BYE → fecha conexão

#### **close() - Encerramento Limpo**
```python
def close(self):
    1. Verifica se já está fechado
    2. Para keep_alive (se existir)
    3. Marca _rodando.clear()
    4. Fecha socket
    5. Aguarda threads terminarem (timeout 5s)
    6. Remove conexão do state
```

**Por que timeout=5s:**
- Threads podem estar bloqueadas em recv()/send()
- Timeout evita travar close() indefinidamente
- Após 5s, threads são abandonadas (daemon=True garante cleanup)

---

### 8. **keep_alive.py** - Manutenção de Conexões

**Por que existe:**
- Detecta peers offline (não respondem PING)
- Mede RTT (Round Trip Time) para monitoramento
- Mantém conexão TCP ativa (alguns firewalls fecham conexões idle)

**Arquitetura:**
```
KeepAlive
  └─ Thread: _loop_ping()
       ├─ A cada 30s: envia_ping()
       └─ Se 3 PINGs sem resposta: close()
```

#### **Loop de PING**
```python
def _loop_ping(self):
    while rodando:
        1. msg_id = conexao.envia_ping()
        2. _pings_pendentes[msg_id] = time.time()
        3. sleep(30s)
        4. Se msg_id ainda em _pings_pendentes:
           → Incrementa _falhas
           → Se _falhas >= 3: close()
        5. Se PONG foi recebido:
           → _falhas = 0
```

**Por que armazenar timestamp:**
- Cálculo de RTT quando PONG chegar
- RTT = (tempo_recebimento - tempo_envio) * 1000 ms

#### **processa_pong()**
```python
def processa_pong(self, msg_pong):
    msg_id = msg_pong.get("msg_id")

    if msg_id in _pings_pendentes:
        tempo_envio = _pings_pendentes[msg_id]
        rtt = (time.time() - tempo_envio) * 1000  # ms
        _pings_pendentes.pop(msg_id)
        _falhas = 0

        # Armazena RTT (últimos 10)
        _rtts.append(rtt)
        if len(_rtts) > 10:
            _rtts.pop(0)
```

**Por que manter últimos 10 RTTs:**
- Permite calcular RTT médio
- Remove outliers (picos de latência)
- Memória limitada (10 floats ≈ 80 bytes)

#### **get_rtt_medio()**
```python
def get_rtt_medio(self):
    if not _rtts:
        return None
    return sum(_rtts) / len(_rtts)
```

**Usado por:** Comando CLI `/rtt`

**IMPORTANTE - Por que RTT pode mostrar N/A:**
- RTT só é calculado por quem **ENVIA** PING (iniciador da conexão)
- Se você só tem conexões **inbound** (outros conectaram com você):
  - Você recebe PINGs deles
  - Você responde PONGs
  - Mas **você não envia PINGs**
  - Portanto, RTT = N/A
- **Solução:** Ter pelo menos uma conexão outbound (você iniciou)
  - Seja o primeiro a se registrar no Rendezvous
  - Ou use `/reconnect` para forçar novas conexões

---

### 9. **message_router.py** - Roteamento de Mensagens

**Por que existe:**
- Abstrai lógica de SEND/ACK/PUB
- Gerencia timeouts e retries de ACK
- Permite callbacks para mensagens recebidas
- Separa protocolo de transporte da lógica de aplicação

#### **send() - Mensagem Unicast**
```python
def send(dst, payload, require_ack=True, timeout=20, retries=2):
    1. Gera msg_id único
    2. Cria mensagem SEND
    3. Registra pending ACK com Event()
    4. Loop de tentativas:
       a. Enfileira mensagem para envio
       b. Aguarda ACK com timeout
       c. Se ACK recebido: retorna (True, resposta)
       d. Se timeout: retry com backoff
    5. Se todas tentativas falharam: retorna (False, None)
```

**Estrutura de pending ACK:**
```python
_pending_acks = {
    "uuid-123": {
        "event": threading.Event(),  # Sinalizado quando ACK chegar
        "response": None             # Preenchido com mensagem ACK
    }
}
```

**Por que threading.Event():**
- `event.wait(timeout)` bloqueia thread até:
  - ACK chegar → `event.set()` é chamado
  - Timeout expirar → retorna False
- Evita polling ativo (loop while verificando flag)

**Fluxo de ACK:**
```
Thread A (send):                  Thread B (process_incoming):
1. Envia SEND
2. Aguarda event.wait(20s)        ...
                                  3. Recebe ACK
                                  4. Encontra pending[msg_id]
                                  5. pending["response"] = ack
                                  6. event.set() ← ACORDA Thread A
7. event.wait() retorna True
8. Retorna pending["response"]
```

#### **publish() - Broadcast e Namespace-cast**
```python
def publish(dst, payload, ttl=1):
    count = 0
    for peer_id, conn in get_todas_conexoes():
        if dst == "*":
            # Broadcast: envia para TODOS
            conn.enqueue_msg(PUB)
            count += 1
        elif dst.startswith("#"):
            # Namespace-cast: filtra por namespace
            namespace = dst.lstrip("#")
            if peer_id.endswith(f"@{namespace}"):
                conn.enqueue_msg(PUB)
                count += 1
    return count
```

**Por que retornar count:**
- Feedback para CLI quantos peers receberam
- Detecta namespace vazio
- Logs informativos

#### **process_incoming() - Dispatcher de Mensagens**
```python
def process_incoming(msg, peer_conn):
    tipo = msg.get("type")

    if tipo == "ACK":
        # Sinaliza thread esperando ACK
        msg_id = msg.get("msg_id")
        if msg_id in _pending_acks:
            _pending_acks[msg_id]["response"] = msg
            _pending_acks[msg_id]["event"].set()

    elif tipo == "SEND":
        # Notifica callbacks
        src = msg.get("src")
        payload = msg.get("payload")
        _notify_receive(src, payload, {"type": "SEND", "msg": msg})

        # Envia ACK se necessário
        if msg.get("require_ack"):
            ack = {"type": "ACK", "msg_id": msg["msg_id"], ...}
            peer_conn.enqueue_msg(ack)

    elif tipo == "PUB":
        # Notifica callbacks
        src = msg.get("src")
        payload = msg.get("payload")
        _notify_receive(src, payload, {"type": "PUB", "msg": msg})
```

**Por que callbacks:**
- Desacopla MessageRouter do CLI
- Permite múltiplos handlers (ex: salvar histórico, mostrar notificação)
- Padrão Observer

**Callback padrão:**
```python
router.register_receive_callback(
    lambda src, payload, meta: print(f"[{src}] {payload}")
)
```

---

### 10. **p2p_client.py** - Orquestração P2P

**Por que existe:**
- **Orquestrador central** de todas operações P2P
- Coordena PeerServer, discover, reconexão, re-registro
- Implementa lógica de backoff exponencial para peers offline

**Threads gerenciadas:**
```
P2PClient
  ├─ PeerServer thread (aceita conexões)
  ├─ _loop_discover() (descobre peers a cada 60s)
  └─ _loop_reregister() (re-registra antes do TTL expirar)
```

**Contagem total de threads:**
- **Thread principal:** 1 (CLI)
- **Threads de sistema:** 3 (PeerServer, discover, reregister)
- **Threads por peer conectado:**
  - 2 threads fixas (leitura + escrita)
  - 1 thread KeepAlive (se conexão foi iniciada por você)
  - 1 thread handshake temporária (durante aceitação de conexão inbound)

**Exemplo com 10 peers:**
- 5 outbound (você conectou): 5 × 3 threads = 15 threads
- 5 inbound (conectaram com você): 5 × 2 threads = 10 threads
- Sistema: 4 threads
- **Total: ~29 threads**

**Exemplo com 10 peers (todos outbound):**
- 10 outbound: 10 × 3 threads = 30 threads
- Sistema: 4 threads
- **Total: ~34 threads**

#### **start()**
```python
def start(self):
    1. Inicia PeerServer (listen na porta)
    2. Cria MessageRouter e registra no state
    3. Registra callback padrão (print mensagens)
    4. Inicia thread de discover
    5. Inicia thread de re-registro
```

**Por que essa ordem:**
- PeerServer primeiro → pode receber conexões imediatamente
- MessageRouter antes de discover → pronto para receber mensagens
- Threads por último → começam a trabalhar quando tudo está pronto

#### **stop() - Encerramento Gracioso**
```python
def stop(self):
    1. Para flag _rodando
    2. Itera por todas conexões ativas
    3. Envia BYE para cada peer (reason="Encerrando aplicação")
    4. Aguarda 2 segundos (timeout para BYE_OKs)
    5. Para PeerServer
    6. Aguarda threads discover/reregister terminarem (timeout 5s)
```

**Por que enviar BYE antes de fechar:**
- Conforme especificação do protocolo
- Permite peer remoto fechar graciosamente
- Evita logs de erro "connection reset" no peer remoto

**Por que aguardar 2 segundos:**
- Tempo para BYE ser enviado (thread de escrita)
- Tempo para BYE_OK retornar (thread de leitura)
- Em redes normais (RTT < 100ms), 2s é mais que suficiente
- Se peer remoto offline, timeout evita travar encerramento

**Limitações do timeout:**
- Se BYE_OK não chegar em 2s, conexão fecha abruptamente
- Peer remoto pode receber "connection reset"
- Trade-off entre encerramento gracioso e encerramento rápido

#### **_loop_discover() - Descoberta Automática**
```python
def _loop_discover(self):
    while rodando:
        1. discover(state) → lista de peers
        2. Para cada peer:
           a. Pula se for eu mesmo
           b. Pula se já conectado
           c. Verifica backoff (_deve_tentar_conectar)
           d. Cria thread para conectar em paralelo
        3. Aguarda threads terminarem (timeout 30s)
        4. sleep(60s)
```

**Versão Paralela (Commit 5f53fa8):**

**ANTES:**
```python
for peer in peers:
    conectar_com_peer(peer)  # Bloqueia ~63s se offline
# Total: N peers × 63s = muitos minutos
```

**DEPOIS:**
```python
threads = []
for peer in peers:
    t = threading.Thread(target=conectar_com_peer, args=(peer,))
    t.start()
    threads.append(t)

# Todas conexões tentadas simultaneamente
# Total: ~63s para N peers
```

**Por que limite de 10 threads:**
```python
if len(threads) >= 10:
    # Aguarda 5 primeiras threads terminarem
    for t in threads[:5]:
        t.join(timeout=1)
    # Remove threads finalizadas
    threads = [t for t in threads if t.is_alive()]
```

- Evita criar centenas de threads se houver muitos peers
- 10 threads simultâneas é equilíbrio entre paralelismo e recursos

#### **Backoff Exponencial para Peers Offline**
```python
_peers_com_falha = {
    "alice@CIC": {
        "timestamp": 1234567890.0,  # Última tentativa
        "tentativas": 3              # Contador de falhas
    }
}
```

**_deve_tentar_conectar():**
```python
def _deve_tentar_conectar(self, peer_id):
    if peer_id not in _peers_com_falha:
        return True  # Primeira tentativa

    info = _peers_com_falha[peer_id]
    tempo_desde_falha = time.time() - info['timestamp']
    tentativas = info['tentativas']

    # Backoff: 2^(n-1) minutos, máximo 30 min
    backoff_min = min(2 ** (tentativas - 1), 30)
    backoff_seg = backoff_min * 60

    return tempo_desde_falha >= backoff_seg
```

**Progressão do backoff:**
- Tentativa 1: 2^0 = 1 minuto
- Tentativa 2: 2^1 = 2 minutos
- Tentativa 3: 2^2 = 4 minutos
- Tentativa 4: 2^3 = 8 minutos
- Tentativa 5: 2^4 = 16 minutos
- Tentativa 6: 2^5 = 32 → limitado a 30 minutos

**Por que crescimento exponencial:**
- Peer temporariamente offline (1 min reiniciando) → tenta logo novamente
- Peer permanentemente offline (servidor desligado) → evita spam de conexões

#### **_registra_falha_conexao():**
```python
def _registra_falha_conexao(self, peer_id):
    with _lock_falhas:
        if peer_id in _peers_com_falha:
            _peers_com_falha[peer_id]['tentativas'] += 1
        else:
            _peers_com_falha[peer_id] = {
                'timestamp': time.time(),
                'tentativas': 1
            }
        _peers_com_falha[peer_id]['timestamp'] = time.time()
```

**Por que atualizar timestamp:**
- Reseta timer de backoff
- Próxima tentativa será daqui a `backoff_min` minutos

#### **_limpa_falha_conexao():**
```python
def _limpa_falha_conexao(self, peer_id):
    with _lock_falhas:
        if peer_id in _peers_com_falha:
            del _peers_com_falha[peer_id]
```

**Chamado quando:**
- Conexão é estabelecida com sucesso
- Remove peer da "lista negra"
- Próxima falha reinicia contador

#### **_loop_reregister() - Re-registro Automático**
```python
def _loop_reregister(self):
    while rodando:
        1. Verifica se ttl_recebido e timestamp_registro existem
        2. Calcula tempo restante de TTL
        3. threshold = min(60s, TTL * 10%)
        4. Se tempo_restante <= threshold:
           → register(state)
        5. sleep(30s)
```

**Por que threshold dinâmico:**
```python
threshold = min(60, ttl_recebido * 0.1)
```

- **TTL curto (121s):** threshold = min(60, 12.1) = 12.1s
  - Re-registra 12s antes de expirar
- **TTL longo (7200s):** threshold = min(60, 720) = 60s
  - Re-registra 60s antes de expirar
- **Vantagem:** TTL curto tem margem proporcionalmente maior

**Por que verificar a cada 30s:**
- Granularidade razoável (não precisa verificar a cada segundo)
- Garante re-registro a tempo mesmo com threshold de 12s
- Baixo overhead de CPU

#### **conectar_com_peer() - Estabelecimento de Conexão**
```python
def conectar_com_peer(self, peer_info):
    ip = peer_info.get("ip")
    porta = peer_info.get("port")
    peer_id = f"{peer_info['name']}@{peer_info['namespace']}"

    # Detecção de mesma rede
    if state.public_ip == ip:
        ip_conexao = "127.0.0.1"
    else:
        ip_conexao = ip

    # 3 tentativas com backoff 1s, 2s, 4s
    for tentativa in range(3):
        try:
            sock = socket.socket(AF_INET, SOCK_STREAM)
            sock.settimeout(90)
            sock.connect((ip_conexao, porta))

            conexao = PeerConnection(sock, peer_id, state, foi_iniciado=True)
            if not conexao.handshake_iniciador():
                sock.close()
                continue

            state.adiciona_conexao(peer_id, conexao)
            conexao.start()
            _limpa_falha_conexao(peer_id)
            return True

        except Exception as e:
            if tentativa < 2:
                sleep(2 ** tentativa)

    return False
```

**Detecção de Mesma Rede Local:**

O código detecta quando dois peers estão na mesma rede local e ajusta o IP de conexão:

```python
if state.public_ip == peer_info.get("ip"):
    ip_conexao = "127.0.0.1"  # Mesma rede → conecta via localhost
else:
    ip_conexao = ip          # Rede diferente → conecta via IP público
```

**Por que isso é necessário:**

1. **Servidor Rendezvous retorna IP público**
   - Peer A: IP público = 187.84.186.59, porta = 9087
   - Peer B: IP público = 187.84.186.59, porta = 9088
   - Ambos estão atrás do mesmo roteador NAT

2. **Problema do NAT loopback:**
   - Se Peer A tentar conectar em 187.84.186.59:9088
   - Pacote sai para internet com destino ao próprio IP público
   - Muitos roteadores NAT **não suportam loopback**
   - Conexão falha com timeout

3. **Solução implementada:**
   - Detecta que `public_ip` é igual ao IP do peer descoberto
   - Usa 127.0.0.1 (localhost) para conexão
   - Conexão fica na rede local, não sai para internet
   - **Vantagens:**
     - Funciona mesmo sem suporte a NAT loopback
     - Latência muito menor (RTT < 1ms)
     - Economia de banda de internet

4. **Casos de uso:**
   - **Testes locais:** Vários peers na mesma máquina
   - **LAN:** Vários peers na mesma rede local
   - **Mesma rede atrás de NAT:** Economiza banda e latência

**Por que timeout=90s:**
- Conexão através de firewall/NAT pode demorar
- Muito curto (10s) → falha em redes lentas
- Muito longo (5min) → trava descoberta

#### **limpar_todas_falhas() - Comando /reconnect**
```python
def limpar_todas_falhas(self):
    with _lock_falhas:
        count = len(_peers_com_falha)
        _peers_com_falha.clear()
        return count
```

**Usado por:** Comando CLI `/reconnect`

**Por que existir:**
- Permite forçar reconexão sem esperar backoff
- Útil após resolver problema de rede

#### **forcar_discover() - Comando /reconnect**
```python
def forcar_discover(self):
    peers = discover(state)
    count = 0

    for peer in peers:
        if não_conectado and não_sou_eu:
            thread = Thread(target=_tentar_conectar_thread, args=(peer,))
            thread.start()  # NÃO aguarda término
            count += 1

    return count
```

**Por que NÃO aguardar threads:**
- Versão anterior aguardava: `thread.join(timeout=30)`
- Bloqueava CLI por até 30s × N peers
- Versão corrigida: retorna imediatamente
- Conexões acontecem em background

---

### 11. **Race Conditions e Conexões Duplicadas**

**Por que existe este problema:**

Em redes P2P, dois peers podem tentar conectar um ao outro **simultaneamente**:

```
Tempo T0:
  Peer A descobre Peer B via DISCOVER
  Peer B descobre Peer A via DISCOVER (ao mesmo tempo)

Tempo T1:
  Peer A inicia conexão → B (thread outbound de A)
  Peer B inicia conexão → A (thread outbound de B)

Tempo T2:
  Peer A recebe conexão ← B (thread inbound de A)
  Peer B recebe conexão ← A (thread inbound de B)

Resultado: DUAS conexões TCP entre A e B!
  - Conexão 1: A→B (iniciada por A)
  - Conexão 2: B→A (iniciada por B)
```

**Problema se não tratar:**
- Mensagens duplicadas (enviadas em ambas conexões)
- Uso dobrado de recursos (threads, memória, banda)
- Loops de mensagens PUB

**Solução Implementada - peer_server.py linha 92:**

```python
def _handle_conexao(cliente_socket, endereco):
    # ... recebe HELLO ...
    peer_id_remoto = hello_msg.get("peer_id")

    # VERIFICAÇÃO CRÍTICA
    if self.state.verifica_conexao(peer_id_remoto):
        logger.info(f"[PeerServer] Conexão já existe com {peer_id_remoto}")
        cliente_socket.close()  # ← REJEITA conexão duplicada
        return

    # Continua handshake apenas se não existe conexão
```

**Como funciona:**

1. **Primeira conexão estabelecida:**
   - Peer A conecta com B primeiro
   - `state.adiciona_conexao("B", conn)` registra conexão
   - B aceita e registra `state.adiciona_conexao("A", conn)`

2. **Segunda conexão (duplicada) chega:**
   - B tenta conectar com A logo depois
   - A recebe conexão, lê HELLO
   - `verifica_conexao("B")` retorna **True** (já existe!)
   - A **rejeita** conexão e fecha socket
   - B recebe erro de conexão recusada

3. **Resultado:**
   - Apenas **uma** conexão TCP entre A e B
   - A primeira conexão estabelecida é mantida
   - Conexões duplicadas são descartadas

**Por que essa solução funciona:**
- Race condition é inevitável em sistemas distribuídos
- Não tentamos prevenir (impossível sem coordenação central)
- Aceitamos e **tratamos** a duplicação quando ocorre
- Simples e efetivo

**Caso especial - Sobreposição no state:**

Se ambas conexões forem aceitas quase simultaneamente antes da verificação:

```python
# state.py linha 72
def adiciona_conexao(self, peer_id, conexao):
    with self._lock:
        self._conexoes[peer_id] = conexao  # ← SOBRESCREVE!
```

- Segunda conexão sobrescreve a primeira
- Primeira conexão fica "órfã" (sem referência no state)
- Threads continuam rodando mas conexão não é mais acessível
- **Solução:** Uso de RLock garante atomicidade, minimiza janela de race condition
- Na prática, raramente ocorre devido à serialização do handshake

---

### 12. **cli.py** - Interface de Linha de Comando

**Por que existe:**
- Interface humana para controlar o sistema
- Abstrai complexidade dos comandos P2P
- Valida input do usuário

#### **cmd_setup() - Configuração Inicial**
```python
def cmd_setup(self):
    1. Cria State(config.json)
    2. Solicita namespace, name, porta
    3. Loop de validação de TTL:
       - TTL deve ser > 2× threshold
       - Evita loop infinito de re-registro
    4. state.set_peer_info(name, namespace, porta, ttl)
```

**Validação de TTL:**
```python
threshold = 60  # config.json
ttl_minimo = threshold * 2 = 120

if ttl <= 120:
    print("TTL muito baixo! Escolha > 120s")
```

**Por que 2× threshold:**
- Threshold = 60s (quando re-registra)
- Se TTL = 60s:
  - Registra com TTL=60s
  - 0.1s depois: threshold atingido (60s * 0.1 = 6s)
  - Re-registra com TTL=60s
  - Loop infinito!
- Solução: TTL > 120s garante tempo suficiente

#### **cmd_registrar() - Registro no Rendezvous**
```python
def cmd_registrar(self):
    try:
        resposta = register(state)
        registrado = True
        print(f"Status: {resposta.get('status')}")
    except RendezvousError as e:
        print(f"Falha: {e}")
```

#### **cmd_discover() - Descoberta de Peers**
```python
def cmd_discover(self, args):
    namespace = args[0] if args else None

    peers = discover(state, namespace)

    # Agrupa por namespace
    por_namespace = {}
    for peer in peers:
        ns = peer['namespace']
        if ns not in por_namespace:
            por_namespace[ns] = []
        por_namespace[ns].append(peer)

    # Exibe agrupado
    for ns, peers in sorted(por_namespace.items()):
        print(f"[{ns}]")
        for peer in peers:
            print(f"  - {peer['name']}@{ns} ({peer['ip']}:{peer['port']})")
```

**Por que agrupar por namespace:**
- Facilita visualização
- Peers do mesmo namespace geralmente relacionados

#### **cmd_msg() - Mensagem Direta**
```python
def cmd_msg(self, args):
    if len(args) < 2:
        print("Uso: msg <peer_id> <mensagem>")
        return

    peer_id = args[0]
    mensagem = " ".join(args[1:])

    router = state.get_message_router()
    sucesso, ack = router.send(peer_id, mensagem, require_ack=True)

    if sucesso:
        print(f"Mensagem enviada para {peer_id} (ACK recebido)")
    else:
        print(f"Falha ao enviar para {peer_id} (timeout)")
```

**Por que require_ack=True:**
- Confirma que mensagem foi entregue
- Detecta peer offline antes de timeout
- Feedback ao usuário

#### **cmd_pub() - Broadcast e Namespace-cast**
```python
def cmd_pub(self, args):
    if len(args) < 2:
        print("Uso: pub <destino> <mensagem>")
        return

    destino = args[0]  # * ou #namespace
    mensagem = " ".join(args[1:])

    # Valida formato
    if destino != "*" and not destino.startswith("#"):
        print("Destino deve ser '*' ou '#namespace'")
        return

    router = state.get_message_router()
    count = router.publish(destino, mensagem)

    if count == 0:
        print("Nenhum peer conectado")
    elif count == 1:
        print("Mensagem enviada para 1 peer")
    else:
        print(f"Mensagem enviada para {count} peers")
```

**Por que validar destino:**
- Evita typos (usuário digita `@CIC` em vez de `#CIC`)
- Feedback imediato de erro

#### **cmd_conn() - Conexões Ativas**
```python
def cmd_conn(self):
    conexoes = state.get_todas_conexoes()

    # Separa inbound e outbound
    inbound = []
    outbound = []

    for peer_id, conn in conexoes.items():
        if conn.foi_iniciado:
            outbound.append(peer_id)
        else:
            inbound.append(peer_id)

    print("Outbound connections:")
    for peer_id in outbound:
        conn = conexoes[peer_id]
        print(f"  - {peer_id} (Conectado a {conn.remoto_ip}:{conn.remoto_porta})")

    print("Inbound connections:")
    for peer_id in inbound:
        print(f"  - {peer_id}")
```

**Por que separar inbound/outbound:**
- Debugging: saber quem iniciou conexão
- Diagnóstico de NAT/firewall: apenas outbound funciona

#### **cmd_status() - Status de Peers**
```python
def cmd_status(self):
    conexoes = state.get_todas_conexoes()
    print(f"Peers conectados ({len(conexoes)}):")
    for peer_id in sorted(conexoes.keys()):
        print(f"  ✓ {peer_id}")

    with p2p_client._lock_falhas:
        falhas = p2p_client._peers_com_falha.copy()

    print(f"Peers com falha ({len(falhas)}):")
    for peer_id, info in sorted(falhas.items()):
        tentativas = info['tentativas']
        backoff_min = min(2 ** (tentativas - 1), 30)
        tempo_desde = int(time.time() - info['timestamp'])
        tempo_restante = max(0, (backoff_min * 60) - tempo_desde)

        mins = tempo_restante // 60
        secs = tempo_restante % 60

        print(f"  ✗ {peer_id} - Próxima tentativa em {mins}m{secs}s (tentativa #{tentativas})")
```

**Por que mostrar countdown:**
- Usuário sabe quando sistema tentará reconectar
- Transparência do backoff exponencial

#### **cmd_rtt() - Round Trip Time**
```python
def cmd_rtt(self):
    conexoes = state.get_todas_conexoes()

    print(f"{'Peer ID':<25} {'RTT Médio':<15} {'Amostras':<10}")
    print("-"*60)

    for peer_id, conn in sorted(conexoes.items()):
        if hasattr(conn, 'keep_alive') and conn.keep_alive:
            rtt_medio = conn.keep_alive.get_rtt_medio()
            quantidade = conn.keep_alive.get_quantidade_pings()

            if rtt_medio is not None:
                print(f"{peer_id:<25} {rtt_medio:>8.2f} ms     {quantidade:<10}")
            else:
                print(f"{peer_id:<25} {'N/A':<15} {0:<10}")
```

**Saída exemplo:**
```
Peer ID                   RTT Médio       Amostras
------------------------------------------------------------
vm_giga@CIC                    3.45 ms     10
```

**Por que mostrar amostras:**
- RTT com 1 amostra é menos confiável que 10 amostras
- Indica se conexão é recente (poucas amostras)

#### **cmd_reconnect() - Forçar Reconexão**
```python
def cmd_reconnect(self):
    # Limpa falhas
    count_falhas = p2p_client.limpar_todas_falhas()
    print(f"- {count_falhas} peer(s) removido(s) da lista de falhas")

    # Força discover
    count_tentativas = p2p_client.forcar_discover()
    print(f"- {count_tentativas} tentativa(s) de conexão iniciada(s)")
```

**Quando usar:**
- Após resolver problema de rede
- Para testar conectividade imediatamente

#### **cmd_log() - Ajustar Nível de Log**
```python
def cmd_log(self, args):
    nivel_str = args[0].upper()
    niveis = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    if nivel_str not in niveis:
        print("Nível inválido")
        return

    logging.getLogger().setLevel(niveis[nivel_str])
    print(f"Nível de log ajustado para: {nivel_str}")
```

**Por que runtime:**
- Debug sem reiniciar aplicação
- Pode ativar DEBUG durante problema, depois desativar

---

## Fluxo de Execução

### 1. Inicialização

```
main.py
  ↓
configurar_logging()
  ↓
CLI.run()
  ↓
cmd_setup()          → Solicita namespace, name, porta, TTL
  ↓
cmd_registrar()      → REGISTER no Rendezvous
  ↓
P2PClient.start()
  ├─ PeerServer.start()       → Escuta conexões (porta 9076)
  ├─ MessageRouter criado
  ├─ _loop_discover iniciado
  └─ _loop_reregister iniciado
```

### 2. Descoberta e Conexão

```
_loop_discover (a cada 60s)
  ↓
discover(state)      → Lista de peers do Rendezvous
  ↓
Para cada peer:
  ├─ Já conectado? → Pula
  ├─ Sou eu? → Pula
  ├─ Está em backoff? → Pula
  └─ Thread: conectar_com_peer()
       ↓
     socket.connect()
       ↓
     PeerConnection criada (foi_iniciado=True)
       ↓
     handshake_iniciador()
       ├─ Envia HELLO
       └─ Aguarda HELLO_OK
       ↓
     state.adiciona_conexao()
       ↓
     PeerConnection.start()
       ├─ Thread leitura
       ├─ Thread escrita
       └─ KeepAlive iniciado
```

### 3. Recepção de Conexão

```
PeerServer._aceitar_conexoes()
  ↓
socket.accept()      → Nova conexão entrante
  ↓
Thread: _handle_conexao()
  ↓
PeerConnection criada (foi_iniciado=False)
  ↓
_recebe_msg()        → Aguarda HELLO
  ↓
handshake_receptor()
  ├─ Valida HELLO
  └─ Envia HELLO_OK
  ↓
state.adiciona_conexao()
  ↓
PeerConnection.start()
  ├─ Thread leitura
  ├─ Thread escrita
  └─ KeepAlive NÃO iniciado (receptor espera PINGs)
```

### 4. Envio de Mensagem (SEND)

```
CLI: msg alice@CIC Olá!
  ↓
MessageRouter.send("alice@CIC", "Olá!", require_ack=True)
  ↓
Cria mensagem SEND com msg_id único
  ↓
Registra pending ACK com Event()
  ↓
conexao.enqueue_msg(SEND)      → Fila de envio
  ↓
Thread escrita: _envia_direct_msg()
  ↓
socket.sendall(JSON)           → Via TCP
  ↓
Aguarda: event.wait(timeout=20s)
  ↓
Peer destino:
  ├─ Recebe SEND
  ├─ Exibe mensagem
  └─ Envia ACK
  ↓
Thread leitura: _recebe_msg() → ACK
  ↓
MessageRouter.process_incoming(ACK)
  ├─ Encontra pending[msg_id]
  ├─ pending["response"] = ACK
  └─ event.set()               → Acorda thread aguardando
  ↓
send() retorna (True, ACK)
  ↓
CLI: "Mensagem enviada (ACK recebido)"
```

### 5. Broadcast (PUB)

```
CLI: pub * Olá a todos!
  ↓
MessageRouter.publish("*", "Olá a todos!")
  ↓
Para cada conexão:
  ├─ Cria mensagem PUB
  └─ conexao.enqueue_msg(PUB)
  ↓
Retorna count (quantidade enviada)
  ↓
CLI: "Mensagem enviada para 5 peers"
```

### 6. Keep-Alive (PING/PONG)

```
KeepAlive._loop_ping (a cada 30s)
  ↓
conexao.envia_ping()
  ├─ Gera msg_id
  ├─ _pings_pendentes[msg_id] = time.time()
  └─ Enfileira PING
  ↓
Thread escrita: envia PING via TCP
  ↓
sleep(30s)
  ↓
Verifica se msg_id ainda em _pings_pendentes:
  ├─ Se ainda pendente:
  │   ├─ _falhas += 1
  │   └─ Se _falhas >= 3: close()
  └─ Se foi removido (PONG recebido):
      └─ _falhas = 0

Peer destino:
  ├─ Recebe PING
  └─ _envia_pong(PING)
  ↓
Thread leitura: _recebe_msg() → PONG
  ↓
_processa_pong(PONG)
  ↓
KeepAlive.processa_pong(PONG)
  ├─ Calcula RTT
  ├─ Armazena em _rtts
  └─ Remove de _pings_pendentes
```

### 7. Re-registro Automático

```
_loop_reregister (a cada 30s)
  ↓
Calcula tempo_restante = ttl_recebido - (now - timestamp_registro)
  ↓
threshold = min(60s, ttl * 0.1)
  ↓
Se tempo_restante <= threshold:
  ↓
register(state)
  ├─ Envia REGISTER ao Rendezvous
  ├─ Recebe resposta com novo TTL
  ├─ Atualiza ttl_recebido
  └─ Atualiza timestamp_registro
  ↓
sleep(30s)
```

### 8. Encerramento Limpo (com BYE/BYE_OK)

```
CLI: quit
  ↓
cli.limpar()
  ↓
P2PClient.stop()
  ├─ Para flag _rodando
  ├─ Para cada conexão ativa:
  │   ├─ conexao.envia_bye("Encerrando aplicação")
  │   └─ BYE enfileirado para envio
  ├─ sleep(2s)  ← Aguarda BYEs serem enviados e BYE_OKs chegarem
  ├─ PeerServer.stop()
  └─ Para threads discover/reregister
  ↓
Peers remotos:
  ├─ Recebem BYE
  ├─ Enviam BYE_OK
  └─ Fecham conexão graciosamente
  ↓
unregister(state)      → Remove do Rendezvous (automático)
  ↓
sys.exit(0)
```

**Detalhes do timeout de 2 segundos:**

```
T=0s:   envia_bye() enfileira BYE para 5 peers
T=0.1s: Thread escrita envia primeiro BYE via TCP
T=0.2s: Thread escrita envia segundo BYE via TCP
        ...
T=0.5s: Todos BYEs enviados

T=0.6s: Peer remoto 1 recebe BYE, envia BYE_OK
T=0.7s: Thread leitura recebe BYE_OK, chama _processa_bye_ok(), fecha conexão
        ...
T=1.5s: Todos BYE_OKs recebidos, todas conexões fechadas

T=2.0s: Timeout expira
        - Conexões já fechadas graciosamente ✓
        - Ou conexões fechadas abruptamente se peer offline
```

**Por que 2 segundos é suficiente:**
- RTT típico: 50-100ms
- Processamento: ~10ms
- Margem de segurança: 20x o RTT esperado
- Trade-off: Encerramento rápido vs gracioso

---

## Estados de uma Conexão P2P

Uma conexão peer-to-peer passa pelos seguintes estados durante seu ciclo de vida:

```
┌─────────────────┐
│  DESCONECTADO   │
└────────┬────────┘
         │
         │ socket.connect() ou socket.accept()
         ▼
┌─────────────────────────┐
│ CONECTADO (TCP ativo)   │
│ Sem autenticação        │
└────────┬────────────────┘
         │
         │ Handshake: HELLO / HELLO_OK
         ▼
┌──────────────────────────┐
│    AUTENTICADO           │
│ peer_id conhecido        │
│ state.adiciona_conexao() │
└────────┬─────────────────┘
         │
         │ start() → Inicia threads
         ▼
┌──────────────────────────────────────┐
│          ATIVO                       │
│ ┌──────────────────────────────────┐ │
│ │ Thread Leitura: recv() em loop   │ │
│ │ Thread Escrita: send() da fila   │ │
│ │ KeepAlive: PING a cada 30s       │ │
│ │   (se foi_iniciado=True)         │ │
│ └──────────────────────────────────┘ │
│                                      │
│ Trocas de mensagens:                 │
│ • PING / PONG (keep-alive)          │
│ • SEND / ACK (mensagens)            │
│ • PUB (broadcast)                   │
└────────┬─────────────────────────────┘
         │
         │ Condições de saída:
         │ • 3 PINGs sem resposta
         │ • Erro de socket (timeout, reset)
         │ • BYE recebido
         │ • close() chamado explicitamente
         ▼
┌─────────────────────┐
│     FECHANDO        │
│ • BYE/BYE_OK        │
│ • close()           │
│ • join() threads    │
│ • remove_conexao()  │
└────────┬────────────┘
         │
         ▼
┌─────────────────┐
│    FECHADO      │
│ (cleanup done)  │
└─────────────────┘
```

**Transições especiais:**

- **ATIVO → FECHANDO (gracioso):** BYE/BYE_OK antes de fechar socket
- **ATIVO → FECHANDO (abrupto):** Socket fecha sem BYE (erro de rede, 3 PINGs falhados)
- **DESCONECTADO → DESCONECTADO:** Conexão duplicada rejeitada antes do handshake

---

## Protocolo de Comunicação

### Mensagens Peer-to-Peer

Todas mensagens são JSON UTF-8 delimitadas por `\n`:

#### **HELLO / HELLO_OK**
```json
// Iniciador → Receptor
{
  "type": "HELLO",
  "peer_id": "carlos@CIC",
  "version": "1.0",
  "features": ["ack", "metrics"],
  "ttl": 1
}

// Receptor → Iniciador
{
  "type": "HELLO_OK",
  "peer_id": "vm_giga@CIC",
  "version": "1.0",
  "features": ["ack", "metrics"],
  "ttl": 1
}
```

#### **PING / PONG**
```json
// Keep-alive request
{
  "type": "PING",
  "msg_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-30T13:22:49Z",
  "ttl": 1
}

// Keep-alive response
{
  "type": "PONG",
  "msg_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-30T13:22:49Z",
  "ttl": 1
}
```

#### **SEND / ACK**
```json
// Mensagem direta
{
  "type": "SEND",
  "msg_id": "123e4567-e89b-12d3-a456-426614174000",
  "src": "carlos@CIC",
  "dst": "alice@CIC",
  "payload": "Olá, Alice!",
  "require_ack": true,
  "ttl": 1
}

// Confirmação
{
  "type": "ACK",
  "msg_id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2025-01-30T13:22:50Z",
  "src": "alice@CIC",
  "dst": "carlos@CIC",
  "ttl": 1
}
```

#### **PUB**
```json
// Broadcast (*)
{
  "type": "PUB",
  "msg_id": "789e4567-e89b-12d3-a456-426614174000",
  "src": "carlos@CIC",
  "dst": "*",
  "payload": "Mensagem para todos!",
  "ttl": 1
}

// Namespace-cast (#CIC)
{
  "type": "PUB",
  "msg_id": "456e4567-e89b-12d3-a456-426614174000",
  "src": "carlos@CIC",
  "dst": "#CIC",
  "payload": "Mensagem para namespace CIC",
  "ttl": 1
}
```

#### **BYE / BYE_OK**
```json
// Encerramento graceful
{
  "type": "BYE",
  "msg_id": "999e4567-e89b-12d3-a456-426614174000",
  "src": "carlos@CIC",
  "dst": "alice@CIC",
  "reason": "Encerrando sessão",
  "ttl": 1
}

// Confirmação de encerramento
{
  "type": "BYE_OK",
  "msg_id": "999e4567-e89b-12d3-a456-426614174000",
  "src": "alice@CIC",
  "dst": "carlos@CIC",
  "ttl": 1
}
```

---

## Decisões de Design

### 1. **Por que Threading em vez de AsyncIO?**

**Decisão:** Usar `threading.Thread` para concorrência

**Alternativa:** `asyncio` com corrotinas

**Justificativa:**
- Operações de rede são **bloqueantes** (`socket.recv()`, `socket.send()`)
- `asyncio` requer sockets não-bloqueantes e event loop
- Threading é mais simples para I/O bloqueante
- Cada conexão tem 2 threads dedicadas (leitura + escrita)
- Python GIL não é problema (operações I/O liberam GIL)

**Desvantagem:**
- Threading consome mais memória que corrotinas
- 100 conexões = 200 threads + overhead
- `asyncio` seria mais eficiente para >1000 conexões

### 2. **Por que Fila para Envio de Mensagens?**

**Decisão:** `queue.Queue` entre lógica de aplicação e thread de escrita

**Alternativa:** Enviar diretamente via `socket.send()`

**Justificativa:**
```
Thread A (CLI):        Thread B (Keep-alive):
send("Olá")            send(PING)
   ↓                      ↓
   └─→ enqueue_msg() ←───┘
            ↓
       Queue (thread-safe)
            ↓
   Thread Escrita: _loop_de_escrita()
       ├─ msg1 = queue.get()
       ├─ socket.sendall(msg1)
       ├─ msg2 = queue.get()
       └─ socket.sendall(msg2)
```

**Vantagens:**
- Thread-safety automática (Queue é lock-free internamente)
- Serializa envios (evita mensagens intercaladas)
- Desacopla lógica de envio do I/O de rede

**Desvantagem:**
- Adiciona latência (mensagem enfileirada, depois enviada)
- Para este caso (chat), latência aceitável

### 3. **Por que Backoff Exponencial?**

**Decisão:** `2^(n-1)` minutos, máximo 30 min

**Alternativa:** Backoff linear (1min, 2min, 3min) ou fixo (sempre 1min)

**Justificativa:**
- **Peer temporariamente offline:** Tenta novamente rápido (1min, 2min)
- **Peer permanentemente offline:** Reduz tentativas (30min máximo)
- Previne sobrecarga de CPU e rede
- Algoritmo padrão em sistemas distribuídos (TCP, HTTP retries)

**Exemplo prático:**
```
Peer offline por 5 minutos (reiniciando):
  - 0min: Tenta (falha)
  - 1min: Tenta (falha)
  - 3min: Tenta (falha)
  - 7min: Tenta (SUCESSO!) ← Conectou
Total: 3 tentativas em 7 minutos

Peer offline permanente:
  - 0min: Tenta
  - 1min: Tenta
  - 3min: Tenta
  - 7min: Tenta
  - 15min: Tenta
  - 30min: Tenta
  - 60min: Tenta (ainda backoff de 30min)
Total: Poucas tentativas, baixo impacto
```

### 4. **Por que Re-registro Automático?**

**Decisão:** Loop verificando TTL a cada 30s, re-registra quando `tempo_restante <= threshold`

**Alternativa:** Usuário deve fazer re-registro manual

**Justificativa:**
- Servidor Rendezvous **remove peers com TTL expirado**
- Se peer não re-registra, outros peers não o descobrem
- Aplicação P2P deve ser **sempre alcançável**
- Re-registro automático garante disponibilidade contínua

**Por que threshold dinâmico:**
```python
threshold = min(60s, ttl * 0.1)
```
- TTL longo (7200s): threshold = 60s → margem de 1 minuto
- TTL curto (121s): threshold = 12.1s → margem proporcional
- Previne expiração por latência de rede ou carga do servidor

### 5. **Por que Conexões Paralelas no Discover?**

**Decisão (Commit 5f53fa8):** Criar thread por peer durante discover

**Alternativa:** Conectar sequencialmente (um por vez)

**Impacto:**
```
ANTES (sequencial):
  10 peers × 63s cada = 10 minutos para descobrir todos

DEPOIS (paralelo):
  10 peers × 63s em paralelo = 63s total
```

**Justificativa:**
- Discover a cada 60s não conseguia terminar antes do próximo discover
- Peers disponíveis esperavam minutos para conectar
- Paralelização reduz latência de descoberta de **10min → 1min**

**Por que limite de 10 threads:**
- 100 peers simultâneos = 100 threads = overhead excessivo
- Limite de 10 é equilíbrio razoável
- Pode ser ajustado conforme necessidade

### 6. **Por que Armazenar RTT?**

**Decisão:** KeepAlive mantém lista dos últimos 10 RTTs

**Alternativa:** Apenas logar RTT, não armazenar

**Justificativa:**
- Comando `/rtt` exige acesso aos valores
- RTT médio é mais confiável que RTT instantâneo
- 10 amostras capturam variações temporárias
- Memória negligível (10 floats × N conexões ≈ KB)

**Uso futuro:**
- Detecção de degradação de rede (RTT crescente)
- Seleção de peer com menor latência
- Métricas de qualidade de serviço

### 7. **Por que Delimitador `\n` em vez de Tamanho de Mensagem?**

**Decisão:** Mensagens delimitadas por `\n`

**Alternativa:** Protocolo length-prefixed (4 bytes com tamanho + payload)

**Justificativa:**
- **Simplicidade:** JSON já é texto, fácil de adicionar `\n`
- **Debugging:** Pode ler mensagens com `cat`, `nc`, `telnet`
- **Compatibilidade:** Padrão em muitos protocolos (HTTP, SMTP)

**Desvantagem:**
- Payload não pode conter `\n` literal
- Solução: JSON escapa `\n` como `\\n`

**Exemplo:**
```python
# Enviando
msg = {"type": "SEND", "payload": "Linha 1\nLinha 2"}
json_str = json.dumps(msg)  # {"type":"SEND","payload":"Linha 1\\nLinha 2"}
socket.send(json_str + "\n")

# Recebendo
buffer = socket.recv()  # b'{"type":"SEND","payload":"Linha 1\\nLinha 2"}\n'
linha, _, resto = buffer.partition(b'\n')
msg = json.loads(linha)  # Converte \\n de volta para \n
```

### 8. **Por que RLock em vez de Lock?**

**Decisão:** `threading.RLock()` no State

**Alternativa:** `threading.Lock()`

**Justificativa:**
```python
def adiciona_conexao(self, peer_id, conexao):
    with self._lock:
        self._conexoes[peer_id] = conexao
        logger.info(f"Conexão adicionada: {peer_id}")
        # Imagina que logger.info chama get_todas_conexoes()
        # Com Lock: DEADLOCK (mesmo thread tenta adquirir lock novamente)
        # Com RLock: OK (thread pode re-adquirir)
```

**RLock (Reentrant Lock):**
- Mesma thread pode adquirir múltiplas vezes
- Contador interno: `acquire() +1`, `release() -1`
- Só libera quando contador = 0

**Quando Lock é suficiente:**
- Métodos simples que não chamam outros métodos locked
- Neste projeto, RLock é mais seguro

### 9. **Por que KeepAlive Apenas no Iniciador da Conexão?**

**Decisão:** KeepAlive iniciado apenas quando `foi_iniciado=True`

**Alternativa:** Ambos os lados enviam PING

**Justificativa:**

**Conexão TCP é bidirecional:**
```
Peer A (iniciador)          Peer B (receptor)
      │                            │
      ├─────── HELLO ─────────────>│
      │<────── HELLO_OK ───────────┤
      │                            │
      ├─────── PING ──────────────>│  (A envia PING)
      │<────── PONG ───────────────┤  (B responde PONG)
      │                            │
      │  B NÃO envia PING          │
```

**Por que evitar PING duplicado:**

1. **Desperdício de banda:**
   - 1 PING a cada 30s × 2 direções = 2 PINGs/30s
   - 100 peers: 200 PINGs a cada 30s = ~7 PINGs/segundo
   - Desnecessário - uma direção já detecta falha

2. **Complexidade de sincronização:**
   - Se ambos enviam PING, ambos calculam RTT
   - Valores podem divergir (assimetria de rede)
   - Qual RTT usar? Média? Mínimo?

3. **Convenção TCP:**
   - Cliente (quem abre conexão) é responsável por keep-alive
   - Servidor (quem aceita conexão) apenas responde
   - Padrão em protocolos como HTTP WebSocket, SSH

**Vantagens de um único lado:**
- Simples: Apenas iniciador envia, receptor responde
- Eficiente: Metade dos PINGs em relação ao bidirecional
- Claro: Responsabilidade bem definida

**Caso especial - Redes P2P heterogêneas:**
- Nem todos peers seguem mesma implementação
- Alguns podem enviar PING mesmo sendo receptores
- **Solução:** Sempre responder PONG quando receber PING
- Implementado em `_processa_msg_recebida()` - responde PONG independente de quem iniciou

**Consequência - RTT só em outbound:**
- RTT apenas em conexões que você iniciou
- Conexões inbound não têm RTT (você não envia PING)
- Não é problema funcional, apenas métrica de monitoramento
- Ver seção Troubleshooting sobre "RTT mostra N/A"

---

## Configuração

### Ajuste de Parâmetros

#### **Para redes lentas:**
```json
{
  "network": {
    "connection_timeout": 180,  // Aumenta timeout de 90s → 180s
    "ack_timeout": 40           // Aumenta timeout ACK de 20s → 40s
  },
  "keepalive": {
    "ping_interval": 60,        // Reduz frequência de PING
    "max_ping_failures": 5      // Tolera mais falhas
  }
}
```

#### **Para muitos peers:**
```json
{
  "rendezvous": {
    "discover_interval": 120    // Descobre a cada 2 minutos
  }
}
```

#### **Para debugging:**
```json
{
  "logging": {
    "level": "DEBUG",           // Logs detalhados
    "log_to_file": true,
    "file": "chatp2p.log"
  }
}
```

### Variáveis de Ambiente

Não utiliza variáveis de ambiente. Toda configuração em `config.json`.

---

## Troubleshooting

### Problema: "Nenhum peer descoberto"
**Causa:** Servidor Rendezvous inacessível ou TTL expirado
**Solução:**
```bash
# Testar conectividade
telnet pyp2p.mfcaetano.cc 8080

# Verificar TTL no CLI
peers

# Re-registrar manualmente
unregister
# Depois registrar novamente via setup
```

### Problema: "Timeout ao enviar mensagem"
**Causa:** Peer destino offline ou NAT/firewall bloqueando
**Solução:**
```bash
# Verificar conexões ativas
conn

# Tentar reconectar
reconnect

# Verificar RTT (se muito alto, pode indicar problema de rede)
rtt
```

### Problema: "Conexão fecha após 90s"
**Causa:** 3 PINGs consecutivos sem resposta
**Solução:**
- Verificar logs: `grep "Ping não respondido" chatp2p.log`
- Aumentar `ping_interval` ou `max_ping_failures` no config.json
- Verificar firewall bloqueando pacotes TCP

### Problema: "Loop infinito de re-registro"
**Causa:** TTL menor que 2× threshold
**Solução:**
- Aumentar TTL no setup para > 120s
- Ou reduzir `ttl_warning_treshold` no config.json

### Problema: "RTT mostra N/A para todos os peers"
**Causa:** Você só tem conexões **inbound** (outros peers conectaram com você primeiro)

**Explicação:**
- RTT é calculado apenas por quem **envia PING** (iniciador da conexão)
- Se todos os peers conectaram **com você**:
  - Você recebe PINGs deles
  - Você responde PONGs corretamente
  - Mas **você não envia PINGs**
  - Logo, não há como calcular RTT

**Como verificar:**
```bash
# Verificar direção das conexões
conn

# Se todas conexões estiverem em "Inbound connections:", você não enviará PINGs
```

**Soluções:**

1. **Ser o primeiro a se registrar:**
   - Inicie seu peer antes dos outros
   - Seu discover encontrará os outros primeiro
   - Você iniciará conexões outbound
   - RTT será calculado

2. **Usar comando /reconnect:**
   ```bash
   reconnect
   ```
   - Limpa lista de falhas
   - Força discover imediato
   - Pode criar conexões outbound mesmo se já existem inbound

3. **Aguardar próximo discover:**
   - Loop de discover roda a cada 60 segundos
   - Se um peer desconectar e você reconectar, pode ser outbound

**Por que isso acontece:**
- Sistema evita conexões duplicadas (peer_server.py:92)
- Se peer A e peer B descobrem um ao outro simultaneamente:
  - Quem conectar primeiro mantém a conexão
  - Segundo peer detecta conexão existente e não tenta conectar
- Resultado: Apenas uma conexão (pode ser inbound para você)

**Isso é um problema?**
- **NÃO** - Conexão funciona normalmente
- Você recebe e envia mensagens corretamente
- Apenas não consegue **medir** RTT
- RTT é métrica de monitoramento, não afeta funcionalidade

---

## Conclusão

Este sistema implementa um **chat P2P completo** com:
- ✅ Descoberta automática de peers
- ✅ Conexões TCP persistentes e bidirecionais
- ✅ Mensagens unicast, broadcast e namespace-cast
- ✅ Keep-alive com medição de RTT
- ✅ Re-registro automático antes do TTL expirar
- ✅ Reconexão inteligente com backoff exponencial
- ✅ Interface CLI interativa e intuitiva

**Pontos fortes:**
- Arquitetura modular (fácil manutenção)
- Thread-safety (locks e filas)
- Logging completo (debugging facilitado)
- Configuração flexível (config.json)

**Limitações conhecidas:**
- Não implementa relay (peers atrás de NAT simétrico não conectam)
- Não persiste histórico de mensagens
- Não criptografa comunicação (texto plano via TCP)
- Escalabilidade limitada por threading (overhead com >100 peers)

**Possíveis melhorias futuras:**
- Implementar TLS para criptografia
- Adicionar suporte a relay peers
- Migrar para `asyncio` para maior escalabilidade
- Implementar persistência de mensagens (SQLite)
- Adicionar interface gráfica (GUI)

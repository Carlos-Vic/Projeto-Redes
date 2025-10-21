# PyP2P - Aplicação de Chat P2P

Este projeto implementa uma aplicação de chat peer-to-peer (P2P) em Python. Os peers se registram em um servidor central Rendezvous para descobrir uns aos outros e, em seguida, estabelecem conexões diretas para comunicação.

## Pré-requisitos

* Python 3 instalado.
* Nenhuma biblioteca externa é necessária (utiliza apenas bibliotecas padrão do Python).

## Como Executar

A execução envolve dois componentes principais: o Servidor Rendezvous (ponto de encontro) e o Cliente Chat P2P (a aplicação de chat em si).

### 1. Executando o Servidor Rendezvous (Localmente)

**Nota:** Este passo é necessário apenas enquanto o professor não disponibiliza o IP do servidor dele.

1.  Abra um terminal.
2.  Navegue até a pasta do código do servidor Rendezvous:
    ```bash
    cd .\pyp2p-rdv\src\rendezvous\
    ```
3.  Execute o script principal do servidor:
    ```bash
    python .\main.py
    ```
    O servidor começará a escutar por conexões (por padrão, na porta 8080). Mantenha este terminal aberto.

### 2. Executando o Cliente Chat P2P

1.  Abra um **novo** terminal (mantenha o terminal do servidor rodando, se aplicável).
2.  Navegue até a pasta do código do cliente Chat P2P:
    ```bash
    cd .\chatp2p\
    ```

3.  Execute o script principal do cliente:
    ```bash
    python .\main.py
    ```
4.  O programa solicitará que você digite as seguintes informações:
    * Seu nome de usuário (ex: `aluno`)
    * O namespace (ex: `CIC`)
    * A porta local que seu cliente usará para escutar conexões de outros peers (ex: `5000`)
    * O TTL (Time-To-Live) em segundos para o registro no servidor (opcional, pressione Enter para o padrão)

5.  Após o registro bem-sucedido, o cliente estará pronto para uso.

#### Comandos Disponíveis

* **/peers \[namespace]**: Lista os peers conhecidos.
    * Se nenhum `namespace` for fornecido, busca em todos os namespaces.
    * Se um `namespace` for fornecido (ex: `/peers CIC`), busca apenas naquele namespace.
* **/quit**: Envia uma requisição de `UNREGISTER` para o servidor Rendezvous e encerra a aplicação cliente.

### Executando Múltiplos Clientes

Para simular uma rede P2P, você pode executar múltiplos clientes:

* **Na mesma máquina:** Repita os passos da seção "Executando o Cliente Chat P2P" em terminais separados, mas certifique-se de fornecer um **nome** e uma **porta** diferentes para cada cliente quando solicitado.

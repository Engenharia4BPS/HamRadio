# GADX Vector – Arquitetura

## Visão Geral
Arquitetura modular baseada em **Vector Gateway + Vector Client**, com protocolo interno próprio e **Drivers** para integração com tecnologias externas.

## Componentes

### Vector Gateway
- Instalado em cada Site.
- Gerencia autenticação.
- Gerencia autorização e Sessions.
- Publica Resources disponíveis.
- Mantém e publica o estado autoritativo dos Resources.
- Gerencia Leases e políticas de acesso.
- Comunica-se com Hamlib e outros backends exclusivamente através de Drivers.

### Vector Client
- Executado no computador do operador.
- Interface Web para seleção de Site e Resources.
- Serviço local para funções dependentes do sistema operacional.
- Pode expor **múltiplas interfaces virtuais independentes** para compatibilidade com softwares legados.
- **CAT Adapter**: porta COM virtual com emulação CAT, inicialmente Kenwood TS-2000, para frequência, modo, VFO, split e PTT via comando CAT quando utilizado pelo logger.
- **Keying Adapter**: interface/porta virtual independente para observar e traduzir linhas seriais de controle, como RTS/DTR, usadas por softwares de contest para PTT e CW.
- Tradução das interfaces locais para operações normalizadas do domínio Vector.

A separação entre CAT e Keying é intencional. Softwares como N1MM e DXLog podem utilizar uma porta para controle CAT do rádio e outra porta para funções de chaveamento. O Vector Client não deve obrigar essas funções a compartilharem a mesma interface.

### Vector Protocol
Camada de comunicação entre Vector Client e Vector Gateway, independente do Hamlib, fabricante de rádio, protocolo CAT ou sistema operacional.

Na v1, utiliza WSS/TLS + JSON UTF-8 em produção, conforme `05-Protocolo.md` e ADR-011.

### Driver Interface
Contrato entre o núcleo do Vector Gateway e backends/equipamentos externos.

### Hamlib Driver
Driver oficial inicial para Resources do tipo Radio. Traduz operações e estados do domínio Vector para o backend Hamlib, preferencialmente via `rigctld`.

`rigctld` é backend do Hamlib Driver; não é um Driver separado do domínio Vector.

## Fluxo Lógico

```text
                         N1MM / DXLog
                              |
                 +------------+------------+
                 |                         |
                 v                         v
          COM Virtual CAT          COM Virtual Keying
          TS-2000 Adapter           RTS/DTR Adapter
                 |                         |
                 +------------+------------+
                              |
                              v
                         Vector Client
                              |
                              v
                        Vector Protocol
                              |
                              v
                        Vector Gateway
                              |
                              v
              Modelo de Domínio / Máquina de Estados
                              |
                              v
                       Driver Interface
                              |
                              v
                        Hamlib Driver
                              |
                              v
                       rigctld / Hamlib
                              |
                              v
                         Rádio físico
```

## CAT, PTT e CW

### CAT
A camada CAT é uma interface de compatibilidade de borda. Frequência, modo, VFO e split chegam ao Vector por essa interface e são convertidos para operações do domínio.

### PTT
O Vector deve admitir, no mínimo, duas origens locais de solicitação de PTT:

1. **PTT via CAT**, por exemplo comandos `TX`/`RX` da fachada TS-2000;
2. **PTT via linha serial**, por RTS ou DTR em uma interface de Keying dedicada.

As duas origens devem convergir para a mesma semântica de PTT do domínio Vector. A existência de múltiplas origens não elimina Lease, autorização, máquina de estados ou regras de fail-safe do Gateway.

### CW e operações sensíveis a timing
CW por chaveamento é sensível a latência e jitter. Portanto, a arquitetura **não deve presumir** que cada transição de ponto/traço será transportada como um comando JSON individual através da Internet.

O local definitivo de execução do keying CW — Client, Gateway ou keyer dedicado — permanece uma decisão a ser validada experimentalmente. A preferência arquitetural é manter o timing crítico próximo ao ponto de execução, evitando dependência direta da latência WAN.

Essa questão deve ser encerrada por SPIKE/medição antes de se tornar uma ADR normativa.

## Autoridade de Estado

O Vector Gateway é a autoridade sobre o estado publicado aos Clients.

> **O Client solicita. O Gateway decide. O Driver executa. O hardware confirma. O Gateway publica o estado autoritativo.**

Quando a confirmação física não for tecnicamente possível, essa limitação deve permanecer explícita; estado inferido não deve ser apresentado como estado observado confirmado.

## Multiestação
Cada Site possui seu próprio **Vector Gateway**. O operador escolhe no **Vector Client** qual Site deseja utilizar e, em seguida, seleciona um Resource disponível.

Sites iniciais previstos:
- Guatupê
- Purunã
- Casa 68
- Estação de Satélite

## Multiplataforma
As camadas dependentes do sistema operacional devem permanecer isoladas.

A interface Web, o Vector Protocol, os modelos de domínio e a comunicação com o Vector Gateway devem ser independentes do sistema operacional. A implementação específica de COM virtual, acesso a RTS/DTR ou equivalente fica encapsulada na camada nativa local do Vector Client.

Suporte oficial inicial: Windows 10 e Windows 11. Windows 7 é best effort. A arquitetura deve permitir Linux e macOS sem contaminar o núcleo com dependências específicas de sistema operacional.

## Segurança

- Secure by Default.
- TLS/WSS obrigatório em produção.
- Credenciais permanentes apenas durante autenticação.
- Tokens temporários para Sessions.
- Lease exclusivo para Resources que exigem controle exclusivo.
- PTT originado por CAT ou Keying continua sujeito às mesmas regras de autorização e fail-safe.
- Fail-safe tem prioridade sobre continuidade operacional.
- Backends locais, como `rigctld`, não devem ser expostos diretamente à Internet como interface pública do Vector.

## Princípios
- Separação entre interface, protocolo, regras de negócio e hardware.
- Hamlib tratado como backend do Hamlib Driver, não como protocolo interno da plataforma.
- Escalabilidade para múltiplos Sites, Resources e operadores.
- Baixo acoplamento.
- Inclusão de novos backends sem alterar contratos públicos quando possível.
- Compatibilidade CAT e Keying como camadas de borda, não como núcleo do sistema.
- Capabilities determinam funcionalidades disponíveis.
- Máquinas de estado são normativas.

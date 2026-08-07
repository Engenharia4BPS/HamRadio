# GADX Vector – Arquitetura

## Visão Geral
Arquitetura modular baseada em **Vector Gateway + Vector Client**, com protocolo interno próprio e adapters para integração com tecnologias externas.

## Componentes

### Vector Gateway
- Instalado em cada estação.
- Gerencia autenticação.
- Gerencia autorização e sessões.
- Publica recursos disponíveis.
- Mantém o estado dos recursos.
- Comunica-se com o Hamlib e outros backends futuros por adapters.

### Vector Client
- Executado no computador do operador.
- Interface Web para seleção de estação e recursos.
- Serviço local para funções dependentes do sistema operacional.
- Porta COM virtual quando necessária.
- Emulação CAT.
- Tradução entre CAT e Vector Protocol.

### Vector Protocol
Camada de comunicação entre Vector Client e Vector Gateway, independente do Hamlib, fabricante de rádio, protocolo CAT ou sistema operacional.

### Hamlib Adapter
Responsável por traduzir operações e estados do modelo do GADX Vector para a interface do `rigctld`.

## Fluxo Lógico

```text
N1MM / DXLog
     |
     v
COM Virtual / CAT
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
Hamlib Adapter
     |
     v
rigctld
     |
     v
Rádio físico
```

## Multiestação
Cada site possui seu próprio **Vector Gateway**. O operador escolhe no **Vector Client** qual site deseja utilizar e, em seguida, seleciona um recurso disponível.

Sites iniciais previstos:
- Guatupê
- Purunã
- Casa 68
- Estação de satélite

## Multiplataforma
As camadas dependentes do sistema operacional devem permanecer isoladas.

A interface Web, o Vector Protocol, os modelos de domínio e a comunicação com o Vector Gateway devem ser independentes do sistema operacional. A implementação específica de COM virtual ou equivalente fica encapsulada em adapters locais do Vector Client.

## Princípios
- Separação entre interface, protocolo, regras de negócio e hardware.
- Hamlib tratado como adapter, não como protocolo interno da plataforma.
- Escalabilidade para múltiplas estações, rádios e operadores.
- Baixo acoplamento.
- Possibilidade de inclusão de novos backends sem alterar clientes externos.
- Compatibilidade CAT como camada de integração, não como núcleo do sistema.

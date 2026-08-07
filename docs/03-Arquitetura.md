# GADX – Arquitetura

## Visão Geral
Arquitetura modular baseada em Gateway + Bridge, com protocolo interno próprio e adapters para integração com tecnologias externas.

## Componentes

### GADX Gateway
- Instalado em cada estação.
- Gerencia autenticação.
- Gerencia autorização e sessões.
- Publica recursos disponíveis.
- Mantém o estado dos recursos.
- Comunica-se com o Hamlib e outros backends futuros.

### GADX Bridge
- Executado no computador do operador.
- Interface Web para seleção de estação e recursos.
- Serviço local para funções dependentes do sistema operacional.
- Porta COM virtual.
- Emulação CAT.
- Tradução entre CAT e Protocolo GADX.

### Protocolo GADX
Camada de comunicação entre Bridge e Gateway, independente do Hamlib, fabricante de rádio, protocolo CAT ou sistema operacional.

### Adapter Hamlib
Responsável por traduzir operações e estados do modelo GADX para a interface do `rigctld`.

## Fluxo Lógico

```text
N1MM / DXLog
     |
     v
COM Virtual / CAT
     |
     v
GADX Bridge
     |
     v
Protocolo GADX
     |
     v
GADX Gateway
     |
     v
Adapter Hamlib
     |
     v
rigctld
     |
     v
Rádio físico
```

## Multiestação
Cada site possui seu próprio GADX Gateway. O operador escolhe no GADX Bridge qual site deseja utilizar e, em seguida, seleciona um recurso disponível.

Sites iniciais previstos:
- Guatupê
- Purunã
- Casa 68
- Estação de satélite

## Multiplataforma
As camadas dependentes do sistema operacional devem permanecer isoladas.

A interface Web, o Protocolo GADX, os modelos de domínio e a comunicação com o Gateway devem ser independentes do sistema operacional. A implementação específica de COM virtual ou equivalente fica encapsulada em adapters locais do Bridge.

## Princípios
- Separação entre interface, protocolo, regras de negócio e hardware.
- Hamlib tratado como adapter, não como protocolo interno da plataforma.
- Escalabilidade para múltiplas estações, rádios e operadores.
- Baixo acoplamento.
- Possibilidade de inclusão de novos backends sem alterar clientes externos.
- Compatibilidade CAT como camada de integração, não como núcleo do sistema.

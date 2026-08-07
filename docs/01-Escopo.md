# GADX Vector – Escopo do Projeto

## Visão Geral
O **GADX Vector** é a plataforma de automação e operação remota de estações de rádio amador do **Grupo Araucária de DX (GADX)**. A plataforma permite que o operador utilize seu próprio computador, software de log e ambiente de operação enquanto controla rádios e outros recursos instalados em estações remotas.

## Objetivos
- Operação remota multiestação.
- Compatibilidade com N1MM e DXLog.
- Integração com Hamlib (`rigctld`).
- Interface Web moderna.
- Arquitetura modular e escalável.
- Abstração de equipamentos e backends para evolução futura.

## Conceito Central
O operador não controla um rádio remoto diretamente. Ele conecta-se ao GADX Vector, escolhe um site e solicita acesso a um recurso disponibilizado pela estação.

## Componentes
### Vector Gateway
Servidor instalado em cada estação (Purunã, Guatupê, Casa 68 etc.).
- Autenticação.
- Aprovação de sessões.
- Gerenciamento dos recursos.
- Integração com Hamlib e outros adapters futuros.

### Vector Client
Executado no computador do operador.
- Interface Web.
- Serviço local.
- Emulação CAT.
- Porta COM virtual quando necessária.
- Integração transparente com N1MM, DXLog e aplicações compatíveis.

### Vector Protocol
Protocolo interno entre Vector Client e Vector Gateway, independente do Hamlib, de fabricantes e de protocolos CAT específicos.

## Fluxo
1. Login.
2. Seleção da estação.
3. Seleção do recurso.
4. Solicitação de acesso.
5. Aprovação.
6. Disponibilização da interface local necessária.
7. Operação pelo N1MM/DXLog ou outro software compatível.

## Roadmap Inicial
1. Emulação CAT.
2. Integração Hamlib.
3. Vector Gateway.
4. Interface Web do Vector Client.
5. Multiestação e sessões.
6. Recursos avançados.

## Filosofia
O GADX Vector é uma plataforma completa de automação e gerenciamento de estações remotas, e não apenas um adaptador para Hamlib.

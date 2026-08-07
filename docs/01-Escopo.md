# GADX – Escopo do Projeto

## Visão Geral
O GADX (Grupo Araucária DX) é uma plataforma para gerenciamento e operação remota de estações de rádio amador, permitindo que o operador utilize seu próprio computador, software de log e ambiente de operação enquanto controla rádios instalados em estações remotas.

## Objetivos
- Operação remota multiestação.
- Compatibilidade com N1MM e DXLog.
- Integração com Hamlib (rigctld).
- Interface web moderna.
- Arquitetura modular e escalável.

## Conceito Central
O operador nunca controla um rádio diretamente. Ele conecta-se a uma estação, que disponibiliza recursos como rádios, rotores e amplificadores.

## Componentes
### GADX Gateway
Servidor instalado em cada estação (Purunã, Guatupê, Casa68, etc.).
- Autenticação.
- Aprovação de sessões.
- Gerenciamento dos recursos.
- Integração com Hamlib.

### GADX Bridge
Executado no computador do operador.
- Interface Web.
- Serviço local.
- Emulação CAT.
- Porta COM virtual.

## Fluxo
1. Login.
2. Seleção da estação.
3. Seleção do recurso.
4. Solicitação de acesso.
5. Aprovação.
6. Criação da COM virtual.
7. Operação pelo N1MM/DXLog.

## Roadmap Inicial
1. Emulação CAT.
2. Integração Hamlib.
3. Gateway.
4. Interface Web.
5. Recursos avançados.

## Filosofia
O GADX é uma plataforma completa de gerenciamento de estações remotas, e não apenas um adaptador para Hamlib.

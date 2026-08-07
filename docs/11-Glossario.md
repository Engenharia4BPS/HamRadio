# GADX Vector – Glossário

## GADX
**Grupo Araucária de DX.** Organização responsável pelo desenvolvimento e manutenção do GADX Vector.

## GADX Vector
Plataforma de automação e operação remota de estações de rádio amador desenvolvida pelo Grupo Araucária de DX.

## Vector Gateway
Serviço instalado em cada site e responsável por recursos, sessões, autorização, políticas e integração com equipamentos locais.

## Vector Client
Componente executado no computador do operador. Fornece interface Web, integração local, COM virtual e emulação CAT para softwares como N1MM e DXLog.

## Vector Protocol
Protocolo interno de comunicação entre Vector Client e Vector Gateway, independente do Hamlib e de protocolos CAT específicos.

## Resource
Abstração de qualquer equipamento ou serviço controlável dentro do GADX Vector.

## Driver
Camada que traduz operações do modelo de domínio para uma tecnologia ou protocolo específico e converte estados externos de volta para o domínio Vector.

## Capability
Capacidade anunciada por um Resource, indicando uma função suportada, como Frequency, PTT, Azimuth ou Power On.

## Session
Conexão autenticada entre um operador e um Vector Gateway.

## Ownership
Vínculo temporário que determina qual Session possui autorização para controlar determinado Resource.

## Hamlib
Biblioteca open source usada para controle de rádios e outros equipamentos de radioamador.

## rigctld
Daemon TCP da Hamlib utilizado para expor funções de controle de rádio pela rede.

## CAT
Computer Aided Transceiver. Família de protocolos usada para controle de rádios por software.

## COM virtual
Porta serial virtual apresentada ao software do operador como se fosse uma interface serial física.

## N1MM
Software de contest utilizado como um dos clientes prioritários de compatibilidade do GADX Vector.

## DXLog
Software de contest utilizado como um dos clientes prioritários de compatibilidade do GADX Vector.

## Site
Local físico que hospeda Resources controláveis pelo Vector, como Purunã, Guatupê ou Casa 68.

# GADX – Premissas

## Objetivo
Registrar as decisões e premissas técnicas, arquiteturais e funcionais do projeto.

## Premissas
- Backend oficial inicial: Hamlib, preferencialmente via `rigctld`.
- Compatibilidade inicial obrigatória com N1MM e DXLog.
- Interface de usuário baseada em Web.
- Serviço local apenas para funções que exigem integração nativa, como COM virtual e emulação CAT.
- Gateway responsável por autenticação, autorização e sessões.
- Protocolo GADX independente do Hamlib.
- Multiestação considerada desde o início.
- Arquitetura modular.
- Recursos da estação tratados por abstração: rádio, rotor, amplificador e outros equipamentos futuros.
- Emulação CAT inicial baseada em um único modelo de rádio, a ser validado antes da implementação definitiva.

## Hamlib
A versão de referência inicial será a linha **Hamlib 4.7.x**, devendo a versão exata utilizada em produção ser registrada e validada durante o desenvolvimento.

## Compatibilidade de Sistemas Operacionais
- A arquitetura será concebida como multiplataforma.
- Suporte oficial inicial: Windows 10 e Windows 11.
- Windows 7: melhor esforço, sem compromisso de compatibilidade integral.
- Linux e macOS serão suportáveis pela arquitetura através da separação das camadas dependentes do sistema operacional.
- Interface web, protocolo GADX e regras de negócio não devem depender do sistema operacional.

## Transparência para o operador
O GADX não pretende substituir N1MM, DXLog ou demais aplicações do radioamador. O operador continuará utilizando seus programas, logs e configurações locais normalmente.

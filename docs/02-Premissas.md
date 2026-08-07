# GADX Vector – Premissas

## Objetivo
Registrar as decisões e premissas técnicas, arquiteturais e funcionais do **GADX Vector**, plataforma do **Grupo Araucária de DX (GADX)**.

## Premissas
- Backend oficial inicial: Hamlib, preferencialmente via `rigctld`.
- Compatibilidade inicial obrigatória com N1MM e DXLog.
- Interface de usuário baseada em Web.
- Serviço local apenas para funções que exigem integração nativa, como COM virtual e emulação CAT.
- **Vector Gateway** responsável por autenticação, autorização e sessões.
- **Vector Protocol** independente do Hamlib.
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
- Interface Web, Vector Protocol e regras de negócio não devem depender do sistema operacional.

## Transparência para o operador
O GADX Vector não pretende substituir N1MM, DXLog ou demais aplicações do radioamador. O operador continuará utilizando seus programas, logs e configurações locais normalmente.

## Identidade do produto
- **GADX** = Grupo Araucária de DX, organização responsável pelo projeto.
- **GADX Vector** = nome oficial da plataforma.
- **Vector Gateway**, **Vector Client**, **Vector Protocol**, **Vector API** e futuros componentes utilizarão a marca Vector.

# GADX Vector — Development Setup (Windows)

Este diretório contém a primeira versão do setup automatizado do SPIKE TS-2000.

O objetivo é permitir que o ambiente de testes seja preparado em uma máquina Windows sem configurar manualmente cada porta COM e sem iniciar a bridge em um terminal a cada boot.

## O que o setup faz

`setup.ps1`:

1. exige execução como Administrador;
2. localiza o `setupc.exe` do com0com já instalado;
3. consulta as portas COM ocupadas/reservadas usando `busynames COM?*`;
4. escolhe duas portas livres entre **COM10 e COM30** para apresentar ao logger;
5. escolhe duas portas altas entre **COM100 e COM199** para uso interno do Vector;
6. cria dois pares com0com:
   - CAT do logger <-> CAT interno do Vector;
   - CW/PTT do logger <-> keying interno do Vector;
7. gera `C:\ProgramData\GADXVector\bridge.ini`;
8. gera `C:\ProgramData\GADXVector\logger.ini` com as portas que devem ser configuradas no logger;
9. copia o runtime da bridge para `C:\Program Files\GADX Vector`;
10. instala `pyserial` e `pywin32` globalmente;
11. registra o serviço `GADXVectorBridge`;
12. configura o serviço como **Automatic (Delayed Start)**;
13. configura recuperação automática após falha;
14. inicia o serviço.

## Por que as portas do logger ficam abaixo da COM30

Alguns softwares legados de rádio/contest possuem limitações ou comportamento inconsistente com números altos de portas COM.

Por isso o instalador aplica a regra:

```text
Portas expostas ao logger: COM10..COM30
Portas internas do Vector: COM100..COM199
```

Exemplo:

```text
N1MM CAT      COM19  <-> COM100  Vector CAT
N1MM CW/PTT   COM28  <-> COM101  Vector Keying
```

O logger nunca precisa conhecer COM100/COM101.

## Pré-requisitos da versão de desenvolvimento

- Windows 10/11;
- Python instalado globalmente e acessível como `python`;
- com0com Signed já instalado;
- `setupc.exe` disponível na instalação do com0com;
- Hamlib/`rigctld` já configurado para o rádio físico.

> Esta primeira versão **não redistribui o instalador do com0com**. A licença/origem da build assinada ainda deve ser validada antes de incluirmos binários de terceiros no instalador final.

## Executar

Abra PowerShell como Administrador e, dentro de `spikes\cat-ts2000\installer`:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

Para o IC-7760 usado no SPIKE, os defaults são:

```text
radio keying port = COM22
radio keying baud = 9600
rigctld            = 127.0.0.1:4532
```

Podem ser alterados:

```powershell
.\setup.ps1 -RadioKeyingPort COM25 -RadioKeyingBaud 9600 -RigHost 127.0.0.1 -RigPort 4532
```

Se o `setupc.exe` não for encontrado automaticamente:

```powershell
.\setup.ps1 -SetupcPath "C:\caminho\para\setupc.exe"
```

Para criar apenas as portas e o INI, sem instalar serviço:

```powershell
.\setup.ps1 -SkipService
```

## Arquivos instalados

```text
C:\Program Files\GADX Vector\
  rigctld_bridge.py
  ts2000.py
  service\vector_bridge_service.py

C:\ProgramData\GADXVector\
  bridge.ini
  logger.ini
  logs\bridge-service.log
```

## Serviço

Nome interno:

```text
GADXVectorBridge
```

Nome exibido:

```text
GADX Vector Bridge
```

O serviço é configurado como `Automatic (Delayed Start)` e o Windows tenta reiniciá-lo após falhas.

Para verificar:

```powershell
Get-Service GADXVectorBridge
```

Para reiniciar depois de alterar `bridge.ini`:

```powershell
.\restart-service.ps1
```

Para remover apenas o serviço:

```powershell
.\uninstall-service.ps1
```

As portas virtuais e configurações são preservadas deliberadamente nessa remoção.

## Segurança de PTT/CW

O wrapper do serviço possui uma segunda camada de fail-safe independente da bridge.

Ao parar o serviço ele tenta:

```text
radio_keying_port RTS = OFF
radio_keying_port DTR = OFF
rigctld set_ptt 0
```

Essa proteção existe porque o processo filho pode ser encerrado pelo Service Control Manager antes de conseguir executar seu próprio `finally`.

## Estado desta versão

Esta é uma **versão de desenvolvimento**, não um instalador de produção.

Antes de virar um `.exe` final ainda devemos:

- validar o fluxo em uma máquina de teste;
- tornar upgrades idempotentes sem criar novos pares COM a cada execução;
- guardar os IDs CNCA/CNCB criados para permitir remoção limpa;
- detectar automaticamente a porta física de keying do rádio quando possível;
- melhorar a recuperação se o rádio/USB estiver desligado no boot;
- confirmar a política de redistribuição do com0com Signed;
- empacotar o runtime Python ou gerar executáveis independentes;
- embrulhar o fluxo validado em Inno Setup.

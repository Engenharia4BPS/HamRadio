# GADX Vector Setup — produção v0.1-dev

Primeira geração do instalador autossuficiente do GADX Vector para Windows.

## Objetivos

O instalador deve deixar a estação pronta para uso sem exigir Python global nem criação manual de portas virtuais.

Fluxo esperado:

```text
GADX-Vector-Setup.exe
    |
    +-- instala em C:\Ham\GADX-Vector
    +-- instala Python privado em runtime\
    +-- instala pyserial + pywin32 nesse runtime
    +-- usa a distribuição signed do com0com empacotada
    +-- procura duas COM livres <= COM30 para o logger
    +-- procura duas COM internas entre COM100 e COM199
    +-- cria 2 pares com0com
    +-- gera config\bridge.ini e config\logger.ini
    +-- instala GADXVectorBridge como Windows Service
    +-- Automatic (Delayed Start)
    +-- Recovery: restart on failure
    +-- inicia o serviço
```

## Layout instalado

```text
C:\Ham\GADX-Vector\
├── app\
│   ├── rigctld_bridge.py
│   └── ts2000.py
├── runtime\
│   └── Python privado do Vector
├── service\
│   └── vector_bridge_service.py
├── config\
│   ├── bridge.ini
│   ├── logger.ini
│   └── install-summary.txt
├── logs\
│   └── bridge-service.log[.1..5]
├── installer\
└── thirdparty\
```

## Logs

Padrão inicial:

```ini
log_level = INFO
log_max_mb = 5
log_backups = 5
```

O wrapper do serviço gira `bridge-service.log` quando o arquivo atinge o limite. Com 5 backups de 5 MB, o histórico do serviço fica limitado a aproximadamente 30 MB.

## Portas COM

Regra de compatibilidade:

- portas apresentadas ao N1MM, LogHX e outros loggers: COM10..COM30;
- portas internas do Vector: COM100..COM199.

Exemplo possível:

```text
Logger CAT:    COM28  <-> COM101 Vector
Logger CW/PTT: COM30  <-> COM102 Vector
```

A escolha é automática e respeita as reservas reportadas pelo com0com/ComDB.

## Configuração do rádio

O wizard pergunta:

- porta COM usada para CW keying físico;
- baud dessa porta;
- host do rigctld;
- porta TCP do rigctld.

Para a bancada IC-7760 validada no SPIKE, os valores usados foram COM22, 9600, 127.0.0.1 e 4532.

## Dependências de build

- Inno Setup 6;
- instalador oficial Python Windows x64 homologado;
- distribuição completa signed do com0com.

Os dois últimos são payloads externos e não ficam no GitHub.

Consulte `payload/README.md` e rode `build-installer.ps1`.

## Estado atual

Esta versão é deliberadamente `0.1.0-dev`. O fluxo da bridge, CAT, PTT, CW e Windows Service já foi validado em bancada; o novo empacotamento `C:\Ham\GADX-Vector` ainda precisa ser compilado e testado em uma máquina de desenvolvimento antes de ser considerado release.

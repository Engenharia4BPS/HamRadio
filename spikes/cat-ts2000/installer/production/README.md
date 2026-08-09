# GADX Vector Setup — produção v0.1-dev (legado do SPIKE)

Esta pasta contém a **primeira geração** do instalador autossuficiente do GADX Vector para Windows. Ela foi importante para validar Python privado, com0com, serviço Windows, reparo/reinstalação e rotação de logs, mas ainda gera a configuração **single-client** (`bridge.ini`).

> **Importante:** o estado arquitetural mais novo do SPIKE é a bridge multi-client descrita em `../../README.md` e `../../bridge_multi.ini`. Portanto, este instalador não deve ser tratado como especificação final do produto.

## O que esta geração validou

```text
GADX-Vector-Setup.exe
    |
    +-- instala em C:\Ham\GADX-Vector
    +-- instala Python 3.10 privado em runtime\
    +-- instala pyserial + pywin32 nesse runtime
    +-- instala/reutiliza a distribuicao signed do com0com
    +-- cria 1 par CAT + 1 par keying
    +-- gera config\bridge.ini e config\logger.ini
    +-- instala/repara GADXVectorBridge como Windows Service
    +-- Automatic (Delayed Start)
    +-- Recovery: restart on failure
    +-- inicia e valida o servico
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
│   └── bridge-service.log[.1..N]
├── installer\
└── thirdparty\
```

## Logs

Padrão validado:

```ini
log_level = INFO
log_max_mb = 5
log_backups = 5
```

A rotação é responsabilidade do **wrapper de serviço**. Com arquivo principal de 5 MB e 5 backups, o uso máximo aproximado é 30 MB (arquivo atual + cinco históricos).

## Portas COM — política aprendida no SPIKE

Os testes mostraram que softwares de rádio mais antigos podem ter limitações ou comportamento ruim com números altos de COM. Por isso, a política desejada para a próxima geração do instalador é:

```text
lado apresentado aos aplicativos: começar em COM15 e avançar
lado interno do Vector:          começar em COM101 e avançar
```

Exemplo de alocação futura:

```text
COM15 <-> COM101   CAT #1
COM16 <-> COM102   Keying #1
COM17 <-> COM103   CAT #2
COM18 <-> COM104   Keying #2
...
```

A COM15 é **preferência de início**, não reserva rígida. O instalador deve consultar ComDB/com0com, nunca tomar uma porta ocupada e avançar até encontrar uma livre.

O script v0.1 existente ainda procura portas do lado do software no intervalo COM10..COM30. Isso é comportamento legado e deverá ser alterado quando o instalador for migrado para a arquitetura multi-client.

## Configuração do rádio / keying

O keying físico é propriedade da instalação, não do modelo CAT emulado. O SPIKE comprovou que interfaces diferentes podem usar combinações diferentes de RTS/DTR para PTT e CW.

A configuração multi-client atual representa isso explicitamente em `[radio_keying]`:

```ini
[radio_keying]
port = COM4
baud = 19200
ptt_line = RTS
cw_line = DTR
```

Portanto, a próxima geração do instalador deve perguntar/descobrir também `ptt_line` e `cw_line`, e não assumir uma combinação fixa.

## Python privado

A decisão validada é transportar um runtime Python privado sob `C:\Ham\GADX-Vector\runtime`, em vez de depender do Python global do Windows. Isso facilita reprodução e gestão de versões.

A geração atual foi construída em torno de Python 3.10.11, `pyserial==3.5` e `pywin32==312`.

## com0com

A primeira geração suporta localizar `setupc.exe` em:

```text
C:\Ham\com0com\setupc.exe
%ProgramFiles%\com0com\setupc.exe
%ProgramFiles(x86)%\com0com\setupc.exe
```

Também suporta instalação a partir do payload assinado empacotado e reutilização de pares existentes durante reparo.

## Serviço Windows

O serviço validado é:

```text
GADXVectorBridge
Automatic (Delayed Start)
Recovery: restart on failure
```

O wrapper inicia uma bridge Python como processo filho e redireciona stdout/stderr para `logs\bridge-service.log`.

### Limitação atual

`service/vector_bridge_service.py` ainda espera:

```text
app\rigctld_bridge.py
config\bridge.ini
```

e o `force_safe_state()` ainda lê chaves do formato single-client dentro de `[bridge]`.

Antes de promover a multi-bridge a versão oficial, o wrapper deve entender nativamente:

```text
[cat]
[keying]
[radio_keying]
[rig]
[bridge]
```

## Dependências de build

- Inno Setup 6;
- instalador oficial Python Windows x64 homologado;
- distribuição completa signed do com0com.

Os payloads externos não precisam ficar versionados no GitHub. Consulte `payload/README.md` e o script de build desta pasta.

## Estado

**LEGADO VALIDADO / NÃO É A ESPECIFICAÇÃO FINAL.**

Esta geração provou a mecânica de instalação. A arquitetura funcional mais atual é multi-client e deve ser a base do próximo instalador. Até essa migração, mudanças no instalador v0.1 devem evitar criar novas dependências conceituais sobre o formato single-client.

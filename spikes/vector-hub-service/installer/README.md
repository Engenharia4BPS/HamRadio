# GADX Vector — Phase D Installer

Esta pasta concentra a nova geracao do instalador do GADX Vector Hub.

## D1 — Detector de instalacao

Arquivo:

```text
installer/detect-installation.ps1
```

O detector e deliberadamente **read-only**. Ele nao cria/remove arquivos, servicos ou portas COM.

Ele classifica a maquina em um dos estados:

```text
CLEAN    nenhum artefato conhecido do GADX Vector
CURRENT  estrutura atual reconhecida
LEGACY   estrutura antiga bridge/multi-bridge reconhecida
BROKEN   instalacao parcial, misturada ou inconsistente
```

E sugere um modo:

```text
INSTALL
MIGRATE
MIGRATE_REPAIR
REPAIR
NONE
```

## O que ele verifica

- `C:\Ham\GADX-Vector`;
- arquivos atuais:
  - `app\vector_hub.py`;
  - `service\vector_service.py`;
  - `config\vector.ini`;
  - `tools\port_manager.py`;
- artefatos legados:
  - `app\rigctld_bridge.py`;
  - `app\rigctld_bridge_multi.py`;
  - `service\vector_bridge_service.py`;
  - `config\bridge.ini`;
  - `config\bridge_multi.ini`;
  - `config\logger.ini`;
- servicos `GADXVectorHub` e `GADXVectorBridge`;
- runtime privado `runtime\python.exe`;
- imports obrigatorios:
  - `tkinter`;
  - `serial` / pyserial;
  - `win32serviceutil` / pywin32;
- instalacao do com0com / `setupc.exe`.

## Executar

No PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Ham\GADX-Vector\installer\detect-installation.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector"
```

Para saida estruturada em JSON:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Ham\GADX-Vector\installer\detect-installation.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector" `
  -AsJson
```

A saida JSON sera usada pelo orquestrador grafico/installer nas proximas etapas da Fase D.

## Regras importantes

- uma instalacao LEGACY deve preservar os pares com0com existentes sempre que possivel;
- arquivos INI antigos devem ser copiados para `config\legacy` antes da migracao;
- valores antigos devem ser convertidos para `config\vector.ini`, nao apenas renomeados;
- `GADXVectorBridge` so deve ser removido depois que `GADXVectorHub` estiver pronto;
- runtime existente sem Tcl/Tk deve ser reparado com `Include_tcltk=1`;
- alteracoes em pares com0com deixam reboot pendente;
- ao fim de Install/Migrate/Repair, o Port Manager deve abrir para revisao do operador;
- apos a configuracao de portas, o fluxo deve solicitar reinicio do Windows.

## Proximas etapas

- D2: backup e migracao de configuracao legada;
- D3: instalacao/reparo idempotente do runtime e dependencias;
- D4: instalacao/reparo do servico `GADXVectorHub`;
- D5: integracao com Port Manager + reboot pendente;
- D6: post-install check apos reboot;
- D7: uninstall seguro.

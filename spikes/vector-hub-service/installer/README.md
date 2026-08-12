# GADX Vector — Phase D Installer

Esta pasta concentra a nova geracao do instalador do GADX Vector Hub.

## Status

```text
D1 — Detector/classificador ............ VALIDADO
D2 — Backup + migracao de configuracao . VALIDADO
D3 — Payload + troca transacional svc .. VALIDADO
D4 — Orquestrador unico ................ EM TESTE
D5 — Port Manager + reboot ............. PROXIMO
D6 — Post-install check ................ PLANEJADO
D7 — Uninstall seguro .................. PLANEJADO
```

A validacao foi feita em dois cenarios reais: uma instalacao atual que precisava de repair e uma instalacao legada com `GADXVectorBridge`, `bridge_multi.ini` e pares com0com existentes.

## D1 — Detector de instalacao

Arquivo:

```text
installer/detect-installation.ps1
```

O detector e read-only. Ele classifica a maquina em:

```text
CLEAN
CURRENT
LEGACY
BROKEN
```

e recomenda:

```text
INSTALL
MIGRATE
MIGRATE_REPAIR
REPAIR
NONE
```

O `tools\port_manager.py` e tratado como artefato auxiliar: sua presenca isolada nao transforma uma instalacao antiga em instalacao atual.

## D2 — Migracao de configuracao

Arquivos:

```text
installer/plan-migration.ps1
installer/apply-migration.ps1
```

`plan-migration.ps1` e somente preview. `apply-migration.ps1 -Apply`:

- prioriza `bridge_multi.ini` quando presente;
- le CAT, keying, radio keying, rigctld e permissoes;
- cria backup timestampado em `config\legacy\YYYYMMDD-HHMMSS`;
- gera `config\vector.ini` no formato atual;
- preserva os INIs antigos;
- nao altera pares com0com;
- nao altera servicos.

Clientes legados sem nome amigavel sao migrados como `Cliente 1`, `Cliente 2`, etc. O operador pode renomea-los posteriormente no Port Manager.

## D3 — Payload e troca transacional do servico

Arquivo:

```text
installer/migrate-service.ps1
```

Payload obrigatorio:

```text
installer\payload\app\vector_hub.py
installer\payload\app\ts2000.py
installer\payload\service\vector_service.py
```

Fluxo transacional:

```text
validar payload/runtime/vector.ini
        ↓
deploy da geracao atual
        ↓
parar GADXVectorBridge temporariamente
        ↓
instalar GADXVectorHub
        ↓
configurar delayed-auto + recovery
        ↓
iniciar e validar estabilidade
        ↓
SUCESSO: remover GADXVectorBridge
FALHA:   remover tentativa nova e religar GADXVectorBridge
```

O `vector.ini` e os pares com0com nao sao alterados nesta etapa.

## Runtime privado

Arquivo:

```text
installer/ensure-runtime.ps1
```

O runtime atual exige:

- Python privado em `runtime\python.exe`;
- Tcl/Tk (`tkinter`);
- `pyserial==3.5`;
- `pywin32==312`;
- `pythonservice.exe`/post-install do pywin32.

O script tambem verifica com0com. Se runtime/com0com precisarem ser instalados, ele procura os instaladores em:

```text
<InstallRoot>\thirdparty\
<installer>\thirdparty\
```

Arquivos esperados quando necessarios:

```text
python-installer.exe
com0com-installer.exe
```

A instalacao/reparacao do Python usa explicitamente `Include_tcltk=1`.

## D4 — Orquestrador unico

Ponto de entrada:

```text
installer/setup-vector.ps1
```

O operador nao precisa decidir qual script interno executar. O D4 chama o detector e escolhe automaticamente o plano.

Preview:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Ham\GADX-Vector\installer\setup-vector.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector"
```

Execucao:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File "C:\Ham\GADX-Vector\installer\setup-vector.ps1" `
  -InstallRoot "C:\Ham\GADX-Vector" `
  -Apply
```

### LEGACY / MIGRATE

```text
ensure runtime/com0com
        ↓
backup + gerar vector.ini
        ↓
deploy payload atual
        ↓
troca transacional do servico
```

### CURRENT / REPAIR

```text
ensure/repair runtime/com0com
        ↓
preservar vector.ini
        ↓
deploy/reinstalar GADXVectorHub
        ↓
limpar servico legado residual se houver
```

### CURRENT / NONE

Nenhuma alteracao e feita.

### CLEAN / INSTALL

Na D4 o ambiente base (runtime/com0com) pode ser preparado. A configuracao inicial dos clientes, criacao/revisao de pares e fluxo de reboot sera fechada na D5 com o Port Manager.

## Regras de seguranca

- preservar pares com0com existentes durante migration/repair;
- nunca sobrescrever uma COM ocupada silenciosamente;
- fazer backup antes de converter configuracao antiga;
- nunca remover `GADXVectorBridge` antes de `GADXVectorHub` estar validado;
- reparar runtime existente sem Tcl/Tk em vez de considera-lo saudavel;
- manter `vector.ini` atual em Repair;
- tratar alteracao/criacao de portas virtuais como reboot pendente;
- ao final do fluxo completo, abrir Port Manager para revisao do operador;
- apos configuracao de portas, solicitar reinicio do Windows.

## Proxima etapa — D5

D5 deve fechar a experiencia de instalacao:

```text
D4 concluido
   ↓
abrir Port Manager
   ↓
operador revisa/renomeia clientes e COMs
   ↓
aplicar configuracao
   ↓
marcar reboot pendente quando houver mudanca de portas
   ↓
[Reiniciar agora] [Reiniciar depois]
```

Depois do reboot, D6 fara a validacao final de runtime, com0com, `vector.ini`, portas e `GADXVectorHub`.

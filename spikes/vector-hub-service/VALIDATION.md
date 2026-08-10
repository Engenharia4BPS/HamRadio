# Vector Hub SPIKE 02 — Validation log

## Phase A — Runtime

**Status: VALIDATED**

Data: 2026-08-10

A Fase A foi validada manualmente em uma estacao que ainda utilizava a primeira geracao single-client, anterior ao instalador e anterior ao ambiente multi-client mais recente.

Configuracao da estacao:

```text
CAT Vector:       COM18 @ 19200
Keying Vector:    COM32 @ 19200
CW fisico:        COM22 / RTS @ 9600
PTT fisico:       rigctld
rigctld:          127.0.0.1:4532
```

O `vector_hub.py` foi executado manualmente com `config/vector.ini` e manteve o comportamento funcional esperado.

### Aprendizado adicional

A migracao mostrou que `radio_keying.ptt_line` precisa aceitar `RIGCTLD` alem de `RTS`, `DTR` e `NONE`, porque existem instalacoes validas em que CW usa uma linha serial fisica enquanto PTT permanece controlado pelo Hamlib.

Isso reforca o principio de que PTT e CW sao canais de saida configuraveis independentemente.

## Phase B — Windows Service

**Status: IMPLEMENTED / AWAITING BENCH VALIDATION**

Artefatos:

```text
service/vector_service.py
service/install-service.ps1
service/uninstall-service.ps1
```

Nome do novo servico:

```text
GADXVectorHub
```

O servico legado `GADXVectorBridge` pode permanecer instalado para rollback, mas deve ficar parado durante os testes do Hub porque ambos podem disputar as mesmas COMs.

### Teste de bancada planejado

1. copiar `vector_service.py` e os scripts para `C:\Ham\GADX-Vector\service`;
2. manter `vector_hub.py`, `ts2000.py` e `vector.ini` validados na Fase A;
3. executar `install-service.ps1` como Administrador;
4. verificar `Get-Service GADXVectorHub`;
5. verificar `logs\vector-hub.log`;
6. repetir CAT/PTT/CW com o mesmo software usado na Fase A;
7. parar/iniciar o servico e confirmar fail-safe;
8. reiniciar o Windows e validar delayed auto-start;
9. testar recovery em uma falha controlada posteriormente.

A Fase B so sera marcada VALIDATED depois desses testes.

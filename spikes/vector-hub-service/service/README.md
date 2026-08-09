# Vector Hub Windows Service contract

O servico deste SPIKE sera implementado em `vector_service.py` e substituira conceitualmente o wrapper single-client de `../cat-ts2000/service/vector_bridge_service.py`.

## Responsabilidades

- executar `app/vector_hub.py` usando o Python privado do Vector;
- usar `config/vector.ini` como fonte de configuracao;
- iniciar como Automatic (Delayed Start);
- permitir stop controlado;
- aplicar recovery/restart on failure;
- redirecionar stdout/stderr do runtime para log persistente;
- girar logs segundo `[logging]`;
- aplicar fail-safe independente antes/depois do processo filho;
- validar que o runtime permaneceu ativo apos o start;
- retornar erro claro ao Windows Event Log quando o processo filho falhar.

## Fail-safe do servico

O wrapper deve entender diretamente:

```ini
[radio_keying]
port = ...
baud = ...
ptt_line = ...
cw_line = ...

[rig]
host = ...
port = ...
```

Ao parar/falhar, deve fazer best effort para:

```text
RTS = OFF
DTR = OFF
rigctld set_ptt 0
```

O fail-safe do wrapper e uma camada adicional ao fail-safe do runtime.

## Logging

```ini
[logging]
level = INFO
max_mb = 5
backups = 5
```

`level` e passado ao runtime. `max_mb` e `backups` sao responsabilidade deste wrapper.

## Fora de escopo

O servico nao cria COMs, nao instala com0com e nao decide quais clientes existem. Ele executa exatamente a configuracao persistida pelo provisionador/instalador.

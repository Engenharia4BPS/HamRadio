# Vector Hub runtime contract

O runtime deste SPIKE sera implementado em `vector_hub.py` a partir da base validada em:

```text
../../cat-ts2000/rigctld_bridge_multi.py
```

## Responsabilidades do runtime

- ler `[cat]`, `[keying]`, `[radio_keying]`, `[rig]` e `[runtime]` de `vector.ini`;
- abrir N fachadas CAT;
- manter um `TS2000Emulator` por cliente CAT;
- compartilhar o acesso ao rigctld de forma thread-safe;
- abrir N entradas de keying;
- manter o caminho CW low-latency;
- consolidar PTT/CW por fonte;
- abrir e controlar a COM fisica de keying;
- executar fail-safe local ao iniciar/encerrar;
- escrever logs em stdout/stderr para que o supervisor decida o destino.

## O que NAO pertence ao runtime

- instalar Python;
- instalar ou criar pares com0com;
- escolher COMs livres;
- instalar/remover Windows Service;
- girar arquivos de log;
- definir politica de recovery do servico;
- alterar configuracao automaticamente durante o boot.

Essas responsabilidades pertencem ao provisionador, instalador ou wrapper de servico.

## Regra de portabilidade

A primeira versao de `vector_hub.py` deve ser uma portagem conservadora da multi-bridge congelada. Renomear/reorganizar configuracao e logging e permitido; alterar o caminho de CW, protocolo CAT ou semantica de keying exige teste de regressao antes de entrar.

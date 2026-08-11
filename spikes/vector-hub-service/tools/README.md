# Phase C — GADX Vector Port Manager

Objetivo: validar uma ferramenta visual para inventariar e provisionar pares com0com sem esconder do operador o que sera criado/removido.

## Escopo v0.1

- localizar `setupc.exe` do com0com;
- executar `setupc` com `cwd` no diretorio correto, evitando o problema de `com0com.inf` resolvido em `C:\Windows\System32`;
- ler `list` e `busynames *`;
- inventariar portas seriais ativas via `pyserial`;
- mostrar os pares existentes;
- sugerir 4 pares inicialmente;
- editar Cliente / Tipo / COM do aplicativo / COM interna do Vector;
- adicionar/remover linhas;
- aplicar o plano somente com confirmacao;
- nunca sobrescrever silenciosamente uma porta ativa;
- nunca forcar uma reserva ComDB na v0.1;
- remover apenas pares com0com que aparecem no inventario atual.

## Regra de seguranca

A v0.1 considera uma COM indisponivel quando ela aparece como:

- porta serial ativa; ou
- nome ocupado/reservado retornado por `busynames *`.

Mesmo que uma reserva pareca orfa, a v0.1 nao clica/aceita automaticamente `CONTINUE` do setupc. A classificacao segura de reservas orfas sera uma evolucao posterior.

## Sugestao inicial

Quando nao existem pares com0com, a interface sugere 4 pares:

```text
Cliente 1   CAT
Cliente 1   KEYING
Cliente 2   CAT
Cliente 2   KEYING
```

A busca inicia em COM15 no lado do aplicativo e COM101 no lado interno, pulando nomes ativos/reservados.

## Executar

Com Python que possua `pyserial`:

```powershell
& "C:\Ham\GADX-Vector\runtime\python.exe" `
  "C:\Ham\GADX-Vector\tools\port_manager.py"
```

Para a bancada legada da Fase B:

```powershell
& "C:\Python\Python310\python.exe" `
  "C:\Ham\GADX-Vector\tools\port_manager.py"
```

A ferramenta deve ser aberta como Administrador para aplicar alteracoes. Inventario e visualizacao podem funcionar sem elevacao.

## O que ainda nao faz

- nao gera `vector.ini`;
- nao guarda nomes/owners em `ports.json`;
- nao identifica automaticamente reservas ComDB orfas;
- nao instala/repara com0com;
- nao reinicia o `GADXVectorHub`;
- nao configura RTS/DTR de clientes KEYING;
- nao oferece diagnostico de rigctld/Hub.

Esses pontos entram apenas depois que a mecanica visual de inventario + create/remove estiver validada em bancada.

# GADX Vector — Vector Hub Runtime / Service / Installer SPIKE

## Status

**ACTIVE / SPIKE 02**

Este SPIKE sucede `../cat-ts2000/`, congelado apos validar a fachada TS-2000, CAT multi-client e keying low-latency.

Estado atual:

- **Fase A — Runtime: VALIDADA em bancada**;
- **Fase B — Windows Service: VALIDADA funcionalmente em bancada**;
- **Fase C — Vector Port Manager: EM DESENVOLVIMENTO / funcional em bancada**.

A pergunta atual e:

> Conseguimos transformar a arquitetura CAT + keying ja validada em um componente persistente, configuravel, reparavel e instalavel do GADX Vector no Windows?

## Estrutura atual

```text
spikes/vector-hub-service/
├── README.md
├── app/
│   ├── vector_hub.py
│   └── ts2000.py
├── config/
│   └── vector.ini
├── service/
│   ├── vector_service.py
│   ├── install-service.ps1
│   └── uninstall-service.ps1
└── tools/
    ├── port_manager.py
    └── README.md
```

## Arquitetura-alvo

```text
                            GADX VECTOR HUB

 CAT clients                                      Keying clients
 COM101 -- TS2000 adapter --\                    COM102 --\
 COM103 -- TS2000 adapter ---+-- shared rig -->  COM104 ---+-- logical states
 COM105 -- TS2000 adapter ---+   rigctld         COM106 --/        |
 COM107 -- TS2000 adapter --/                                  physical COM
                                                                  |
                                                               PTT / CW
```

Cada software possui sua propria COM virtual. O Hub nao tenta fazer dois processos abrirem a mesma COM.

## Conceito de pares COM

Cada canal virtual usa um par com0com:

```text
COM do aplicativo  <->  COM interna do Vector
```

Exemplo real de bancada:

```text
LogHX CAT       COM9  <-> COM101
LogHX KEYING    COM29 <-> COM102
N1MM CAT        COM15 <-> COM103
N1MM KEYING     COM30 <-> COM104
OmniRig CAT     COM16 <-> COM105
OmniRig KEYING  COM31 <-> COM106
```

A ponta **Aplicativo** e configurada dentro do LogHX, N1MM, OmniRig etc. A ponta **Vector** e aberta exclusivamente pelo `vector_hub.py`.

## CAT x KEYING

CAT e o canal de controle do radio: frequencia, modo e comandos. O software cliente enxerga uma fachada TS-2000; o radio fisico continua atras do Hamlib/rigctld.

KEYING e separado de CAT e transporta PTT/CW por linhas DTR/RTS. O caminho de CW continua separado de chamadas bloqueantes do rigctld para preservar baixa latencia e baixo jitter.

## Configuracao principal

O arquivo principal e:

```text
C:\Ham\GADX-Vector\config\vector.ini
```

Formato recomendado para clientes de keying:

```ini
[cat]
ports = COM101, COM103, COM105
baud = 19200

[keying]
; clientN = NOME,PORTA_VECTOR,PTT_INPUT,CW_INPUT
client1 = LogHX,COM102,DTR,RTS
client2 = N1MM,COM104,DTR,RTS
client3 = OmniRig,COM106,DTR,NONE
```

O runtime continua aceitando o formato legado:

```ini
client1 = COM102,DTR,RTS
```

Nesse caso, ferramentas e logs usam nomes genericos como `Cliente 1` / `client1`.

Configuracao completa tipica:

```ini
[radio_keying]
port = COM22
baud = 9600
ptt_line = RIGCTLD
cw_line = RTS

[rig]
host = 127.0.0.1
port = 4532
poll_ms = 250

[runtime]
allow_write = true
allow_ptt = true
allow_cw = true

[service]
startup = delayed-auto
recovery = restart

[logging]
level = INFO
max_mb = 5
backups = 5

[ports]
application_start = 15
vector_start = 101
```

## Politica de portas COM

Para novas instalacoes:

```text
lado apresentado aos aplicativos: tentar COM15, COM16, COM17... em ordem crescente
lado interno do Vector:           tentar COM101, COM102, COM103... em ordem crescente
```

COM15 e apenas o primeiro candidato. Portas existentes/ocupadas nunca devem ser sobrescritas silenciosamente. Instalacoes legadas podem manter numeros como COM9/COM29.

## Principios consolidados

1. Uma COM virtual por cliente/canal.
2. TS-2000 e fachada; o radio fisico fica atras do Hamlib/rigctld.
3. CAT e keying sao canais independentes.
4. RTS/DTR pertencem ao INI da instalacao, nao ao modelo de radio no codigo.
5. CW e tempo-critico e fica fora de polling/chamadas bloqueantes do rigctld.
6. Estados multi-client de PTT/CW sao mantidos por fonte e consolidados logicamente.
7. COMs altas sao internas; COMs baixas sao apresentadas aos softwares sempre que possivel.
8. Fail-safe tem prioridade: parar, falhar ou reiniciar nao pode deixar PTT/CW acionados.
9. ComDB sozinho nao define disponibilidade: o provisionador cruza pares com0com, portas ativas e reservas.
10. O operador deve conseguir ver e aprovar o plano antes da criacao/remocao de COMs.
11. Nomes amigaveis de clientes fazem parte da configuracao gerenciada e ajudam diagnostico futuro.

## Fase A — Runtime

`app/vector_hub.py` e a evolucao da multi-bridge congelada. Foi validado manualmente e depois executado pelo servico, preservando CAT, PTT e CW da bancada.

## Fase B — Windows Service

`service/vector_service.py` executa o Hub, usa `vector.ini`, aplica fail-safe, gira logs e funciona com Python privado ou fallback de bancada durante o SPIKE.

Servico:

```text
GADXVectorHub
Automatic (Delayed Start)
Recovery: restart on failure
```

## Fase C — GADX Vector Port Manager

Ferramenta:

```text
tools/port_manager.py
```

O Port Manager ja consegue:

- inventariar portas COM ativas do Windows;
- localizar o `setupc.exe` do com0com;
- consultar pares com0com e nomes reservados;
- esconder consoles auxiliares durante operacoes normais;
- mostrar progresso visual e etapa atual;
- mostrar cada cliente em uma unica linha;
- separar visualmente CAT e KEYING;
- usar dropdowns de portas disponiveis;
- adicionar/remover clientes no plano;
- sugerir COMs livres;
- carregar `vector.ini` existente;
- cruzar COMs internas do INI com a outra ponta do par com0com;
- ler nomes amigaveis de `clientN`;
- usar fallback `Cliente N` em configuracoes legadas;
- detectar alteracoes de nome mesmo quando nenhuma COM mudou;
- persistir nomes amigaveis no `[keying]` preservando comentarios do INI;
- mostrar resumo antes de aplicar alteracoes;
- oferecer tooltips em campos, cabecalhos e botoes;
- abrir ajuda completa pelo botao `?`.

### Fluxo recomendado de uso

Para alterar uma estacao existente:

1. executar o Port Manager como Administrador;
2. aguardar o inventario inicial;
3. clicar em **Carregar configuracao atual**;
4. conferir nomes, CAT, KEYING e os dois lados de cada par;
5. alterar/adicionar/remover somente o necessario;
6. clicar em **Aplicar configuracao**;
7. ler o resumo das alteracoes;
8. confirmar somente se o plano estiver correto.

**Recarregar inventario** apenas consulta novamente Windows/com0com e nao altera a configuracao.

### Help embarcado

A partir da v0.11 existe um botao `?` no canto superior da janela. Ele abre uma ajuda rolavel explicando:

- objetivo do Port Manager;
- arquitetura CAT + KEYING;
- diferenca entre COM Aplicativo e COM Vector;
- papel do com0com;
- relacao com `vector.ini`;
- fluxo de alteracao de uma estacao existente;
- politica COM15+/COM101+;
- cuidados antes de aplicar;
- diagnostico basico de inventario, CAT e keying.

Os campos e botoes continuam com tooltips curtos para consulta rapida.

### Limite atual da Fase C

O Port Manager ja gerencia pares com0com e nomes amigaveis de clientes. **Ainda nao persiste automaticamente toda alteracao estrutural da tela no `vector.ini`**. Transformar a tela inteira na fonte persistente da configuracao do Hub e o proximo marco importante da Fase C.

A evolucao seguinte deve incluir:

- regravar `[cat]` e `[keying]` completos a partir da tela;
- preservar comentarios e secoes nao gerenciadas;
- persistir owners/mapeamentos de forma estruturada;
- opcionalmente parar/reiniciar `GADXVectorHub` ao aplicar mudancas;
- classificar FREE / ACTIVE_PHYSICAL / ACTIVE_COM0COM / RESERVED_COMDB / ORPHAN_RESERVATION / CONFLICT.

## Criterios de aceite do SPIKE 02

- [x] runtime multi-client executado em bancada;
- [x] Windows Service inicia o Hub e mantem CAT/keying funcionais;
- [x] logs limitados por configuracao de servico;
- [x] mapeamento PTT via RIGCTLD + CW serial validado em bancada;
- [x] dois ou mais clientes CAT funcionam simultaneamente em bancada;
- [x] Port Manager inventaria pares com0com e portas ativas;
- [x] Port Manager carrega configuracao existente e reconstrói pares quando o com0com responde;
- [x] nomes amigaveis de keying sao carregados e persistidos;
- [x] help/tooltips incorporados ao Port Manager;
- [ ] runtime instalado por instalador limpo em `C:\Ham\GADX-Vector`;
- [ ] Python privado provisionado automaticamente;
- [ ] com0com instalado/detectado automaticamente;
- [ ] provisionamento automatico/visual com preferencia COM15+;
- [ ] namespace interno COM101+ criado automaticamente;
- [ ] N clientes CAT/keying persistidos integralmente pelo Port Manager;
- [ ] reboot completo com servico retomando sozinho validado;
- [ ] repair/reinstall preservando configuracao;
- [ ] documentacao final de instalacao/diagnostico.

## Fase D — Installer

Somente depois da Fase C provar o provisionamento e a persistencia completa, construiremos a nova geracao do instalador usando as licoes do instalador antigo.

## Fase E — Regressao

Repetir os cenarios reais em mais de uma estacao antes de encerrar o SPIKE.

## Decisoes que ainda exigem teste

- conflitos de escrita CAT simultanea;
- reconexao depois de queda/reinicio do `rigctld`;
- classificacao segura de reservas ComDB orfas;
- comportamento de service recovery quando COMs ainda nao enumeraram no boot;
- split/VFO A/B multi-client;
- eventual PTT por comando CAT no mesmo OR das fontes de keying.

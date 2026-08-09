# SPIKE congelado — CAT/Keying TS-2000

**Status: FROZEN / VALIDATED**

Este SPIKE cumpriu seu objetivo experimental e fica congelado como referencia de bancada e regressao.

Nao introduzir novas funcionalidades aqui, salvo correcoes estritamente necessarias para reproduzir os testes historicos.

## O que este SPIKE respondeu

Foi demonstrado que o GADX Vector pode:

- apresentar uma fachada CAT Kenwood TS-2000 para softwares de radio;
- atender multiplos clientes CAT por COMs virtuais independentes;
- compartilhar um unico radio fisico atras de Hamlib/rigctld;
- receber PTT/CW por clientes de keying independentes;
- mapear DTR/RTS por configuracao;
- preservar CW em caminho dedicado low-latency;
- consolidar estados multi-client de PTT/CW;
- operar na pratica com diferentes softwares e em mais de uma instalacao.

## Continuidade

A evolucao continua em:

```text
../vector-hub-service/
```

O novo SPIKE nao reabre a pergunta de viabilidade do CAT/keying. Ele parte desta base validada para estudar runtime, servico Windows, configuracao, provisionamento de COMs e instalacao/reparo.

## Regra de preservacao

Os arquivos `rigctld_bridge.py`, `rigctld_bridge_multi.py`, `bridge.ini` e `bridge_multi.ini` permanecem como artefatos de referencia da fase experimental.

Mudancas arquiteturais devem ser feitas no novo SPIKE.

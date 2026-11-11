# GADX WinKey Emulator — protótipo isolado para N1MM

Este protótipo permite que o N1MM Logger+ entregue textos CW a um `rigctld` remoto pela interface serial WinKey, sem modificar o caminho atual de CAT, PTT, CW físico ou FSK do **GADX Vector Hub**.

Ele é deliberadamente um processo separado: não é Windows Service, não integra o instalador, não lê nem escreve `C:\Ham\GADX-Vector\config\vector.ini`, e não abre a COM física usada pelo Vector.

```text
N1MM (COM40, WinKey)  <->  COM140  GADX WinKey Emulator
                                      |
                                      | b CQ TEST PY5XT
                                      | 0xbb  (Abort)
                                      | L KEYSPD 32
                                      v
                                  rigctld remoto
                                      v
                                  keyer do rádio

GADXVectorHub continua, em paralelo, usando suas COMs CAT/keying atuais.
```

## Escopo desta primeira prova

Implementado:

- handshake WinKey usado pelo N1MM: `ADMIN/ECHO` e `ADMIN/OPEN`, com revisão WK2 configurável;
- texto ASCII buffered, agrupado após `15 ms` de silêncio por padrão, em um único `b TEXTO`;
- velocidade WinKey imediata, buffered e `Load Defaults`, em `L KEYSPD <WPM>`;
- `CLEAR BUFFER` (`0x0A`), `PAUSE` e fim da sessão limpam o estado WinKey local; por padrão não interrompem texto já aceito pelo keyer remoto;
- `stop_morse` (`0xbb`) pode ser habilitado explicitamente apenas para backends em que tenha sido validado sem efeitos espúrios;
- consultas de status e speed-pot suficientes para o handshake; o bit `BUSY` é estimado a partir do texto/WPM;
- eventos WinKey de `BUSY`/idle e, quando o N1MM habilita esse modo, eco serial de cada caractere segundo temporização Morse estimada;
- comandos de ponteiro que o N1MM usa antes de mensagens com alteração buffered de velocidade;
- parsing seguro de comandos comuns que ainda não têm mapeamento, para que seus parâmetros não virem texto CW.

Intencionalmente fora de escopo nesta prova: paddle físico/por software, tune/key-down, PTT via WinKey, weighting, Farnsworth, timing de waits e posição de alterações de velocidade dentro de uma mensagem. Esses recursos não acionam PTT, DTR, RTS ou o CW físico do Vector.

O N1MM documenta que um emulador WinKey recebe caracteres ASCII e é adequado para transformar esses textos em CW; a documentação K1EL define o `ADMIN/OPEN`, o comando de velocidade, `CLEAR BUFFER` e os status que este protótipo implementa. Consulte [N1MM — Configurer](https://n1mmwp.hamdocs.com/setup/the-configurer/) e [K1EL WinKeyer2 manual](https://www.k1elsystems.com/files/WinkeyUSBman.pdf).

## Instalação sem alterar o Vector

1. Confirme que o Vector atual está normal e faça seu teste de CAT/PTT/CW físico habitual. Não pare nem reinstale `GADXVectorHub`.

2. Crie um novo par com0com **fora do Port Manager**. O Port Manager associa cada linha ao `vector.ini`; portanto, usar “Adicionar cliente” para este teste criaria canais CAT/CW/FSK do Hub e deixaria esse par sujeito a remoção no próximo Apply. Em um PowerShell elevado, usando os números livres do exemplo:

   ```text
   N1MM: COM40  <->  Emulador: COM140
   ```

   ```powershell
   Push-Location "C:\Program Files (x86)\com0com"
   try {
     .\setupc.exe install "PortName=COM40" "PortName=COM140"
     .\setupc.exe list
   }
   finally {
     Pop-Location
   }
   ```

   `setupc.exe` localiza o arquivo `com0com.inf` no diretório de trabalho. Por isso, chamar o EXE por caminho completo a partir de `C:\Ham\GADX-Vector\tools` falha com `SetupOpenInfFile(...com0com.inf)`; entre na pasta de instalação do com0com antes de executá-lo.

   Substitua os números somente se já estiverem usados. Não reutilize `COM30/COM104` (ou qualquer par do keying atual) e não ligue RTS/DTR deste novo par a equipamento físico. Enquanto o par experimental existir, não use **Aplicar configuração** no Port Manager: ele conhece apenas os pares pertencentes ao Vector e poderá propor remover o par independente.

3. Copie esta pasta para um diretório experimental independente, por exemplo:

   ```text
   C:\Ham\GADX-WinKey-Emulator
   ```

4. Copie `winkey.ini.example` para `winkey.ini`. Ajuste somente a porta `COM140` e, se necessário, `[rigctld] host`/`port`. Mantenha `allow_transmit = false` nesta primeira partida. O padrão `abort_mode = none` evita enviar abort remoto automaticamente.

5. Verifique apenas a configuração:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass `
     -File C:\Ham\GADX-WinKey-Emulator\run-winkey-emulator.ps1 -Check
   ```

   A saída esperada contém `CONFIG_OK`; esse modo não abre COM nem se conecta ao rádio.

6. Inicie o emulador em uma janela PowerShell separada:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass `
     -File C:\Ham\GADX-WinKey-Emulator\run-winkey-emulator.ps1
   ```

   O script reutiliza somente o Python privado já instalado pelo Vector (`C:\Ham\GADX-Vector\runtime\python.exe`). Não instala bibliotecas nem registra serviço.

## Inicialização automática (perfil de rede)

Quando instalado pelo perfil `installer/network-client`, o emulador roda como
o serviço Windows `GADXWinKeyEmulator`, separado do `GADXVectorHub`. O log fica
em `C:\Ham\GADX-Vector\logs\winkey-emulator.log`. O serviço abre somente a
COM WinKey dedicada e usa o `winkey.ini` separado; ele nunca abre a COM física
de keying nem altera `vector.ini`.

## Configuração e validação no N1MM

No **Config > Configure Ports, Mode Control, Winkey, etc.**:

1. Selecione `COM40` em uma linha livre.
2. Marque `CW/Other`, abra **Set** e marque **WinKey**.
3. Não marque CW/Other na COM física/virtual usada pelo keying atual enquanto estiver neste teste; mantenha um só método de CW ativo para o rádio em teste.
4. Na guia WinKey, use uma velocidade inicial de 28 WPM e marque **Ignore Winkey Speed Pot** (este emulador não tem potenciômetro físico).
5. Feche e reabra o Configurer. O log deve mostrar `WinKey host interface opened`; com `allow_transmit = false`, F1/F2/F3 deve registrar `CW text -> ...` e `TX disabled`, sem transmissão.

Depois de validar o texto e o destino do `rigctld`, pare o emulador com `Ctrl+C`, mude explicitamente `allow_transmit = true` e inicie-o de novo. Faça primeiro uma mensagem curta com carga desligada ou frequência/mode de teste. Verifique no log:

```text
CW speed -> 28 WPM
CW text -> 'TEST'
```

No padrão `abort_mode = none`, `Esc` limpa a fila local do N1MM, mas texto já entregue ao keyer interno do rádio termina normalmente. Não envie uma nova macro até esse texto acabar. Só use `abort_mode = stop_morse` em um rádio/backend onde o comando `0xbb` tenha sido validado para realmente interromper CW sem transmitir caracteres extras.

## Plano de validação e critérios de aceite

| Etapa | Ação | Resultado esperado | Proteção |
| --- | --- | --- | --- |
| 0 | Rodar `-Check` | `CONFIG_OK` | Não abre hardware nem rede |
| 1 | Iniciar com `allow_transmit=false`; configurar N1MM como WinKey | `WinKey host interface opened` | Nenhum comando TX é enviado |
| 2 | F1/F2/F3 no N1MM | Texto expandido aparece agrupado no log | Nenhum `b` é enviado |
| 3 | Mudar WPM na interface N1MM | `CW speed -> <WPM>` no log | Nenhum `L KEYSPD` é enviado |
| 4 | Confirmar host/porta do rigctld e habilitar `allow_transmit=true` | apenas depois de revisão manual | Opt-in explícito |
| 5 | Enviar `TEST` em carga/frequência de teste | rigctld recebe `L KEYSPD` e `b TEST`; rádio gera CW | Vector continua ativo e sem alteração |
| 6 | Iniciar mensagem longa e pressionar `Esc` | Estado WinKey local volta a idle; rádio termina texto já aceito | Não toca RTS/DTR do Vector |
| 7 | Fechar o emulador (`Ctrl+C`) durante um envio | Processo encerra sem enviar abort remoto no modo padrão | Serviço e INI do Vector intactos |
| 8 | Retornar N1MM à COM/método de CW anterior | CW físico original funciona como antes | Rollback sem instalação |

## Rollback

1. Feche o emulador (`Ctrl+C`). No modo padrão, ele não envia abort remoto; qualquer texto já presente no keyer interno do rádio termina normalmente.
2. No N1MM, desmarque WinKey/COM40 ou retorne à porta CW anterior.
3. Se desejar, rode `setupc.exe list`, confirme o índice do par `COM40 <-> COM140` e remova somente esse índice com `setupc.exe remove <índice>`. Não use o Port Manager para remover este par independente.
4. Apague `C:\Ham\GADX-WinKey-Emulator`.

Nenhum desses passos modifica `vector.ini`, o serviço `GADXVectorHub`, os pares COM CAT/CW existentes ou a COM física.

## Testes automatizados

Sem rádio e sem COM física:

```powershell
& "C:\Ham\GADX-Vector\runtime\python.exe" `
  -m unittest discover -s C:\Ham\GADX-WinKey-Emulator\tests -v
```

Os testes cobrem o handshake, batch ASCII, WPM/KEYSPD, `CLEAR BUFFER`, status, bloco `Load Defaults`, a opção segura de abort local e a emissão opt-in de `L KEYSPD`, `b TEXTO` e `0xbb` contra um rigctld simulado.

## Diagnóstico sem RF

Se o texto exibido pelo rádio divergir do `CW text -> ...` do emulador, não faça novos testes no ar. Use o receptor local incluso para separar o protocolo WinKey do rigctld/radio:

1. Pare o emulador e deixe `allow_transmit = true` somente para este teste seguro. Em `[rigctld]`, troque temporariamente `port = 4532` por `port = 45330`. Em `[logging]`, defina `protocol_trace = true`.
2. Em uma janela PowerShell, execute:

   ```powershell
   & "C:\Ham\GADX-Vector\runtime\python.exe" `
     "C:\Ham\GADX-WinKey-Emulator\rigctld_recorder.py" --port 45330
   ```

3. Em outra janela, inicie `run-winkey-emulator.ps1` e envie F3/F4 a 22 WPM pelo N1MM. O recorder deve mostrar linhas exatas como:

   ```text
   RIGCTL RX -> 'L KEYSPD 22'
   RIGCTL RX -> 'b TU'
   ```

   O recorder responde `RPRT 0`, mas não se conecta ao rádio. Assim, mesmo com `allow_transmit = true`, não há RF.
4. Pare ambos com `Ctrl+C`, volte `port = 4532`, `allow_transmit = false` e `protocol_trace = false`. Guarde as duas saídas para análise.

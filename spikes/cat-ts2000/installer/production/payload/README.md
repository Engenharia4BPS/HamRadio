# Payloads externos do GADX Vector Setup

Os binários de terceiros **não são versionados no repositório**.

Antes de compilar `GADX-Vector-Setup.exe`, esta pasta deve conter:

```text
payload/
├── python-installer.exe
└── com0com/
    ├── setupc.exe
    ├── com0com.inf
    ├── ... arquivos CAT/SYS/INF da distribuição signed ...
```

## Python

Use o instalador oficial Windows x64 da versão de Python homologada para a release do Vector.

O `install-vector.ps1` instala essa cópia de forma privada em:

```text
C:\Ham\GADX-Vector\runtime
```

Sem adicionar Python ao PATH, sem launcher, sem associações de `.py` e sem atalhos.

## com0com

Use a **distribuição signed completa** que contenha `setupc.exe` e os arquivos de driver necessários. O diretório completo é empacotado dentro do Setup para que o instalador consiga consultar `busynames`, criar os pares virtuais e instalar/atualizar o driver quando necessário.

Antes de distribuir publicamente uma release, registre no documento de release:

- nome e versão exata do pacote;
- origem do download;
- licença;
- SHA-256 do pacote original;
- SHA-256 do `GADX-Vector-Setup.exe` final.

## Build

Exemplo:

```powershell
.\build-installer.ps1 `
  -PythonInstaller C:\Downloads\python-3.12.x-amd64.exe `
  -Com0comDirectory C:\Temp\com0com-signed
```

O resultado será:

```text
dist\GADX-Vector-Setup.exe
```

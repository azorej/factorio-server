# Factorio dedicated server on Yandex Cloud

## Architecture

1. Setup [Yandex Container Solution](https://yandex.cloud/en/docs/cos/) VM
2. Run Docker image from https://github.com/factoriotools/factorio-docker 
3. TODO: mount volumes for saves, setup backups

## Settings
Main settings is in `dagger/src/main/config.py`

## CI/CD

The project uses [Dagger](https://dagger.io/) as main CI tool.
IaC (Infrastructure as code) is done via [OpentFofu](https://opentofu.org/).
Local development is done via VSCode and [local devcontainer](https://code.visualstudio.com/docs/devcontainers/containers).

## Local development
 
### Requirements:
- [VSCode](https://code.visualstudio.com/download)
- [Docker](https://docs.docker.com/engine/install/)

### Starting Guide
0. [Create billing account in Yandex Cloud](https://yandex.cloud/en/docs/billing/quickstart/)
1. Clone repository
2. Open project in VSCode
3. Rebuild and reopen in Devcontainer: `<CTRL>/<CMD> + <SHIFT> + P` -> `Dev Container: Reopen in Container`
4. Customize `config.py` (**YC_TOFU_BUCKET_NAME must be unique across the whole platform**)
5. Call `apply-tofu` Dagger function


## Dagger cheatsheet

Deploy installation:
```bash
dagger call apply-tofu --open-tofu-dir=opentofu
```

Connect to machine:
```bash
dagger call open-ssh --open-tofu-dir=opentofu
```

Stop machine:
```bash
dagger call command-server-machine --command=stop
```
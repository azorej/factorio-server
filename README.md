# Factorio dedicated server on Yandex Cloud

## Architecture

1. Setup [Yandex Container Solution](https://yandex.cloud/en/docs/cos/) VM
2. Run Docker image from https://github.com/factoriotools/factorio-docker 
3. TODO: mount volumes for saves, setup backups

## Settings
Main settings is in `dagger/src/main/config.py`

## CI/CD

The project uses [Dagger](https://dagger.io/) as main CI tool.
Local development is done via VSCode and [local devcontainer](https://code.visualstudio.com/docs/devcontainers/containers).

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
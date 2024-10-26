import typing as tp
from datetime import datetime

import dagger
from dagger import dag, function, object_type

from main.utils import add_env_variables, exec_bash, exec_bash_and_save_exit_code, install_packages


@object_type
class FactorioServer:
    @function
    def ubuntu_base(self) -> dagger.Container:
        return (
            dag.container()
            .from_('ubuntu:noble')
            .with_(install_packages(['curl']))
            .with_(add_env_variables(HOME='/root'))
        )

    @function
    def yandex_cloud_cli(self) -> dagger.Container:
        base = tp.cast(dagger.Container, self.ubuntu_base())
        return base.with_(
            exec_bash("""
                curl https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash -s -- -i /opt/yc -a
            """)
        ).with_env_variable('PATH', '/opt/yc/bin:$PATH', expand=True)

    @function
    async def open_tofu_cli(self) -> dagger.Container:
        platform = (await dag.default_platform()).split('/')[1]
        base = tp.cast(dagger.Container, self.ubuntu_base())
        return base.with_(install_packages(['zip', 'wget'])).with_(
            exec_bash(f"""
                # https://edu.chainguard.dev/open-source/sigstore/cosign/how-to-install-cosign/#installing-cosign-with-the-cosign-binary
                wget "https://github.com/sigstore/cosign/releases/download/v2.0.0/cosign-linux-{platform}" 
                mv cosign-linux-amd64 /usr/local/bin/cosign 
                chmod +x /usr/local/bin/cosign

                # https://opentofu.org/docs/intro/install/standalone/
                curl --proto '=https' --tlsv1.2 -fsSL https://get.opentofu.org/install-opentofu.sh -o install-opentofu.sh
                chmod +x install-opentofu.sh
                ./install-opentofu.sh --install-method standalone
                rm -f install-opentofu.sh
            """)  # noqa
        )

    @function
    async def login_yandex_cloud(self) -> dagger.Secret:
        yc_config_volume = dag.cache_volume('yc_config')
        c = self.yandex_cloud_cli().with_mounted_cache('${HOME}/.config/yandex-cloud', yc_config_volume, expand=True)  # type: ignore

        exit_code_file = '/exit_code'
        check_logged_c = (
            await c.with_env_variable('CACHEBUSTER', str(datetime.now()))
            .with_(exec_bash_and_save_exit_code('yc resource-manager folder list', exit_code_file))
            .sync()
        )
        logged_in = (await check_logged_c.file(exit_code_file).contents()).strip() == '0'

        if not logged_in:
            c = await c.terminal(cmd=['yc', 'init'])

        yc_config = (
            await c.with_exec(['cp', '${HOME}/.config/yandex-cloud/config.yaml', '/secret'], expand=True)
            .file('/secret')
            .sync()
        )

        return dag.set_secret('yc-creds', await yc_config.contents())

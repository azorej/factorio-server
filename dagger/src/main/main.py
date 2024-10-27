import json
import typing as tp
from datetime import datetime
from textwrap import dedent

import dagger
import pydantic
from dagger import DaggerError, dag, enum_type, function, object_type

from main.config import (
    FACTORIO_IMAGE_TAG,
    HOST_INSTANCE_NAME,
    HOST_USERNAME,
    YC_FOLDER_NAME,
    YC_SERVICE_ACCOUNT,
    YC_TOFU_BUCKET_NAME,
    YC_ZONE,
)
from main.utils import add_env_variables, exec_bash, exec_bash_and_save_exit_code, install_packages


@enum_type
class MachineCommand(dagger.Enum):
    START = 'start', 'Start machine'
    STOP = 'stop', 'Stop machine'
    RESTART = 'restart', 'Restart machine'


class YcFolderInfo(pydantic.BaseModel):
    id: str
    cloud_id: str
    created_at: datetime
    name: str
    status: str


class YcServiceAccount(pydantic.BaseModel):
    id: str
    name: str


class YcAnonymousAccessFlags(pydantic.BaseModel):
    read: bool
    list: bool


class YcBucketInfo(pydantic.BaseModel):
    name: str
    folder_id: str
    anonymous_access_flags: YcAnonymousAccessFlags
    default_storage_class: str
    versioning: str
    max_size: tp.Optional[str] = None
    created_at: datetime


class YcServiceAccessAccountKey(pydantic.BaseModel):
    id: str = pydantic.Field(validation_alias=pydantic.AliasPath('access_key', 'id'))
    key_id: str = pydantic.Field(validation_alias=pydantic.AliasPath('access_key', 'key_id'))
    secret: str

    class Config:
        populate_by_name = True


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
    async def logged_yandex_cloud_cli(self) -> dagger.Container:
        return (
            self.yandex_cloud_cli()
            .with_mounted_secret(
                '${HOME}/.config/yandex-cloud/config-bak.yaml', await self.login_yandex_cloud(), expand=True
            )
            .with_exec(
                ['cp', '${HOME}/.config/yandex-cloud/config-bak.yaml', '${HOME}/.config/yandex-cloud/config.yaml'],
                expand=True,
            )
        )

    @function
    async def init_yc_folder(self) -> str:
        c = await self.logged_yandex_cloud_cli()
        folders = pydantic.TypeAdapter(list[YcFolderInfo]).validate_json(
            await c.with_exec(['yc', 'resource-manager', 'folder', 'list', '--format=json']).stdout()
        )
        for f in folders:
            if f.name == YC_FOLDER_NAME:
                target_folder = f
                break
        else:
            target_folder = YcFolderInfo.model_validate_json(
                await c.with_exec(
                    [
                        'yc',
                        'resource-manager',
                        'folder',
                        'create',
                        '--name',
                        YC_FOLDER_NAME,
                        '--description',
                        'Managed by: https://github.com/azorej/factorio-server/tree/main',
                        '--format=json',
                    ]
                ).stdout()
            )

        if target_folder.status != 'ACTIVE':
            raise DaggerError(f'Folder {YC_FOLDER_NAME} in invalid state: {f.status}')

        return target_folder.model_dump_json()

    @function
    async def init_yc_service_account(self) -> str:
        c = await self.logged_yandex_cloud_cli()
        folder = YcFolderInfo.model_validate_json(await self.init_yc_folder())
        accounts = pydantic.TypeAdapter(list[YcServiceAccount]).validate_json(
            await c.with_exec(
                ['yc', 'iam', 'service-account', 'list', f'--folder-id={folder.id}', '--format=json']
            ).stdout()
        )
        for a in accounts:
            if a.name == YC_SERVICE_ACCOUNT:
                target_account = a
                break
        else:
            target_account = YcServiceAccount.model_validate_json(
                await c.with_exec(
                    [
                        'yc',
                        'iam',
                        'service-account',
                        'create',
                        '--name',
                        YC_SERVICE_ACCOUNT,
                        f'--folder-id={folder.id}',
                        '--format=json',
                    ]
                ).stdout()
            )

        await c.with_exec(
            [
                'yc',
                'resource-manager',
                'folder',
                'set-access-bindings',
                folder.id,
                '--access-binding',
                f'role=editor,subject=serviceAccount:{target_account.id}',
                '-y',
                f'--folder-id={folder.id}',
            ]
        ).sync()

        return target_account.model_dump_json()

    @function
    async def service_logged_yandex_cloud_cli(self) -> dagger.Container:
        account_info = YcServiceAccount.model_validate_json(await self.init_yc_service_account())
        folder = YcFolderInfo.model_validate_json(await self.init_yc_folder())
        c = await self.logged_yandex_cloud_cli()
        return c.with_exec(
            [
                'yc',
                'iam',
                'key',
                'create',
                '--service-account-id',
                account_info.id,
                '--folder-name',
                YC_FOLDER_NAME,
                '--output',
                '${HOME}/key.json',
            ],
            expand=True,
        ).with_(
            exec_bash(
                f"""
                        yc config profile create tofu-sa
                        yc config set service-account-key ${{HOME}}/key.json
                        yc config set cloud-id {folder.cloud_id}
                        yc config set folder-id {folder.id}
                    """,
                expand=True,
            )
        )

    @function
    async def create_yc_service_account_access_key(self) -> dagger.Secret:
        c = await self.logged_yandex_cloud_cli()
        folder = YcFolderInfo.model_validate_json(await self.init_yc_folder())
        account_info = YcServiceAccount.model_validate_json(await self.init_yc_service_account())
        key = YcServiceAccessAccountKey.model_validate_json(
            await c.with_exec(
                [
                    'yc',
                    'iam',
                    'access-key',
                    'create',
                    '--service-account-name',
                    account_info.name,
                    f'--folder-id={folder.id}',
                    '--format=json',
                ]
            ).stdout()
        )
        return dag.set_secret('service-account-key', key.model_dump_json())

    @function
    async def init_tofu_backend_storage(self) -> str:
        c = await self.logged_yandex_cloud_cli()
        folder = YcFolderInfo.model_validate_json(await self.init_yc_folder())
        buckets = pydantic.TypeAdapter(list[YcBucketInfo]).validate_json(
            await c.with_exec(['yc', 'storage', 'bucket', 'list', '--folder-id', folder.id, '--format=json']).stdout()
        )
        for b in buckets:
            if b.name == YC_TOFU_BUCKET_NAME:
                target_bucket = b
                break
        else:
            target_bucket = YcBucketInfo.model_validate_json(
                await c.with_exec(
                    [
                        'yc',
                        'storage',
                        'bucket',
                        'create',
                        f'--name={YC_TOFU_BUCKET_NAME}',
                        '--default-storage-class=Standard',
                        '--max-size=0',
                        f'--folder-id={folder.id}',
                        '--format=json',
                    ]
                ).stdout()
            )
        return target_bucket.model_dump_json()

    @function
    async def open_tofu_cli(self) -> dagger.Container:
        platform = (await dag.default_platform()).split('/')[1]
        base = tp.cast(dagger.Container, self.ubuntu_base())
        return base.with_(install_packages(['zip', 'wget'])).with_(
            exec_bash(f"""
                # https://docs.sigstore.dev/cosign/system_config/installation/#with-the-cosign-binary-or-rpmdpkg-package
                curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-{platform}"
                mv cosign-linux-{platform} /usr/local/bin/cosign
                chmod +x /usr/local/bin/cosign

                # https://opentofu.org/docs/intro/install/standalone/
                curl --proto '=https' --tlsv1.2 -fsSL https://get.opentofu.org/install-opentofu.sh -o install-opentofu.sh
                chmod +x install-opentofu.sh
                ./install-opentofu.sh --install-method standalone
                rm -f install-opentofu.sh
            """)  # noqa
        )

    @function
    async def logged_open_tofu_cli(self, open_tofu_dir: dagger.Directory) -> dagger.Container:
        logged_yc = await self.service_logged_yandex_cloud_cli()
        yc_token = json.loads(await logged_yc.with_exec(['yc', 'iam', 'create-token', '--format=json']).stdout())[
            'iam_token'
        ]
        yc_cloud_id = await logged_yc.with_exec(['yc', 'config', 'get', 'cloud-id']).stdout()
        yc_folder_id = YcFolderInfo.model_validate_json(await self.init_yc_folder()).id
        yc_tofu_bucket = YcBucketInfo.model_validate_json(await self.init_tofu_backend_storage()).name
        yc_service_key = YcServiceAccessAccountKey.model_validate_json(
            await (await self.create_yc_service_account_access_key()).plaintext()
        )
        terraform_cache = dag.cache_volume('teraform-cache')
        c = await self.open_tofu_cli()
        c = (
            c.with_(
                add_env_variables(
                    YC_TOKEN=yc_token,
                    YC_CLOUD_ID=yc_cloud_id,
                    YC_FOLDER_ID=yc_folder_id,
                    YC_ZONE=YC_ZONE,
                    YC_TOFU_BUCKET=yc_tofu_bucket,
                    ACCESS_KEY=yc_service_key.key_id,
                    SECRET_KEY=yc_service_key.secret,
                    TF_VAR_zone=YC_ZONE,
                    TF_VAR_username=HOST_USERNAME,
                    TF_VAR_host_instance_name=HOST_INSTANCE_NAME,
                    TF_VAR_factorio_image_tag=FACTORIO_IMAGE_TAG,
                )
            )
            .with_mounted_directory('${HOME}/opentofu', open_tofu_dir, expand=True)
            .with_workdir('${HOME}/opentofu', expand=True)
            .with_mounted_cache('${HOME}/opentofu/.terraform', terraform_cache, expand=True)
            .with_(
                exec_bash(
                    """
                        cd ${HOME}/opentofu
                        tofu init -reconfigure -backend-config="bucket=${YC_TOFU_BUCKET}" -backend-config="region=${YC_ZONE}" -backend-config="access_key=${ACCESS_KEY}" -backend-config="secret_key=${SECRET_KEY}"
                    """,  # noqa: E501
                    expand=True,
                )
            )
        )
        return c

    @function
    async def apply_tofu(self, open_tofu_dir: dagger.Directory):
        await (await self.logged_open_tofu_cli(open_tofu_dir=open_tofu_dir)).terminal(cmd=['tofu', 'apply']).sync()

    @function
    async def force_apply_tofu(self, open_tofu_dir: dagger.Directory):
        await (
            (await self.logged_open_tofu_cli(open_tofu_dir=open_tofu_dir))
            .with_env_variable('CACHEBUSTER', str(datetime.now()))
            .with_(
                exec_bash(
                    """
                        cd ${HOME}/opentofu
                        tofu apply -auto-approve
                    """,
                    expand=True,
                )
            )
            .sync()
        )

    @function
    async def export_ssh_keys(self, open_tofu_dir: dagger.Directory) -> dagger.Directory:
        c = await self.logged_open_tofu_cli(open_tofu_dir=open_tofu_dir)
        return c.with_(
            exec_bash(
                """
            cd ${HOME}/opentofu
            mkdir -p ${HOME}/.ssh
            tofu output -raw 'ssh_private_key' > ${HOME}/.ssh/id_rsa
            tofu output -raw 'ssh_public_key' > ${HOME}/.ssh/id_rsa.pub
            chmod 400 ${HOME}/.ssh/*
        """,
                expand=True,
            )
        ).directory('${HOME}/.ssh', expand=True)

    @function
    async def resolve_public_ip(self) -> str:
        folder = YcFolderInfo.model_validate_json(await self.init_yc_folder())
        return json.loads(
            await (await self.logged_yandex_cloud_cli())
            .with_env_variable('CACHEBUSTER', str(datetime.now()))
            .with_exec(
                [
                    'yc',
                    'compute',
                    'instance',
                    'get',
                    f'--folder-id={folder.id}',
                    f'--name={HOST_INSTANCE_NAME}',
                    '--format=json',
                ]
            )
            .stdout()
        )['network_interfaces'][0]['primary_v4_address']['one_to_one_nat']['address']

    @function
    async def ssh_container(self, open_tofu_dir: dagger.Directory) -> dagger.Container:
        ip = await self.resolve_public_ip()
        keys = await self.export_ssh_keys(open_tofu_dir=open_tofu_dir)
        return (
            self.ubuntu_base()
            .with_(install_packages(['openssh-client']))
            .with_mounted_directory('${HOME}/.ssh', keys, expand=True)
            .with_new_file(
                '${HOME}/.ssh/config',
                dedent(f"""Host factorio-server
                    HostName {ip}
                    User {HOST_USERNAME}
                """),
                expand=True,
            )
        )

    @function
    async def open_ssh(self, open_tofu_dir: dagger.Directory):
        await (
            (await self.ssh_container(open_tofu_dir=open_tofu_dir))
            .terminal(cmd=['ssh', '-o', 'StrictHostKeyChecking=no', 'factorio-server'])
            .sync()
        )

    @function
    async def upload_save(self, open_tofu_dir: dagger.Directory, save: dagger.File):
        """In case of devcontainer you need to copy save from host system to container fs
        You can do it like this (from host system):
        > CONTAINER_ID=$(docker ps --format 'table {{.ID}}\t{{.Image}}' | awk '{ if ($2~/^vsc-factorio-server.*/) print $1 }'); docker cp ${PATH_TO_SAVE} "${CONTAINER_ID}:/save.zip"
        """  # noqa: E501
        # TODO:
        # 1. Remove magic literals: 845 (factorio docker user), paths
        # 2. Think how to restart Docker (without restarting machine)
        # 3. Think how to upload saves from host machine more easily
        c = await self.ssh_container(open_tofu_dir=open_tofu_dir)
        await (
            c.with_file('/save.zip', save)
            .with_(
                exec_bash(
                    """
                        #!bash
                        scp -o StrictHostKeyChecking=no /save.zip factorio-server:/home/factorio-sre/original.zip
                        ssh -o StrictHostKeyChecking=no factorio-server <<-'ENDSSH'
                            #!/usr/bin/env bash
                            set -xeuo pipefail
                            CONTAINER_ID="$(docker ps --format "table {{.ID}}" | tail -n +2)"
                            if [ -n "$CONTAINER_ID" ]; then
                                docker container stop "$CONTAINER_ID"
                            fi
                            sudo rm -f /factorio-data/saves/*
                            sudo mv /home/factorio-sre/original.zip /factorio-data/saves
                            sudo chown -R 845:845 /factorio-data
                        ENDSSH
                    """,  # noqa: E501
                ),
            )
            .sync()
        )
        await self.command_server_machine(MachineCommand.RESTART)

    @function
    async def command_server_machine(self, command: MachineCommand):
        folder = YcFolderInfo.model_validate_json(await self.init_yc_folder())
        (
            await (await self.logged_yandex_cloud_cli())
            .with_env_variable('CACHEBUSTER', str(datetime.now()))
            .with_exec(
                ['yc', 'compute', 'instance', str(command), f'--folder-id={folder.id}', f'--name={HOST_INSTANCE_NAME}']
            )
            .sync()
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

import typing as tp
from pathlib import Path
from textwrap import dedent

import dagger


class classproperty:
    def __init__(self, func):
        self.fget = func

    def __get__(self, instance, owner):
        return self.fget(owner)


def withable(func: tp.Callable) -> tp.Callable:
    def wrapper(*args, **kwrags) -> tp.Callable:
        def impl(c: dagger.Container) -> dagger.Container:
            return func(c, *args, **kwrags)

        return impl

    return wrapper


@withable
def install_packages(
    c: dagger.Container, packages: list[str], update: bool = True, upgrade: bool = True
) -> dagger.Container:
    if update:
        c = c.with_exec(['apt-get', '-yqqo', 'Dpkg::Use-Pty=0', 'update'])
    if upgrade:
        c = c.with_exec(['apt-get', '-yqqo', 'Dpkg::Use-Pty=0', 'upgrade'])
    return c.with_exec(['apt-get', '-yqqo', 'Dpkg::Use-Pty=0', 'install'] + packages)


@withable
def add_env_variables(c: dagger.Container, **kwargs) -> dagger.Container:
    for k, v in kwargs.items():
        c = c.with_env_variable(k, str(v))
    return c


@withable
def create_user(c: dagger.Container, user_name: str, uid: int = 65533, gid: int = 65533) -> dagger.Container:
    return (
        c.with_exec(['groupadd', '-g', str(gid), '-o', user_name])
        .with_exec(['useradd', '-m', '-u', str(uid), '-g', str(gid), '-o', '-s', '/bin/bash', user_name])
        .with_(
            add_env_variables(
                USER_UID=uid,
                USER_GID=gid,
                USER_LOGIN=user_name,
            )
        )
    )


@withable
def exec_bash(
    c: dagger.Container, script: str, expand: bool = False, insecure_root_capabilities: bool = False
) -> dagger.Container:
    n = str(Path('/tmp/script.sh'))
    script = dedent("""
        set -xeuo pipefail
    """) + dedent(script)
    return c.with_new_file(n, script, permissions=0o750).with_exec(
        ['/bin/bash', '-c', n], expand=expand, insecure_root_capabilities=insecure_root_capabilities
    )


@withable
def exec_bash_and_save_exit_code(c: dagger.Container, script: str, exit_code_file: str):
    n = str(Path('/tmp/script.sh'))
    script = dedent("""
        set -xeuo pipefail
    """) + dedent(script)
    return c.with_new_file(n, script, permissions=0o750).with_exec(
        ['/bin/bash', '-c', f'{n}; echo -n $? > {exit_code_file}']
    )

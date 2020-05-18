#!/usr/bin/env python3
# encoding: utf-8

import sys
from datetime import datetime

from vyosextra import log
from vyosextra import arguments
from vyosextra.config import config

from vyosextra.entry import build as control


class Control(control.Control):
    location = 'packages'

    def make(self, where, target):
        self.ssh(where, config.docker(where, '', f'sudo make {target}'))

    def backdoor(self, where, password):
        build_repo = config.get(where, 'repo')

        lines = config.read('vyos-iso-backdoor').split('\n')
        location = lines.pop(0).lstrip().lstrip('#').strip()

        if not password:
            self.ssh("build", f"rm {build_repo}/{location}", exitonfail=False)
            self.ssh("build", f"touch {build_repo}/{location}")
            return

        data = ''.join(lines).format(user='admin', password=password)
        self.chain(config.printf(data), config.ssh(where, f'cat - > {build_repo}/{location}'))

    def configure(self, where, extra, name, release):
        email = config.get('global', 'email')

        date = datetime.now().strftime('%Y%m%d%H%M')
        name = name if name else 'rolling'
        version = f'1.3-{name}-{date}'

        configure = f"--build-by {email}"
        configure += f" --debian-mirror http://ftp.de.debian.org/debian/"
        configure += f" --version {version}"
        configure += f" --build-type release"
        if extra:
            configure += f"  --custom-package '{extra}'"

        self.ssh(where, config.docker(where, '', f'git checkout {release}'))
        self.ssh(where, config.docker(where, '', f'./configure {configure}'))


def main(target=''):
    'call vyos-build make within docker'

    options = ['server', 'package', 'make', 'presentation']
    if not target:
        options = ['target'] + options

    arg = arguments.setup(__doc__, options)

    if not target:
        target = arg.target

    control = Control(arg.dry, arg.quiet)

    if not config.exists(arg.server):
        sys.exit(f'machine "{arg.server}" is not configured')

    role = config.get(arg.server, 'role')
    if role != 'build':
        sys.exit(f'target "{arg.server}" is not a build machine')

    control.git(arg.server, 'fetch')
    control.cleanup(arg.server)

    if target == 'test':
        control.make(arg.server, 'test')
        return

    done = False
    if not arg.release:
        for package in arg.packages:
            done = control.build(arg.server, package, arg.location)

    if done:
        control.backdoor(arg.server, arg.backdoor)
    if done or arg.release:
        control.configure(arg.server, arg.extra, arg.name, arg.release or 'current')
        control.make(arg.server, target)

    if target == 'iso' and arg.test:
        control.make(arg.server, 'test')

    log.completed('iso built and tested')


if __name__ == '__main__':
    main('iso')

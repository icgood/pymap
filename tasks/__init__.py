# type: ignore

import inspect
import os
import os.path
from shlex import join

if not hasattr(inspect, 'getargspec'):
    # https://github.com/pyinvoke/invoke/issues/833
    inspect.getargspec = inspect.getfullargspec

from invoke import task, Collection

from . import check, doc, lint, test, types


@task
def clean(ctx, full=False):
    """Delete all the standard build and validate artifacts."""
    if full:
        ctx.run('git clean -dfX')
    else:
        anywhere = ['__pycache__']
        top_level = [
            '.coverage',
            '.mypy_cache',
            '.pytest_cache',
            'dist',
            'doc/build/']
        for name in anywhere:
            for path in [ctx.package, 'test']:
                subpaths = [os.path.join(subpath, name)
                            for subpath, dirs, names in os.walk(path)
                            if name in dirs or name in names]
                for subpath in subpaths:
                    ctx.run(join(['rm', '-rf', subpath]))
        for name in top_level:
            ctx.run(join(['rm', '-rf', name]))


@task
def install(ctx, dev=True, update=False):
    """Install the library and all development tools."""
    choice = 'dev' if dev else 'all'
    if update:
        ctx.run('pip install -U -r requirements-{}.txt'.format(choice))
    else:
        ctx.run('pip install -r requirements-{}.txt'.format(choice))


@task(test.all, types.all, lint.all)
def validate(ctx):
    """Run all tests, type checks, and linters."""
    pass


ns = Collection(clean, install)
ns.add_task(validate, default=True)
ns.add_collection(check)
ns.add_collection(test)
ns.add_collection(types)
ns.add_collection(lint)
ns.add_collection(doc)

ns.configure({
    'package': 'pymap',
    'run': {
        'echo': True,
        'pty': True,
    }
})

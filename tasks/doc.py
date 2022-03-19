# type: ignore

from invoke import task, Collection


@task
def install(ctx, update=False):
    """Install the tools needed to build the docs."""
    if update:
        ctx.run('pip install -U -r doc/requirements.txt')
    elif not ctx.run('which sphinx-build', hide=True, warn=True):
        ctx.run('pip install -r doc/requirements.txt')


@task(install)
def clean(ctx):
    """Clean up the doc build directory."""
    ctx.run('make -C doc clean')


@task(install)
def build(ctx):
    """Build the HTML docs."""
    ctx.run('make -C doc html')


@task(install, build)
def open(ctx):
    """Open the docs in a browser (on macOS)."""
    ctx.run('open doc/build/html/index.html')


ns = Collection(install, clean, open)
ns.add_task(build, default=True)

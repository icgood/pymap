# type: ignore

from invoke import task, Collection

from .check import check_import


@task(check_import)
def flake8(ctx):
    """Run the flake8 linter."""
    ctx.run('flake8 {} test {} *.py'.format(ctx.package, __package__))


@task(check_import)
def bandit(ctx):
    """Run the bandit linter."""
    ctx.run('bandit -c pyproject.toml -qr {}'.format(ctx.package))


@task(flake8, bandit)
def all(ctx):
    """Run all linters."""
    pass


ns = Collection(flake8, bandit)
ns.add_task(all, default=True)

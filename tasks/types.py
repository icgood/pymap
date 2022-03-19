# type: ignore

from invoke import task, Collection

from .check import check_import


@task(check_import)
def mypy(ctx):
    """Run the mypy type checker."""
    ctx.run('mypy {} test'.format(ctx.package))


@task(mypy)
def all(ctx):
    """Run all the type checker tools."""
    pass


ns = Collection(mypy)
ns.add_task(all, default=True)

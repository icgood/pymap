# type: ignore

from invoke import task, Collection

from .check import check_import


@task(check_import)
def pytest(ctx):
    """Run the unit tests with py.test."""
    ctx.run('py.test --cov={} --cov-report=term-missing'.format(ctx.package))


@task(pytest)
def all(ctx):
    """Run all test utilities."""
    pass


ns = Collection(pytest)
ns.add_task(all, default=True)

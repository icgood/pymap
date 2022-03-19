# type: ignore

import warnings

from invoke import task, Collection


@task
def check_import(ctx):
    """Check that the library can be imported."""
    try:
        __import__(ctx.package)
    except Exception:
        warnings.warn('Could not import {!r}, '
                      'task may fail'.format(ctx.package))


ns = Collection()
ns.add_task(check_import, default=True)

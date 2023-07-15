# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))

from importlib.metadata import distribution

import cloud_sptheme as csp  # type: ignore


# -- Project information -----------------------------------------------------

project = 'pymap'
copyright = '2022, Ian Good'
author = 'Ian Good'

# The short X.Y version
project_version = distribution(project).version
version_parts = project_version.split('.')
version = '.'.join(version_parts[0:2])
# The full version, including alpha/beta/rc tags
release = project_version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.githubpages',
    'sphinx.ext.viewcode',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []  # type: ignore


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'cloud'

# set the theme path to point to cloud's theme data
html_theme_path = [csp.get_theme_dir()]

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
if csp.is_cloud_theme(html_theme):
    html_theme_options = {
        'borderless_decor': True,
        'sidebarwidth': '3in',
        'hyphenation_language': 'en',
    }

# -- Extension configuration -------------------------------------------------

autodoc_member_order = 'bysource'
autodoc_default_flags = ['show-inheritance']
autodoc_typehints = 'description'
autodoc_typehints_format = 'short'
napoleon_numpy_docstring = False

# -- Options for intersphinx extension ---------------------------------------

intersphinx_mapping = {'python': ('https://docs.python.org/3/', None),
                       'pymap-admin': ('https://icgood.github.io/pymap-admin/', None),
                       'pysasl': ('https://icgood.github.io/pysasl/', None),
                       'swim-protocol': ('https://icgood.github.io/swim-protocol/', None),
                       'grpclib': ('https://grpclib.readthedocs.io/en/latest/', None),
                       'pymacaroons': ('https://pymacaroons.readthedocs.io/en/latest/', None)}

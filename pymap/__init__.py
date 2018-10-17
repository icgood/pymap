# Declares pymap to be a namespace package. This file should be copied into
# all other projects that use the namespace.

__import__('pkg_resources').declare_namespace(__name__)


from __future__ import annotations

from grpclib.const import Status
from grpclib.exceptions import GRPCError
from google.rpc.error_details_pb2 import ErrorInfo

__all__ = ['get_unimplemented_error', 'get_incompatible_version_error']


def get_unimplemented_error(*, domain: str = None, **metadata: str) \
        -> GRPCError:
    """Build a :exc:`~grpclib.exceptions.GRPCError` exception for an
    operation that is not implemented by the server.

    Args:
        domain: The domain string to include in the error.
        metadata: Additional metadata to include in the error.

    """
    return GRPCError(Status.UNIMPLEMENTED, 'Operation not available', [
        ErrorInfo(reason='UNIMPLEMENTED', domain=domain, metadata=metadata)])


def get_incompatible_version_error(client_version: str, server_version: str, *,
                                   domain: str = None, **metadata: str) \
        -> GRPCError:
    """Build a :exc:`~grpclib.exceptions.GRPCError` exception for an
    incompatible version error.

    Args:
        client_version: The client version string.
        server_version: The server version string.
        domain: The domain string to include in the error.
        metadata: Additional metadata to include in the error.

    """
    metadata = {'client_version': client_version,
                'server_version': server_version,
                **metadata}
    return GRPCError(Status.FAILED_PRECONDITION, 'Incompatible version', [
        ErrorInfo(reason='INCOMPATIBLE', domain=domain, metadata=metadata)])

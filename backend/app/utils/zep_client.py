"""Zep client helpers for company TLS environments."""

import ssl

import httpx
import truststore
from zep_cloud.client import Zep


def create_zep_client(api_key: str, timeout: float = 20.0) -> Zep:
    """Create a Zep client using the OS certificate store for TLS."""
    ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    httpx_client = httpx.Client(verify=ssl_context, timeout=timeout)
    return Zep(api_key=api_key, httpx_client=httpx_client)

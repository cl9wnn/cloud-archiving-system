"""Download public HTTP(S) files without forwarding cloud credentials."""

import http.client
import ipaddress
import socket
import ssl
from contextlib import contextmanager
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

TIMEOUT = 30
REDIRECTS = {301, 302, 303, 307, 308}


def connect_public(host, port):
    last_error = None
    for _, _, _, _, address in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        ip = ipaddress.ip_address(address[0])
        if ip.is_global and not ip.is_multicast and not ip.is_reserved:
            try:
                return socket.create_connection((str(ip), port), timeout=TIMEOUT)
            except OSError as error:
                last_error = error
    if last_error is not None:
        raise last_error
    raise ValueError("The source must have a public IP address")


@contextmanager
def source_response(url):
    for _ in range(6):
        parts = urlsplit(url)
        if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username is not None:
            raise ValueError("Expected a public HTTP(S) URL without credentials")
        host = parts.hostname.encode("idna").decode("ascii")
        port = parts.port or (443 if parts.scheme == "https" else 80)
        # Connect to the checked address, preserving the hostname for TLS and Host.
        conn = http.client.HTTPConnection(host, port, timeout=TIMEOUT)
        try:
            conn.sock = connect_public(host, port)
            if parts.scheme == "https":
                conn.sock = ssl.create_default_context().wrap_socket(conn.sock, server_hostname=host)
            target = urlunsplit(("", "", parts.path or "/", parts.query, ""))
            authority = f"[{host}]" if ":" in host else host
            if parts.port is not None:
                authority += f":{port}"
            conn.request("GET", quote(target, safe="/%?:@!$&'()*+,;=-._~"),
                         headers={"Host": authority, "Accept-Encoding": "identity"})
            with conn.getresponse() as response:
                location = response.getheader("Location")
                if response.status in REDIRECTS and location:
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise RuntimeError(f"Source returned HTTP {response.status}")
                yield response
                return
        finally:
            conn.close()
    raise ValueError("Too many source redirects")

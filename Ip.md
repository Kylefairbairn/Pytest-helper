# Discovering a DHCP\-Assigned IPv4 Address in Python

This example finds a development board’s IPv4 address after DHCP completes, even when the interface name and assigned address are unknown\. It does not require internet access\.

## Requirements

- Linux\-based development board
- Python 3
- An interface with an IPv4 address assigned by DHCP or static configuration
- No third\-party Python packages

The implementation uses `socket.if_nameindex()` to discover the interfaces and Linux `ioctl` calls to inspect them\.

## Implementation

Save this as `network_address.py`:

```python
import fcntl
import ipaddress
import socket
import struct


SIOCGIFADDR = 0x8915
SIOCGIFFLAGS = 0x8913

IFF_UP = 0x1
IFF_LOOPBACK = 0x8


def get_ipv4_addresses() -> list[tuple[str, str]]:
    """Return active, non-loopback IPv4 interface/address pairs."""
    addresses = []

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for _, interface in socket.if_nameindex():
            request = struct.pack("256s", interface[:15].encode())

            try:
                flags_response = fcntl.ioctl(
                    sock.fileno(), SIOCGIFFLAGS, request
                )
                flags = struct.unpack("H", flags_response[16:18])[0]

                if not flags & IFF_UP or flags & IFF_LOOPBACK:
                    continue

                address_response = fcntl.ioctl(
                    sock.fileno(), SIOCGIFADDR, request
                )
                address = socket.inet_ntoa(address_response[20:24])

                # Ignore automatic link-local addresses.
                if address.startswith("169.254."):
                    continue

                addresses.append((interface, address))

            except OSError:
                # The interface is unsupported or has no IPv4 address.
                continue

    return addresses


def get_ip_on_network(network: str) -> str:
    """Return the board's only IPv4 address within the given subnet."""
    expected_network = ipaddress.ip_network(network, strict=False)

    matches = [
        address
        for _, address in get_ipv4_addresses()
        if ipaddress.ip_address(address) in expected_network
    ]

    if not matches:
        raise RuntimeError(f"No IPv4 address found on {expected_network}")

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple IPv4 addresses found on {expected_network}: {matches}"
        )

    return matches[0]


if __name__ == "__main__":
    addresses = get_ipv4_addresses()

    if not addresses:
        print("No active non-loopback IPv4 addresses found")
    else:
        for interface, address in addresses:
            print(f"{interface}: {address}")

    # Example for an isolated 10.0.0.0/24 development network:
    try:
        board_ip = get_ip_on_network("10.0.0.0/24")
        print(f"Selected board IP: {board_ip}")
    except RuntimeError as error:
        print(error)
```

## Run it

```bash
python3 network_address.py
```

Example output:

```text
eth1: 10.0.0.218
Selected board IP: 10.0.0.218
```

## Why subnet filtering matters

A board may have several active interfaces, including Ethernet, Wi\-Fi, Docker bridges, or virtual interfaces\. Selecting the first address is therefore unreliable\. If the application expects the isolated `10.0.0.0/24` network, `get_ip_on_network()` selects the address belonging to that subnet and reports an error when the result is missing or ambiguous\.

## Waiting for DHCP

An application may start before DHCP has assigned an address\. The following helper waits for the expected address instead of failing immediately:

```python
import time


def wait_for_ip(network: str, timeout_seconds: float = 30.0) -> str:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        try:
            return get_ip_on_network(network)
        except RuntimeError:
            time.sleep(0.5)

    raise TimeoutError(
        f"No usable IPv4 address appeared on {network} "
        f"within {timeout_seconds} seconds"
    )


board_ip = wait_for_ip("10.0.0.0/24")
print(board_ip)
```

## Notes

- No internet connection is required\.
- This solution is Linux\-specific because `fcntl.ioctl` is used\.
- `socket.gethostbyname(socket.gethostname())` is not recommended because embedded systems commonly resolve their hostname to `127.0.0.1`\.
- If the expected subnet is unknown, call `get_ipv4_addresses()` and let the application or configuration choose from the returned interface/address pairs\.
- An address beginning with `169.254` is link\-local and normally indicates that DHCP did not provide an address\.

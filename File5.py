from pathlib import Path

import pytest

from .capture import CaptureConfig, TsharkCapture
from .profiles import CaptureProfile


def pytest_addoption(parser):
    group = parser.getgroup("traffic capture")
    group.addoption("--capture-interface", help="Interface visible to tshark")
    group.addoption(
        "--capture-profile",
        choices=[profile.value for profile in CaptureProfile],
        default=CaptureProfile.ALL.value,
    )
    group.addoption("--capture-artifacts", default="artifacts/pcaps")


@pytest.fixture
def traffic_capture(request):
    interface = request.config.getoption("--capture-interface")
    if not interface:
        pytest.skip("--capture-interface was not supplied")

    capture = TsharkCapture(
        CaptureConfig(
            interface=interface,
            profile=CaptureProfile(request.config.getoption("--capture-profile")),
        )
    )
    capture.start()
    yield capture
    capture.stop()
    safe_nodeid = request.node.nodeid.replace("/", "_").replace("::", "__")
    destination = Path(request.config.getoption("--capture-artifacts")) / f"{safe_nodeid}.pcapng"
    capture.save_pcap(destination)

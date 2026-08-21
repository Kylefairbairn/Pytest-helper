from enum import StrEnum


class CaptureProfile(StrEnum):
    ALL = "all"
    MULTICAST = "multicast"
    MULTICAST_RTP = "multicast_rtp"


def build_capture_filter(
    profile: CaptureProfile | str,
    *,
    rtp_port_range: tuple[int, int] | None = None,
) -> str | None:
    """Return a libpcap/BPF capture filter, evaluated before packets are saved.

    RTP has no fixed port. Without a configured port range, MULTICAST_RTP keeps
    multicast UDP packets; Wireshark can then decode them as RTP heuristically
    or through Decode As. Supplying the system's RTP port range is tighter.
    """
    selected = CaptureProfile(profile)
    multicast = "(ip multicast or ip6 multicast)"

    if selected is CaptureProfile.ALL:
        return None
    if selected is CaptureProfile.MULTICAST:
        return multicast
    if rtp_port_range is None:
        return f"{multicast} and udp"

    low, high = rtp_port_range
    if not 1 <= low <= high <= 65535:
        raise ValueError("RTP port range must satisfy 1 <= low <= high <= 65535")
    return f"{multicast} and udp portrange {low}-{high}"

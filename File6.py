
@dataclass(frozen=True, slots=True)
class RtpPacket:
    frame_number: int
    source_ip: str
    source_port: int
    destination_ip: str
    destination_port: int
    ssrc: str
    payload_type: int
    sequence_number: int
    timestamp: int


@dataclass(frozen=True, slots=True)
class RtpVerification:
    pcap: Path
    packets: tuple[RtpPacket, ...]

    @property
    def is_rtp(self) -> bool:
        return bool(self.packets)

    @property
    def packet_count(self) -> int:
        return len(self.packets)


def verify_rtp(
    pcap: str | Path,
    *,
    udp_port: int | None = None,
    display_filter: str | None = None,
    tshark_path: str = "tshark",
) -> RtpVerification:
    """Use tshark's RTP dissector to find and describe RTP packets.

    Pass ``udp_port`` when signaling is absent from the capture or Wireshark
    does not otherwise recognize the UDP stream as RTP. This applies Decode As
    before evaluating the ``rtp`` display filter.
    """
    capture_path = Path(pcap)
    if not capture_path.is_file():
        raise CaptureError(f"pcap does not exist: {capture_path}")
    if udp_port is not None and not 1 <= udp_port <= 65535:
        raise ValueError("udp_port must be between 1 and 65535")

    executable = shutil.which(tshark_path)
    if executable is None:
        raise CaptureError(f"tshark executable not found: {tshark_path}")

    packet_filter = "rtp"
    if display_filter:
        packet_filter = f"rtp and ({display_filter})"

    command = [executable, "-n", "-r", str(capture_path)]
    if udp_port is not None:
        command.extend(["-d", f"udp.port=={udp_port},rtp"])
    command.extend(
        [
            "-Y", packet_filter,
            "-T", "fields",
            "-E", "separator=\t",
            "-E", "occurrence=f",
            "-e", "frame.number",
            "-e", "ip.src",
            "-e", "ipv6.src",
            "-e", "udp.srcport",
            "-e", "ip.dst",
            "-e", "ipv6.dst",
            "-e", "udp.dstport",
            "-e", "rtp.ssrc",
            "-e", "rtp.p_type",
            "-e", "rtp.seq",
            "-e", "rtp.timestamp",
        ]
    )

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise CaptureError(f"tshark RTP analysis failed: {completed.stderr.strip()}")

    packets: list[RtpPacket] = []
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 11:
            continue
        frame, ip4_src, ip6_src, src_port, ip4_dst, ip6_dst, dst_port, ssrc, payload, sequence, timestamp = fields
        try:
            packets.append(
                RtpPacket(
                    frame_number=int(frame),
                    source_ip=ip4_src or ip6_src,
                    source_port=int(src_port),
                    destination_ip=ip4_dst or ip6_dst,
                    destination_port=int(dst_port),
                    ssrc=ssrc,
                    payload_type=int(payload),
                    sequence_number=int(sequence),
                    timestamp=int(timestamp),
                )
            )
        except ValueError as error:
            raise CaptureError(f"unexpected tshark RTP field output: {line!r}") from error

    return RtpVerification(pcap=capture_path, packets=tuple(packets))


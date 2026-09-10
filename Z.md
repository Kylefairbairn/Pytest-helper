# Multicast Troubleshooting Across an L2VPN

This guide diagnoses multicast audio that must travel from an isolated cloud network, across a Layer\-2 VPN, through a bare\-metal host and physical switch, to a DAVE board\.

Unicast ping working does **not** prove multicast will work\. Ping verifies IP unicast reachability\. Multicast also depends on Layer\-2 flooding, IGMP membership, snooping/querier state, multicast routing boundaries, application interface selection, and firewall rules\.

## Topology

Replace the names below with the real host and interface names\.

```text
Audio source VM
    |
Cloud virtual network / switch
    |
Cloud-side L2VPN endpoint or bridge
    |
L2VPN
    |
Bare-metal L2VPN endpoint / Linux bridge
    |
Physical Ethernet interface
    |
Physical switch
    |
DAVE board
```

Two systems having addresses in the same IP subnet does not guarantee they are in the same Ethernet broadcast domain\. A routed overlay, proxy ARP, or gateway can make unicast work while multicast fails\.

## Test values

Examples in this guide use:

```text
Multicast group: 239.10.10.10
UDP port:       5004
```

Set values matching the audio application:

```bash
MCAST_GROUP=239.10.10.10
MCAST_PORT=5004
```

Run commands with explicit interface names whenever possible\. Capturing on `any` is useful for discovery, but it does not prove which interface received or transmitted a packet\.

## 1\. Verify that the sender transmits multicast

On the source VM:

```bash
ip -br address
ip route get "$MCAST_GROUP"
ip maddr show
sudo tcpdump -ni any "dst host $MCAST_GROUP and udp port $MCAST_PORT"
```

Expected result: UDP packets destined for the multicast group and port appear while audio is playing\.

If no packets appear:

- Confirm the application is sending to the intended group and UDP port\.
- Configure the application to use the intended output interface/address\.
- Check whether the application is binding to another NIC\.
- Use an administratively scoped group in `239.0.0.0/8`\.
- Set multicast TTL to `16` temporarily\. TTL greater than one is required if any part of the path is routed\.

For a multi\-interface Linux sender, a temporary route can force the intended interface:

```bash
sudo ip route replace 239.0.0.0/8 dev <source-interface>
```

Remove or replace this test route after determining the correct permanent network configuration\.

## 2\. Verify that the DAVE board joins the multicast group

Start a capture on the board, then start its multicast receiver:

```bash
tcpdump -eni <board-interface> igmp
```

Also inspect memberships when Linux is running:

```bash
ip maddr show dev <board-interface>
cat /proc/net/igmp
```

Expected result: an IGMP membership report for the audio multicast group\.

If no membership report appears:

- Confirm the receiving application actually joins the group\.
- Confirm it joins on the board’s physical Ethernet interface, not loopback or another NIC\.
- Confirm the group address configured on the receiver matches the sender\.
- Start the packet capture before starting the receiver\.
- Check whether the current board environment supports the required multicast operation\.

## 3\. Follow the audio packet hop by hop

Keep audio playing and capture at every boundary\. Use the same filter everywhere:

```bash
sudo tcpdump -eni <interface> "dst host $MCAST_GROUP and udp port $MCAST_PORT"
```

Capture in this order:

1. Source VM output interface
2. Cloud virtual\-switch or bridge port
3. Cloud\-side L2VPN interface
4. Bare\-metal L2VPN interface
5. Bare\-metal Linux bridge
6. Bare\-metal physical interface connected to the switch
7. DAVE board interface

On the bare\-metal host, run simultaneous captures in separate terminals:

```bash
sudo tcpdump -eni <l2vpn-interface> "dst host $MCAST_GROUP and udp port $MCAST_PORT"
```

```bash
sudo tcpdump -eni <physical-interface> "dst host $MCAST_GROUP and udp port $MCAST_PORT"
```

Interpretation:

|Observation                                                 |Likely fault                                                      |
|------------------------------------------------------------|------------------------------------------------------------------|
|Missing on the source VM                                    |Application, route, or output-interface selection                 |
|Present before L2VPN but absent after it                    |L2VPN multicast/flooding configuration                            |
|Present on bare-metal L2VPN port but absent on physical port|Linux bridge, VLAN, IGMP snooping, or firewall                    |
|Present on physical port but absent at board                |Physical switch snooping/VLAN configuration or cabling/port path  |
|Present at board but application receives nothing           |Board socket binding, group membership, port, or application issue|

Save evidence when needed:

```bash
sudo tcpdump -eni <interface> -w multicast-test.pcap \
  "igmp or (host $MCAST_GROUP and udp port $MCAST_PORT)"
```

## 4\. Trace IGMP in both directions

IGMP snooping devices learn which ports want each multicast group\. Capture IGMP on every bridge boundary:

```bash
sudo tcpdump -eni <interface> igmp
```

Look for:

- Membership Query: normally sent by the IGMP querier\.
- Membership Report: sent by the receiver when it joins a group\.
- Leave Group: sent when a receiver leaves, depending on IGMP version\.

The DAVE board’s membership report should be visible on the physical side and should propagate far enough toward the multicast source for every snooping device to learn the path\.

If membership reports are visible near the board but disappear at a bridge or L2VPN boundary, investigate that boundary first\.

## 5\. Inspect Linux bridge multicast state

Run on each Linux bridge endpoint:

```bash
ip -br link
bridge link
bridge vlan show
bridge mdb show
ip -d link show type bridge
```

Check:

- All required ports are members of the intended bridge\.
- Ports have the intended VLAN membership and PVID\.
- The multicast database contains the audio group and expected receiver\-facing port\.
- `mcast_snooping` and `mcast_querier` have appropriate values\.

Inspect a particular bridge:

```bash
ip -d link show dev <bridge-name>
bridge mdb show dev <bridge-name>
```

### Temporary snooping test

Temporarily disable multicast snooping on the specific test bridge:

```bash
sudo ip link set dev <bridge-name> type bridge mcast_snooping 0
```

Replay the audio\. If multicast now reaches the board, the problem is probably missing IGMP state or a missing querier\.

Restore snooping after the test:

```bash
sudo ip link set dev <bridge-name> type bridge mcast_snooping 1
```

Where appropriate, test Linux bridge querier operation:

```bash
sudo ip link set dev <bridge-name> type bridge mcast_querier 1
```

Do not permanently introduce multiple uncontrolled queriers\. Decide which device should be the querier based on the complete Layer\-2 topology\.

## 6\. Determine whether the network is truly Layer 2 end to end

On the source\-side systems, inspect the neighbor entry for the board:

```bash
ip neigh show <board-ip>
```

Clear only that neighbor entry if a fresh test is needed:

```bash
sudo ip neigh del <board-ip> dev <source-interface>
```

Then capture ARP while pinging:

```bash
sudo tcpdump -eni <source-interface> arp
ping -c 3 <board-ip>
```

Repeat the ARP capture on both sides of the L2VPN\.

Expected for a transparent Layer\-2 domain:

- The source broadcasts an ARP request for the board\.
- That request crosses the L2VPN\.
- The board replies with its own MAC address\.

Warning signs:

- A gateway or overlay endpoint answers ARP on behalf of the board\.
- The ARP request never crosses the L2VPN\.
- The learned MAC address belongs to a router instead of the board\.

These indicate routing, proxy ARP, or Layer\-2 termination\. Multicast will then require multicast routing or explicit replication rather than ordinary Ethernet bridging\.

## 7\. Check MAC learning and VLAN handling

On each Linux bridge:

```bash
bridge fdb show br <bridge-name>
bridge vlan show
```

Confirm the board’s source MAC is learned on the physical\-switch\-facing port\. Confirm the source VM’s MAC, or the expected remote MAC, is learned on the L2VPN\-facing port\.

Even if the L2VPN reduces the need for VLAN tagging, check for accidental VLAN filtering:

```bash
ip -d link show dev <bridge-name>
```

If `vlan_filtering 1` is enabled, every bridge port must have correct VLAN membership\. Untagged frames must enter with the intended PVID and leave untagged where required\.

## 8\. Check firewalls

Inspect rather than immediately flushing rules:

```bash
sudo nft list ruleset
sudo iptables -S
sudo iptables -t raw -S
sudo iptables -t mangle -S
sudo iptables -t nat -S
```

Look for drops involving:

- Destination `224.0.0.0/4`
- The multicast group
- The UDP port
- IGMP, IP protocol number 2
- Forwarded or bridged packets

If bridge netfilter is active, bridged frames may pass through firewall hooks:

```bash
sysctl net.bridge.bridge-nf-call-iptables 2>/dev/null
sysctl net.bridge.bridge-nf-call-ip6tables 2>/dev/null
```

Do not flush production firewall rules as a diagnostic shortcut\. Add narrow temporary logging or allow rules only according to the system’s firewall policy\.

## 9\. Test with a simple multicast sender and receiver

This separates the audio application from the network\.

### Receiver

If `socat` is available on the receiving Linux system:

```bash
socat -u UDP4-RECVFROM:$MCAST_PORT,ip-add-membership=$MCAST_GROUP:<receiver-interface-ip>,reuseaddr -
```

### Sender

```bash
while true; do
  printf 'multicast test %s\n' "$(date -Iseconds)"
  sleep 1
done | socat -u - UDP4-DATAGRAM:$MCAST_GROUP:$MCAST_PORT,ip-multicast-if=<sender-interface-ip>,ip-multicast-ttl=16
```

Run packet captures during this test\. If the simple stream works but audio does not, inspect the audio application’s socket binding, group, port, TTL, and interface selection\.

## 10\. Physical switch checks

Inspect the switch configuration and status for:

- IGMP snooping enabled or disabled
- Active IGMP querier and querier VLAN
- Multicast group/MDB membership
- Port VLAN membership and PVID
- Storm\-control or multicast rate limiting
- Port isolation/private VLAN behavior
- Static multicast forwarding entries

For a short diagnostic test, disable IGMP snooping only on the isolated test VLAN, if operational policy allows it\. If the stream starts working, restore snooping and fix the querier or group\-membership propagation\.

## Recommended troubleshooting order

1. Confirm multicast packets leave the source VM\.
2. Confirm the board sends an IGMP membership report\.
3. Capture audio and IGMP on both sides of the L2VPN\.
4. Capture on both sides of the bare\-metal Linux bridge\.
5. Inspect `bridge mdb show` and multicast\-snooping state\.
6. Temporarily disable bridge snooping as a controlled test\.
7. Verify ARP crosses the L2VPN and no proxy answers for the board\.
8. Verify bridge VLANs and MAC learning\.
9. Inspect firewalls and bridge\-netfilter behavior\.
10. Inspect physical\-switch IGMP, VLAN, isolation, and rate\-limit settings\.
11. Reproduce with a simple `socat` multicast stream\.

## Most likely cause

The leading suspect is IGMP snooping without a working querier or without the DAVE board’s membership report propagating across the entire L2VPN path\. A close second is that the network provides unicast reachability between same\-subnet addresses without being a transparent Layer\-2 domain\.

Do not change several controls simultaneously\. Make one temporary change, replay the stream, capture the result, and restore the original setting before moving to the next test\.

## Evidence collection template

Record the following so the failure can be narrowed down without guessing:

```text
Source VM IP/interface:
Multicast group/port:
Multicast TTL:
Cloud bridge name and ports:
Cloud L2VPN interface:
Bare-metal L2VPN interface:
Bare-metal bridge name and ports:
Bare-metal physical interface:
Physical switch model/VLAN:
DAVE board IP/interface:

Audio visible on source interface:        yes/no
Audio visible entering L2VPN:              yes/no
Audio visible leaving L2VPN:               yes/no
Audio visible on bare-metal physical NIC:  yes/no
Audio visible on DAVE board:                yes/no
Board IGMP report visible locally:          yes/no
Board IGMP report visible across L2VPN:     yes/no
Bridge MDB includes group/receiver port:    yes/no
Works with bridge snooping disabled:        yes/no
ARP is answered by board's actual MAC:      yes/no
```

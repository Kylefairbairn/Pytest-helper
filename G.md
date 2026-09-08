TI U-Boot: TFTP and NFS-Root Boot Across an L2VPN

This guide boots a TI ARM board using:

• TFTP to load the Linux kernel and Device Tree into RAM
• NFS to provide the Linux root filesystem
• A reduced TFTP block size when an L2VPN cannot carry full-size frames

No initramfs or local root filesystem is required. The commands below do not
write to flash unless you explicitly run saveenv.

Example Network

|Device         |Address          |
|---------------|-----------------|
|Target board   |`192.168.50.20`  |
|TFTP/NFS server|`192.168.50.10`  |
|Netmask        |`255.255.255.0`  |
|NFS export     |`/srv/nfs/rootfs`|
|Device Tree    |`k3-am625-sk.dtb`|

Replace these values with the addresses, paths, and Device Tree for your
environment.

Boot Flow

```text
U-Boot
  -> configure the board network
  -> download the kernel with TFTP
  -> download the Device Tree with TFTP
  -> start the Linux kernel
  -> Linux initializes its network driver
  -> Linux mounts the root filesystem over NFS
  -> Linux executes /sbin/init
```

L2VPN MTU Considerations

An L2VPN adds encapsulation around the customer’s Ethernet frame. Depending on
the implementation, this can include VLAN tags, MPLS labels, a pseudowire
control word, VXLAN headers, GRE, or IPsec overhead.

If the underlay MTU was not increased to accommodate that overhead, large
customer frames may be fragmented or silently discarded. TFTP exposes this
problem because it uses UDP and U-Boot has limited path-MTU recovery.

For IPv4 on a normal 1500-byte network, the largest TFTP data block that fits
without IP fragmentation is:

```text
1500-byte IP MTU
- 20-byte IPv4 header
-  8-byte UDP header
-  4-byte TFTP header
= 1468-byte TFTP data block
```

That calculation applies to the customer packet. The L2VPN underlay must still
carry the complete customer Ethernet frame plus the tunnel overhead.

If reducing the TFTP block size allows the transfer to progress, treat that as
strong evidence of an MTU or fragmentation problem.

Verify the TFTP and NFS Server

The TFTP directory must contain the kernel and Device Tree:

```bash
ls -lh /srv/tftp/Image
ls -lh /srv/tftp/k3-am625-sk.dtb
```

The exported NFS root should contain a complete Linux filesystem:

```text
/srv/nfs/rootfs/
  bin/
  dev/
  etc/
  lib/
  proc/
  run/
  sbin/
  sys/
  tmp/
  usr/
  var/
```

Verify that init exists and is executable:

```bash
ls -l /srv/nfs/rootfs/sbin/init
file /srv/nfs/rootfs/sbin/init
```

If /sbin/init is a symbolic link, verify its destination:

```bash
readlink -f /srv/nfs/rootfs/sbin/init
ls -l "$(readlink -f /srv/nfs/rootfs/sbin/init)"
```

Verify the NFS export:

```bash
sudo exportfs -v
showmount -e localhost
```

Example /etc/exports entry:

```text
/srv/nfs/rootfs 192.168.50.0/24(rw,sync,no_subtree_check,no_root_squash)
```

After changing /etc/exports, reload it:

```bash
sudo exportfs -ra
```

Determine Safe U-Boot RAM Addresses

Inspect the addresses supplied by the board’s U-Boot configuration:

```bash
printenv loadaddr
printenv fdtaddr
printenv kernel_addr_r
printenv fdt_addr_r
```

Prefer kernel_addr_r and fdt_addr_r when they are defined. Do not invent RAM
addresses without checking the board’s memory map.

The examples below use:

```bash
setenv kernel_addr ${kernel_addr_r}
setenv dtb_addr ${fdt_addr_r}
```

If those variables are unavailable but loadaddr and fdtaddr are valid for
the board, use:

```bash
setenv kernel_addr ${loadaddr}
setenv dtb_addr ${fdtaddr}
```

Manual Boot from the U-Boot Prompt

1. Configure the network

```bash
setenv ipaddr 192.168.50.20
setenv serverip 192.168.50.10
setenv netmask 255.255.255.0
setenv autoload no
```

Verify basic connectivity:

```bash
ping ${serverip}
```

A successful ping proves basic reachability, but it does not prove that
full-size frames can cross the L2VPN.

2. Reduce the TFTP block size

Start with 1024 bytes:

```bash
setenv tftpblocksize 1024
```

If transfers still stall or repeatedly time out, use the standard 512-byte
block size:

```bash
setenv tftpblocksize 512
```

Do not run saveenv while testing. The setting will remain temporary.

3. Select the load addresses

```bash
setenv kernel_addr ${kernel_addr_r}
setenv dtb_addr ${fdt_addr_r}
```

4. Download the Device Tree

```bash
tftp ${dtb_addr} k3-am625-sk.dtb
```

Validate it:

```bash
fdt addr ${dtb_addr}
fdt header
```

5. Download the kernel

For ARM64:

```bash
tftp ${kernel_addr} Image
```

For ARM32, use the appropriate zImage instead:

```bash
tftp ${kernel_addr} zImage
```

6. Configure the NFS-root kernel arguments

Static IPv4 configuration with NFSv3 over TCP:

```bash
setenv bootargs "console=${console} root=/dev/nfs rw ip=192.168.50.20:192.168.50.10::255.255.255.0::eth0:off nfsroot=192.168.50.10:/srv/nfs/rootfs,v3,tcp"
```

The ip= fields are:

```text
ip=<client-ip>:<server-ip>:<gateway-ip>:<netmask>:<hostname>:<device>:<autoconf>
```

If a gateway is required, include it between the server address and netmask:

```bash
setenv bootargs "console=${console} root=/dev/nfs rw ip=192.168.50.20:192.168.50.10:192.168.50.1:255.255.255.0::eth0:off nfsroot=192.168.50.10:/srv/nfs/rootfs,v3,tcp"
```

DHCP alternative:

```bash
setenv bootargs "console=${console} root=/dev/nfs rw ip=dhcp nfsroot=192.168.50.10:/srv/nfs/rootfs,v3,tcp"
```

Do not include rdinit=/init; no initramfs is being used.

7. Start Linux

ARM64:

```bash
booti ${kernel_addr} - ${dtb_addr}
```

ARM32:

```bash
bootz ${kernel_addr} - ${dtb_addr}
```

The dash means that no initramfs is supplied.

Copy-and-Paste ARM64 Boot Sequence

Run each line separately the first time so a failed command does not get hidden
by the following commands:

```bash
setenv ipaddr 192.168.50.20
setenv serverip 192.168.50.10
setenv netmask 255.255.255.0
setenv autoload no
setenv tftpblocksize 1024
setenv kernel_addr ${kernel_addr_r}
setenv dtb_addr ${fdt_addr_r}
ping ${serverip}
tftp ${dtb_addr} k3-am625-sk.dtb
fdt addr ${dtb_addr}
fdt header
tftp ${kernel_addr} Image
setenv bootargs "console=${console} root=/dev/nfs rw ip=192.168.50.20:192.168.50.10::255.255.255.0::eth0:off nfsroot=192.168.50.10:/srv/nfs/rootfs,v3,tcp"
booti ${kernel_addr} - ${dtb_addr}
```

If 1024-byte TFTP blocks fail, repeat the downloads after running:

```bash
setenv tftpblocksize 512
```

Example uEnv.txt

Test the manual sequence successfully before automating it.

```text
ipaddr=192.168.50.20
serverip=192.168.50.10
netmask=255.255.255.0
autoload=no
tftpblocksize=1024

kernel_file=Image
fdt_file=k3-am625-sk.dtb

set_addresses=setenv kernel_addr ${kernel_addr_r}; setenv dtb_addr ${fdt_addr_r}
tftp_kernel=tftp ${kernel_addr} ${kernel_file}
tftp_fdt=tftp ${dtb_addr} ${fdt_file}
set_nfs_args=setenv bootargs console=${console} root=/dev/nfs rw ip=192.168.50.20:192.168.50.10::255.255.255.0::eth0:off nfsroot=192.168.50.10:/srv/nfs/rootfs,v3,tcp
nfs_boot=run set_addresses; run tftp_fdt; run tftp_kernel; run set_nfs_args; booti ${kernel_addr} - ${dtb_addr}
uenvcmd=run nfs_boot
```

If kernel_addr_r or fdt_addr_r is not defined on the board, replace those
references with verified loadaddr and fdtaddr values.

Confirm the L2VPN Path MTU

Use Linux hosts on opposite sides of the L2VPN. Do not rely only on a normal
ping, because a small ICMP packet can succeed while large packets fail.

For IPv4, test a complete 1500-byte IP packet:

```bash
ping -M do -s 1472 <remote-ip>
```

The size is calculated as:

```text
1472 bytes ICMP data + 8 bytes ICMP header + 20 bytes IPv4 header = 1500
```

Reduce the payload until it succeeds:

```bash
ping -M do -s 1464 <remote-ip>
ping -M do -s 1400 <remote-ip>
ping -M do -s 1300 <remote-ip>
ping -M do -s 1200 <remote-ip>
```

The approximate IPv4 path MTU is the largest successful payload plus 28 bytes.
For example, a largest successful -s 1400 test indicates an MTU of
approximately 1428 bytes.

Run the test in both directions. An asymmetric result can indicate different
MTUs or filtering on the two L2VPN paths.

Capture the TFTP Failure

Capture traffic simultaneously on both sides of the L2VPN:

```bash
sudo tcpdump -ni <interface> -s0 -w tftp-side-a.pcap udp
```

```bash
sudo tcpdump -ni <interface> -s0 -w tftp-side-b.pcap udp
```

Check for:

• A TFTP DATA block visible at the ingress but missing at the egress
• Repeated DATA blocks or acknowledgements
• IP fragments
• An OACK response negotiating an unexpectedly large block size
• Packets larger than the discovered path MTU
• Only UDP port 69 being allowed by a firewall

TFTP uses UDP port 69 for the initial request, then switches to negotiated UDP
ports for the actual transfer. A firewall must allow the complete TFTP session,
not only destination port 69.

Permanent Network Fix

Reducing tftpblocksize is a workaround. The preferred fix is to configure the
L2VPN underlay to carry the customer MTU plus every encapsulation header.

Verify all of the following:

• Both L2VPN endpoints use the same service or pseudowire MTU.
• Every underlay interface supports the required larger frame.
• VLAN and QinQ tags are included in the MTU calculation.
• MPLS labels and any pseudowire control word are included.
• VXLAN, GRE, or IPsec overhead is included when present.
• The pseudowire is not reporting an MTU mismatch.
• Intermediate switches do not have a smaller system or port MTU.
• QoS policies or policers are not dropping TFTP bursts.
• Firewalls allow the dynamically selected TFTP UDP ports.

The exact required provider MTU depends on the encapsulation. Common core MTU
choices include 1600, 2000, or a supported jumbo MTU, but the value should be
calculated for the actual headers rather than selected blindly.

NFS Can Still Fail After TFTP Works

A small TFTP block may allow the kernel and Device Tree to download while the
underlying MTU problem remains. Linux NFS traffic can use much larger packets,
so NFS root may later stall or repeatedly retransmit.

If TFTP succeeds but Linux cannot mount the NFS root:

1. Fix the L2VPN/core MTU first.
2. Confirm that the kernel network driver initialized the expected interface.
3. Confirm that the static ip= argument contains the correct netmask and
gateway.
4. Confirm the NFS server can see requests from the board.
5. Confirm NFSv3 and its supporting RPC services are allowed through any
firewall.
6. Capture traffic on both ends and look for large packets disappearing inside
the L2VPN.

For temporary diagnosis, NFSv3 read and write sizes can be reduced:

```bash
setenv bootargs "console=${console} root=/dev/nfs rw ip=192.168.50.20:192.168.50.10::255.255.255.0::eth0:off nfsroot=192.168.50.10:/srv/nfs/rootfs,v3,tcp,rsize=1024,wsize=1024"
```

This is a diagnostic workaround, not a replacement for correcting the path
MTU.

Troubleshooting Checklist

U-Boot and TFTP

☐ ping ${serverip} succeeds.
☐ kernel_addr_r and fdt_addr_r are valid and do not overlap.
☐ The TFTP server contains Image and the correct .dtb file.
☐ tftpblocksize=1024 works, or 512 is used for diagnosis.
☐ fdt header validates the downloaded Device Tree.
☐ The firewall permits the negotiated TFTP UDP session.
☐ Large DF pings succeed across the L2VPN.

NFS Root

☐ /srv/nfs/rootfs is exported to the board’s network.
☐ /sbin/init exists and is executable.
☐ A linked /sbin/init target exists.
☐ The root filesystem architecture matches the kernel.
☐ The dynamic loader and required libraries exist.
☐ root=/dev/nfs is present in bootargs.
☐ nfsroot= points to the exported directory.
☐ The ip= argument includes the correct client IP and netmask.
☐ The kernel includes the required network and NFS-root support.
☐ The console shows VFS: Mounted root (nfs filesystem).

Safety

☐ No flash erase or write command was issued.
☐ No saveenv command was issued during testing.
☐ Only the kernel and Device Tree were loaded into RAM.

Expected Success Messages

During TFTP, expect a completed transfer and byte count rather than repeated
timeouts.

During Linux boot, look for messages similar to:

```text
IP-Config: Complete
VFS: Mounted root (nfs filesystem)
Run /sbin/init as init process
```

If VFS: Mounted root never appears, Linux did not successfully mount the NFS
export. If TFTP works only with small blocks and NFS then stalls, the L2VPN MTU
remains the leading cause.

References

• TFTP Blocksize Option: https://www.rfc-editor.org/rfc/rfc2348.html
• TFTP Option Extension: https://www.rfc-editor.org/rfc/rfc2347.html
• Requirements for IP Version 4 Routers: https://www.rfc-editor.org/rfc/rfc1812.html

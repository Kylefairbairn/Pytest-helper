# TI U\-Boot: Manual TFTP and NFS\-Root Recovery Across an L2VPN

This runbook boots a TI ARM64 board without using its incorrect `uEnv.txt` and
provides packet\-level debugging for TFTP and NFS across an L2VPN\.

Nothing here is persistent unless `saveenv` or a storage\-write command is
explicitly executed\. Do **not** run either while recovering the board\.

## Network

|Item                |Value                                  |
|--------------------|---------------------------------------|
|Board               |`10.0.0.218`                           |
|TFTP/NFS boot server|`10.0.0.139`                           |
|Netmask             |`255.255.255.0`                        |
|Gateway             |None; both systems are on `10.0.0.0/24`|
|Example NFS root    |`/srv/nfs/rootfs`                      |
|Example kernel      |`Image`                                |
|Example Device Tree |`k3-am625-sk.dtb`                      |

Replace the file names and NFS path if the server uses different values\.

## What the Jump\-Host Test Proves

A successful NFS mount from the jump host proves that NFS works for that host\.
It does not prove that:

- The board’s packets cross the L2VPN bidirectionally\.
- The export permits the board’s source address\.
- The kernel contains built\-in Ethernet and NFS\-root support\.
- The board can reach RPC `mountd` along its own network path\.
- The L2VPN carries the packet sizes used by TFTP and NFS\.

## Recovery Plan

1. Interrupt automatic boot and remain at the U\-Boot prompt\.
2. Capture all boot\-server traffic involving `10.0.0.218`\.
3. Replace the bad U\-Boot variables temporarily in RAM\.
4. Download the DTB and kernel using small TFTP blocks\.
5. Boot manually with verbose NFS\-root diagnostics\.
6. Identify the last successful network exchange\.
7. After Linux boots, repair the persistent `uEnv.txt`\.

Do not run `run bootcmd`, `run uenvcmd`, `saveenv`, or `reset` during
manual recovery\.

## 1\. Capture the Board’s Traffic

On the boot server, save a complete capture:

```bash
sudo tcpdump -ni any -e -vvv -s0 \
  -w /tmp/board-boot.pcap \
  'host 10.0.0.218'
```

In a second terminal, watch it live:

```bash
sudo tcpdump -ni any -l -e -vvv \
  'host 10.0.0.218'
```

The broad host filter intentionally captures ARP, ICMP, TFTP, RPC, mountd,
NFS, TCP retransmissions, and ICMP errors\.

Stop a capture with `Ctrl-C`\. Inspect the saved capture with:

```bash
sudo tcpdump -nn -tttt -r /tmp/board-boot.pcap
```

## 2\. Retained Server, Export, and Firewall Checks

These checks have already been completed, but they are retained so the runbook
is repeatable\.

```bash
sudo exportfs -v
showmount -e 10.0.0.139
sudo rpcinfo -p 10.0.0.139
sudo ss -lntup | grep -E ':(69|111|2049)\b'
sudo rpcinfo -p 10.0.0.139 | grep mountd
ip route get 10.0.0.218
```

Example export:

```text
/srv/nfs/rootfs 10.0.0.0/24(rw,sync,no_subtree_check,no_root_squash)
```

After changing `/etc/exports`:

```bash
sudo exportfs -ra
```

Retained firewall inspection:

```bash
sudo nft list ruleset
sudo iptables -S
```

For NFSv3, allowing only TCP ports 111 and 2049 may be insufficient because
`mountd` commonly uses another port reported by `rpcinfo -p`\.

## 3\. Inspect U\-Boot

At the U\-Boot prompt:

```bash
printenv ipaddr serverip gatewayip netmask
printenv console ethact ethprime
printenv kernel_addr_r fdt_addr_r
printenv loadaddr fdtaddr
printenv bootargs
printenv bootcmd uenvcmd
```

This records the original in\-memory state and shows the board\-selected RAM
addresses\.

## 4\. Configure Networking Temporarily

Both endpoints are on `10.0.0.0/24`, so clear any old gateway:

```bash
setenv ipaddr 10.0.0.218
setenv serverip 10.0.0.139
setenv netmask 255.255.255.0
setenv gatewayip
setenv autoload no
setenv tftpblocksize 512
```

Confirm the values:

```bash
printenv ipaddr serverip gatewayip netmask autoload tftpblocksize
```

Test reachability:

```bash
ping 10.0.0.139
```

A successful small ping proves basic connectivity, not the L2VPN path MTU\.

### Expected ping capture

```text
ARP request: Who has 10.0.0.139? Tell 10.0.0.218
ARP reply:   10.0.0.139 is at <server-mac>
ICMP echo request: 10.0.0.218 -> 10.0.0.139
ICMP echo reply:   10.0.0.139 -> 10.0.0.218
```

If ARP requests appear without replies, stop and debug the VLAN, L2VPN,
server interface, or ARP handling\. NFS cannot work without bidirectional
Layer 2 connectivity\.

## 5\. Select Safe RAM Addresses

Prefer the addresses defined by the board:

```bash
setenv kernel_addr ${kernel_addr_r}
setenv dtb_addr ${fdt_addr_r}
printenv kernel_addr dtb_addr
```

If either value is empty, use verified board\-specific values\. Use the following
only when `loadaddr` and `fdtaddr` are defined and known not to overlap:

```bash
setenv kernel_addr ${loadaddr}
setenv dtb_addr ${fdtaddr}
printenv kernel_addr dtb_addr
```

Do not invent addresses without checking the TI board’s memory map\.

## 6\. Download and Validate the Device Tree

```bash
tftpboot ${dtb_addr} k3-am625-sk.dtb
fdt addr ${dtb_addr}
fdt header
```

Do not continue if TFTP times out or `fdt header` fails\.

## 7\. Download the ARM64 Kernel

```bash
tftpboot ${kernel_addr} Image
```

The command must complete and report a byte count\.

### Healthy TFTP exchange

1. Board sends a read request to UDP port 69\.
2. Server replies from a newly selected UDP port\.
3. Server sends DATA blocks\.
4. Board acknowledges each DATA block\.
5. Final DATA block is smaller than the negotiated block size\.
6. Board acknowledges it and reports the total loaded bytes\.

### TFTP failure patterns

- Repeated DATA block: its acknowledgement did not reach the server, or the
  DATA packet did not reach the board\.
- Repeated acknowledgement: the next DATA block is being lost\.
- Small blocks work but large blocks fail: probable MTU or fragmentation issue\.
- Even 512\-byte blocks fail intermittently: investigate loss, policing,
  forwarding, link errors, or firewall session tracking\.

## 8\. Verify the Serial Console

```bash
printenv console
```

It must expand to the correct TI UART and baud rate\. If it is empty or wrong,
Linux may run without displaying useful diagnostics\. Use the known board value
rather than guessing\.

## 9\. Configure Verbose NFS\-Root Arguments

Start with small NFS reads and writes to reduce MTU sensitivity:

```bash
setenv bootargs "console=${console} root=/dev/nfs rw ip=10.0.0.218:10.0.0.139::255.255.255.0::eth0:off nfsroot=10.0.0.139:/srv/nfs/rootfs,vers=3,proto=tcp,mountproto=tcp,rsize=1024,wsize=1024 nfsrootdebug loglevel=8 ignore_loglevel"
printenv bootargs
```

Static kernel IP format:

```text
ip=<client>:<server>:<gateway>:<netmask>:<hostname>:<device>:<autoconf>
```

The gateway field is empty because both systems are on the same subnet\.

If Linux does not call the interface `eth0`, use its known kernel name\. If
the board has one usable network interface, leave the device field empty:

```bash
setenv bootargs "console=${console} root=/dev/nfs rw ip=10.0.0.218:10.0.0.139::255.255.255.0:::off nfsroot=10.0.0.139:/srv/nfs/rootfs,vers=3,proto=tcp,mountproto=tcp,rsize=1024,wsize=1024 nfsrootdebug loglevel=8 ignore_loglevel"
```

Do not include `rdinit=/init`\.

## 10\. Boot Linux Manually

```bash
booti ${kernel_addr} - ${dtb_addr}
```

The dash means no initramfs is passed\. Watch the serial console and live packet
capture simultaneously\.

## 11\. Expected NFSv3 Exchange

|Stage|Traffic                    |Meaning                         |
|-----|---------------------------|--------------------------------|
|1    |ARP request and reply      |Board resolves the server MAC   |
|2    |TCP connection to port 111 |Board contacts RPC portmapper   |
|3    |RPC reply from port 111    |Server supplies the mountd port |
|4    |Connection to mountd       |Board requests the root export  |
|5    |Successful MOUNT response  |Server returns a root filehandle|
|6    |TCP connection to port 2049|NFS operations begin            |
|7    |NFS GETATTR, LOOKUP, READ  |Kernel reads the root filesystem|
|8    |`VFS: Mounted root`        |NFS root succeeded              |

Expected serial messages:

```text
IP-Config: Complete
VFS: Mounted root (nfs filesystem)
Run /sbin/init as init process
```

## 12\. Diagnose the Last Successful Stage

### No ARP after `booti`

Probable causes:

- Kernel Ethernet driver is not built in\.
- Wrong Device Tree was loaded\.
- The `ip=` argument was not passed correctly\.
- The specified Linux interface name is wrong\.
- Kernel failed before networking initialized\.

Required kernel options must be built in, not modules:

```text
CONFIG_NFS_FS=y
CONFIG_ROOT_NFS=y
CONFIG_IP_PNP=y
```

Check the kernel build:

```bash
grep -E 'CONFIG_(NFS_FS|ROOT_NFS|IP_PNP)=' .config
```

The TI Ethernet driver must also be built in\.

### ARP request but no reply

Check:

- Server owns `10.0.0.139` on the expected interface\.
- Both endpoints belong to the same VLAN/L2VPN service\.
- MAC learning occurs at both L2VPN endpoints\.
- Broadcast and unknown\-unicast forwarding are allowed\.
- Neither IP address is duplicated\.

```bash
ip -br address
ip neigh show 10.0.0.218
```

### ARP works but no connection to port 111

The kernel initialized networking but did not begin NFS\-root mounting\. Verify
the serial log and ensure `root=/dev/nfs` and the complete `nfsroot=`
argument were passed\. Ensure no `rdinit=` argument overrides NFS root\.

### Port 111 SYN receives no reply

Retained checks:

```bash
sudo systemctl status rpcbind
sudo rpcinfo -p 10.0.0.139
sudo nft list ruleset
sudo iptables -S
```

### Port 111 works but mountd does not

```bash
sudo rpcinfo -p 10.0.0.139 | grep mountd
```

Compare the reported port with the capture\. A firewall may permit 111 and 2049
but block the separate NFSv3 mountd port\.

### Mount request returns access denied

Retained checks:

```bash
sudo exportfs -v
showmount -e 10.0.0.139
```

Confirm that the export allows `10.0.0.218` or `10.0.0.0/24`, and that the
requested path exactly matches `/srv/nfs/rootfs`\.

### Port 2049 starts but NFS retransmits or stalls

This suggests packet loss or an L2VPN MTU problem\. The temporary options:

```text
rsize=1024,wsize=1024
```

keep NFS requests small\. If they work but normal sizes do not, correct the
L2VPN underlay MTU\. It must carry the customer Ethernet frame plus all VLAN,
MPLS, pseudowire, VXLAN, GRE, or IPsec overhead\.

### NFS mounts but init fails

```bash
ls -l /srv/nfs/rootfs/sbin/init
file /srv/nfs/rootfs/sbin/init
readlink -f /srv/nfs/rootfs/sbin/init
```

Confirm that init is executable, symlink destinations exist inside the root,
the userspace architecture matches the kernel, and required runtime libraries
exist\.

## 13\. Test the L2VPN MTU

From Linux hosts on opposite sides of the L2VPN, test a full 1500\-byte IPv4
packet without fragmentation:

```bash
ping -M do -s 1472 <remote-linux-host>
```

Reduce the size until it works:

```bash
ping -M do -s 1464 <remote-linux-host>
ping -M do -s 1400 <remote-linux-host>
ping -M do -s 1300 <remote-linux-host>
ping -M do -s 1200 <remote-linux-host>
```

Approximate IPv4 path MTU equals the largest successful payload plus 28 bytes\.
Test both directions\.

For TFTP over a normal 1500\-byte IPv4 path:

```text
1500-byte IP MTU
- 20-byte IPv4 header
-  8-byte UDP header
-  4-byte TFTP header
= 1468-byte maximum TFTP data block without fragmentation
```

The L2VPN underlay must additionally carry its encapsulation overhead\.

## 14\. Optional U\-Boot NFS File Test

If this U\-Boot build supports NFS:

```bash
help nfs
nfs ${loadaddr} 10.0.0.139:/srv/nfs/rootfs/boot/Image
```

Use a path that actually exists\. This is only a diagnostic: U\-Boot retrieving
one file with its NFS implementation is not equivalent to Linux mounting NFS
as its root filesystem\.

## 15\. Import a Corrected uEnv Without Reflashing

If `corrected-uEnv.txt` is available through TFTP and `env import` exists:

```bash
tftpboot ${loadaddr} corrected-uEnv.txt
env import -t -r ${loadaddr} ${filesize}
```

Inspect it before executing anything:

```bash
printenv ipaddr serverip netmask gatewayip
printenv bootargs
printenv nfs_boot
printenv uenvcmd
```

Only run a verified recovery variable:

```bash
run nfs_boot
```

Do not run `saveenv`\. Importing without saving changes only RAM\.

## 16\. Repair the Persistent uEnv After NFS Boot

Once Linux successfully boots:

1. Identify the board’s boot storage and partition\.
2. Mount the boot partition read/write\.
3. Back up the bad `uEnv.txt`\.
4. Replace it with the validated version\.
5. Flush writes and unmount cleanly\.
6. Reboot and verify automatic boot\.

Do not guess the storage device:

```bash
lsblk -f
findmnt
```

## Copy\-and\-Paste Manual Boot Sequence

Run each command separately the first time:

```bash
setenv ipaddr 10.0.0.218
setenv serverip 10.0.0.139
setenv netmask 255.255.255.0
setenv gatewayip
setenv autoload no
setenv tftpblocksize 512
ping 10.0.0.139
setenv kernel_addr ${kernel_addr_r}
setenv dtb_addr ${fdt_addr_r}
tftpboot ${dtb_addr} k3-am625-sk.dtb
fdt addr ${dtb_addr}
fdt header
tftpboot ${kernel_addr} Image
setenv bootargs "console=${console} root=/dev/nfs rw ip=10.0.0.218:10.0.0.139::255.255.255.0::eth0:off nfsroot=10.0.0.139:/srv/nfs/rootfs,vers=3,proto=tcp,mountproto=tcp,rsize=1024,wsize=1024 nfsrootdebug loglevel=8 ignore_loglevel"
printenv bootargs
booti ${kernel_addr} - ${dtb_addr}
```

Before running it, verify the RAM variables, DTB filename, NFS path, console,
and Linux interface name\.

## Success Checklist

- [ ] Board ARPs for `10.0.0.139` and gets a reply\.
- [ ] U\-Boot pings `10.0.0.139`\.
- [ ] DTB downloads and passes `fdt header`\.
- [ ] Kernel downloads completely\.
- [ ] Linux prints `IP-Config: Complete`\.
- [ ] Board connects to RPC port 111\.
- [ ] Board connects to the reported mountd port\.
- [ ] Board connects to NFS port 2049\.
- [ ] NFS LOOKUP and READ operations appear\.
- [ ] Linux prints `VFS: Mounted root (nfs filesystem)`\.
- [ ] Linux starts `/sbin/init`\.
- [ ] Persistent `uEnv.txt` is repaired after successful recovery\.

## References

- Linux NFS\-root documentation: [https://docs\.kernel\.org/admin\-guide/nfs/nfsroot\.html](https://docs.kernel.org/admin-guide/nfs/nfsroot.html)
- U\-Boot environment command: [https://docs\.u\-boot\.org/en/latest/usage/cmd/env\.html](https://docs.u-boot.org/en/latest/usage/cmd/env.html)
- TFTP block\-size option: [https://www\.rfc\-editor\.org/rfc/rfc2348\.html](https://www.rfc-editor.org/rfc/rfc2348.html)

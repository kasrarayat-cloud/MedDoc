---
id: A07-P2-001
title: Several network sysctls below hardened defaults
severity: P2
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

Most kernel hardening sysctls are set sensibly (kptr_restrict=1,
dmesg_restrict=1, yama.ptrace_scope=1, unprivileged_bpf_disabled=2,
tcp_syncookies=1, accept_source_route=0, all.accept_redirects=0). A few
are below recommended values for an internet-facing PHI host:

| sysctl                                  | current | recommended | rationale |
|-----------------------------------------|---------|-------------|-----------|
| `net.ipv4.conf.all.send_redirects`      | 1       | 0           | host is not a router |
| `net.ipv4.conf.all.rp_filter`           | 2 (loose) | 1 (strict) | tighter spoof protection |
| `net.ipv4.conf.default.rp_filter`       | 2 (loose) | 1 (strict) | tighter spoof protection |
| `net.ipv4.conf.all.log_martians`        | 0       | 1           | log spoofed packet attempts |
| `net.ipv4.conf.default.log_martians`    | 0       | 1           | as above for new ifaces |
| `net.ipv4.conf.default.accept_redirects`| 1       | 0           | already 0 on `all` but new ifaces inherit `default` |
| `net.ipv6.conf.all.accept_redirects`    | 1       | 0           | symmetry with v4 |
| `net.ipv6.conf.default.accept_redirects`| 1       | 0           | symmetry with v4 |

`vm.swappiness=60` (default) — see A07-P1-006 for the swap encryption
finding; reducing this also reduces PHI-in-swap exposure.

## Evidence

```
$ sysctl net.ipv4.conf.all.send_redirects \
         net.ipv4.conf.all.rp_filter \
         net.ipv4.conf.all.log_martians \
         net.ipv4.conf.default.accept_redirects \
         net.ipv6.conf.all.accept_redirects
net.ipv4.conf.all.send_redirects = 1
net.ipv4.conf.all.rp_filter = 2
net.ipv4.conf.all.log_martians = 0
net.ipv4.conf.default.accept_redirects = 1
net.ipv6.conf.all.accept_redirects = 1
```

## Risk

- Loose RPF (`rp_filter=2`) accepts packets if they could egress via *any*
  interface. Strict (`=1`) requires the packet to arrive on the same
  interface the reply would leave by — meaningfully harder to spoof from
  a multihomed attacker.
- IPv6 `accept_redirects=1` allows ICMPv6 router-redirect attacks (CVE-class
  pre-`accept_redirects=0`).
- `send_redirects=1` on a non-router host leaks routing topology info.
- `log_martians=0` means spoofed-source attempts go unlogged → forensic
  blind spot.

## Recommended fix

Drop a `/etc/sysctl.d/99-meddoc.conf`:

```
# A07-P2-001
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Reduce paging pressure (couples with A07-P1-006 swap encryption)
vm.swappiness = 10
```

Apply with `sysctl --system`.

Verify post-deploy with `sudo sysctl -a | grep -E 'rp_filter|martians|redirects|swappiness'`.

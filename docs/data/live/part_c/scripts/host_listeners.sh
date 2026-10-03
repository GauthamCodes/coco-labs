#!/usr/bin/env bash
# host_listeners.sh -- every listening socket on this host, and whether any
# is on a non-loopback address. If none is, nothing on the host is
# reachable from any network, whatever the NAT or firewall in front of it:
# the tunnel (an OUTBOUND connection) is the only way in.
date -u +%FT%TZ
echo "== TCP listeners (all interfaces)"
ss -Hltn
echo "== UDP sockets bound (all interfaces)"
ss -Hlun
echo "== TCP listeners NOT on loopback"
ss -Hltn | awk '{print $4}' | grep -v -E '^(127\.|\[::1\]|::1|\[::ffff:127\.)' || echo "none"
echo "== UDP sockets NOT on loopback"
ss -Hlun | awk '{print $4}' | grep -v -E '^(127\.|\[::1\]|::1|\[::ffff:127\.)' || echo "none"
echo "== SSH / Docker API"
pgrep -a sshd || echo "no sshd process"
ss -Hltn | grep -E ':(22|2375|2376)\b' || echo "no listener on 22, 2375, 2376"
ls -l /var/run/docker.sock
echo "== containers and published ports"
docker ps --format '{{.Names}} {{.Image}} ports=[{{.Ports}}] net={{.Networks}}'

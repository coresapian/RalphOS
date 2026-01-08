#!/bin/bash
# Flush DNS cache on macOS
# Requires: sudo entry in /etc/sudoers.d/dns-flush

sudo dscacheutil -flushcache 2>/dev/null
sudo killall -HUP mDNSResponder 2>/dev/null

echo "DNS cache flushed"


#!/usr/bin/env bash
# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
#
# CI only (ci.yml, R3 Part A): recover apt after a timed-out "Setup ROS 2 Jazzy" attempt.
# The attempt's apt-get survives the step timeout and holds the dpkg lock (run 42252885733),
# so: kill it, wait for the locks, repair dpkg, and put archive.ubuntu.com ahead of the Azure
# mirror (that run crawled at ~30 kB/s there). Never run this on a developer machine.
set -u
[ "${GITHUB_ACTIONS:-}" = true ] || { echo "ci_apt_recover.sh: CI runners only" >&2; exit 2; }
sudo pkill -9 -x apt-get || true
sudo pkill -9 -x apt || true
sudo pkill -9 -f /usr/lib/apt/methods/ || true
sudo pkill -9 -x dpkg || true
for _ in $(seq 1 60); do
  sudo fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock \
    > /dev/null 2>&1 || break
  sleep 2
done
sudo rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock \
  /var/cache/apt/archives/lock
sudo dpkg --configure -a || true
if [ -f /etc/apt/apt-mirrors.txt ]; then
  printf 'http://archive.ubuntu.com/ubuntu/\tpriority:1\nhttp://azure.archive.ubuntu.com/ubuntu/\tpriority:2\nhttp://security.ubuntu.com/ubuntu/\tpriority:3\n' \
    | sudo tee /etc/apt/apt-mirrors.txt
fi
echo "apt recovered"

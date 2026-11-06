# Copyright 2026 Gautham Anil
# SPDX-License-Identifier: Apache-2.0
# R2.6: the leaderboard verifier's sandbox image (ADR 0012). Built from the BASE branch's tree
# (never the pull request's), before the network is taken away; run with --network none,
# read-only, no capabilities, an unprivileged user and CPU, memory and pid limits.
FROM python:3.12.3-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir PyYAML==6.0.1
WORKDIR /coco
COPY coco_lab /coco/coco_lab
COPY coco_schemas /coco/coco_schemas
COPY coco_config /coco/coco_config
COPY worlds /coco/worlds
COPY tools/r2/leaderboard.py /coco/tools/r2/leaderboard.py
ENV COCO_WORLDS=/coco/worlds
USER 65534:65534
ENTRYPOINT ["python", "-P", "/coco/tools/r2/leaderboard.py"]

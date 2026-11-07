// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R3.7: how to cite COCO Lab / COCO-Bench (the "Cite" section of About). Kept in step with the
 * repository's CITATION.cff by lab_web/tools/test_r3_citation.py.
 */
import { DEFAULT_BASE, REPO_BLOB_URL } from '../../site.config';

export const CITATION_TITLE =
  'COCO Lab and COCO-Bench: reproducible, browser-based benchmarking of mobile-robot navigation, validated against ROS 2 and Gazebo';
export const CITATION_AUTHOR = 'Gautham';
/** the repository, from site.config (the repository name is defined once) */
export const CITATION_URL = REPO_BLOB_URL.replace(/\/blob\/main\/$/, '');
export const SITE_URL = `https://gauthamcodes.github.io${DEFAULT_BASE}`;

export const BIBTEX = `@software{coco_lab,
  author = {${CITATION_AUTHOR}},
  title  = {${CITATION_TITLE}},
  url    = {${CITATION_URL}},
  note   = {Live at ${SITE_URL}},
  license = {Apache-2.0}
}`;

/** R3.7: "Reproduce this paper" -- the query of the paper's browser experiment link (its digest included)
 *  (docs/paper/generated/reproduce.json, tools/r3/paper_link.py; the Workbench checks the digest). */
export const REPRODUCE_QUERY =
  '?view=workbench&exp=eyJzY2hlbWEiOiJjb2NvLmV4cGVyaW1lbnQudjEiLCJ0aXRsZSI6IkNPQ08tQmVuY2ggdjEgYmFzZWxpbmU6IGRlcG90LW5hdi0xMDAsIHBsYW5uaW5nLCBwdWJsaWMiLCJmYW1pbHkiOiJwbGFubmluZyIsInNlZWQiOjEsIndvcmxkIjoiY29jb19kZXBvdF92MSIsImFsZ29yaXRobXMiOlt7Im5hbWUiOiJiZnMifSx7Im5hbWUiOiJkaWprc3RyYSJ9LHsibmFtZSI6ImFzdGFyIn0seyJuYW1lIjoiZ3JlZWR5In0seyJuYW1lIjoid2VpZ2h0ZWRfYXN0YXIifSx7Im5hbWUiOiJkc3Rhcl9saXRlIn1dLCJzY2VuYXJpb3MiOnsia2luZCI6InN1aXRlIiwiaWQiOiJkZXBvdC1uYXYtMTAwIiwidmVyc2lvbiI6MX19&d=e32dc88b25aebfee0298103dbcdc1105439d3d25b5e73f731c9476a22e780543';

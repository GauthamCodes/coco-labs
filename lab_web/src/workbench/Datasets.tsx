// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/**
 * R1.6: the Datasets tab -- the committed datasets (docs/v2/r1/datasets/index.json,
 * tools/r1/build_datasets.py): the benchmark reference results and the paired
 * model-vs-Gazebo runs that exist, each file with its sha256, size and evidence class,
 * plus the notebook that reproduces an export's summary (pandas + matplotlib).
 */
import { useEffect, useState } from 'react';
import { REPO_BLOB_URL } from '../../site.config';

const BASE = import.meta.env.BASE_URL;
const NOTEBOOK = 'docs/v2/r1/notebooks/analyse_experiment.ipynb';
const GITHUB = `${REPO_BLOB_URL}${NOTEBOOK}`;
const COLAB = `https://colab.research.google.com/github/${REPO_BLOB_URL.replace(/^https:\/\/github\.com\//, '')}${NOTEBOOK}`;

interface File { path: string; sha256: string; bytes: number; evidence: string; github: string; served?: string }
interface Dataset { id: string; kind: 'benchmark' | 'paired'; title: string; description: string; evidence: string; files: File[] }

const size = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} kB` : `${(n / 1048576).toFixed(2)} MB`);

function DatasetCard({ d }: { d: Dataset }) {
  return <article className="wb-card" data-dataset={d.id}>
    <p className="eyebrow">{d.kind === 'paired' ? 'PAIRED MODEL ↔ STACK' : 'BENCHMARK · MODEL'}</p>
    <h3>{d.title}</h3><p>{d.description}</p>
    <div className="wb-scroll"><table className="wb-table"><caption className="wb-muted">{d.files.length} file{d.files.length === 1 ? '' : 's'}</caption>
      <thead><tr><th scope="col">File</th><th scope="col">Evidence</th><th scope="col">Size</th><th scope="col">sha256</th></tr></thead>
      <tbody>{d.files.map((f) => <tr key={f.path}><td><a href={f.served ? `${BASE}${f.served}` : f.github} download={f.served ? '' : undefined}>{f.path.split('/').pop()}</a></td>
        <td>{f.evidence}</td><td>{size(f.bytes)}</td><td><code title={f.sha256}>{f.sha256.slice(0, 12)}…</code></td></tr>)}</tbody></table></div>
  </article>;
}

export function DatasetsTab() {
  const [data, setData] = useState<Dataset[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let alive = true;
    fetch(`${BASE}generated/r1/datasets.json`, { credentials: 'omit' }).then((r) => { if (!r.ok) throw new Error(`datasets: HTTP ${r.status}`); return r.json(); })
      .then((d: { datasets: Dataset[] }) => { if (alive) setData(d.datasets); }).catch((e) => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, []);
  return <section className="wb-section" aria-label="Datasets">
    <h2>Datasets</h2>
    <p className="wb-muted">Committed, checksummed, downloadable. MODEL files come from coco_lab (the model in your browser); STACK files are recorded from the full ROS 2 stack in Gazebo (a simulation; no physical robot exists). Every experiment you run exports the same file set: results.csv, summary.json, spec.json, manifest.json and, optionally, each run's MCAP trace.</p>
    <div className="wb-card"><h3>Analyse an export in Python</h3>
      <p>The notebook loads an export (or a reference result below) with pandas, recomputes the summary from results.csv, checks it against summary.json, and draws the summary plots with matplotlib.</p>
      <a href={GITHUB}>analyse_experiment.ipynb</a><a href={COLAB}>Open in Colab</a>
      <p className="wb-muted">The links point at the repository's main branch, so they work once R1 is merged.</p></div>
    {error && <p role="alert">{error}</p>}
    {!data && !error && <p role="status">Loading the datasets index…</p>}
    {data && <>
      <h3>Paired model and Gazebo runs</h3>
      <div className="wb-cards wb-wide">{data.filter((d) => d.kind === 'paired').map((d) => <DatasetCard key={d.id} d={d} />)}</div>
      <h3>COCO-Bench v0 reference results</h3>
      <div className="wb-cards wb-wide">{data.filter((d) => d.kind === 'benchmark').map((d) => <DatasetCard key={d.id} d={d} />)}</div>
    </>}
  </section>;
}

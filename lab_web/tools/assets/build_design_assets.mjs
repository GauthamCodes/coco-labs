// Copyright 2026 Gautham Anil
// SPDX-License-Identifier: Apache-2.0
/** Pin provenance and bytes for the self-hosted typefaces and one icon set. */
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
const web = join(dirname(fileURLToPath(import.meta.url)), '../..');
const repo = join(web, '..');
const output = join(repo, 'docs/v2/DESIGN_ASSETS.json');
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
const walk = (path) => readdirSync(path, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name, 'en')).flatMap((entry) => entry.isDirectory() ? walk(join(path, entry.name)) : [join(path, entry.name)]);
export function designManifest() {
  const lock = JSON.parse(readFileSync(join(web, 'package-lock.json')));
  const assets = [];
  for (const family of ['outfit', 'manrope']) {
    const name = '@fontsource-variable/' + family;
    const root = join(web, 'node_modules', name);
    const pkg = JSON.parse(readFileSync(join(root, 'package.json')));
    const meta = JSON.parse(readFileSync(join(root, 'metadata.json')));
    if (pkg.license !== 'OFL-1.1' || meta.license.type !== 'OFL-1.1') throw new Error('Expected OFL font: ' + name);
    const fontFiles = readdirSync(join(root, 'files')).filter((file) => file.endsWith('.woff2')).sort();
    const files = fontFiles.map((file) => { const path = join(root, 'files', file); const bytes = readFileSync(path); return { path: relative(repo, path), bytes: bytes.length, sha256: sha(bytes) }; });
    const licence = readFileSync(join(root, 'LICENSE'));
    assets.push({ name: meta.family, kind: 'font', role: family === 'outfit' ? 'display' : 'UI', package: name, version: pkg.version,
      licence: pkg.license, attribution: meta.license.attribution, source: 'https://fontsource.org/fonts/' + family,
      npm_integrity: lock.packages['node_modules/' + name].integrity, files,
      licence_path: 'lab_web/public/licenses/' + family + '.txt', licence_sha256: sha(licence) });
  }
  const root = join(web, 'node_modules/lucide-react');
  const pkg = JSON.parse(readFileSync(join(root, 'package.json')));
  if (pkg.license !== 'ISC') throw new Error('Expected permissive Lucide licence');
  const sources = walk(join(root, 'dist/esm')).filter((path) => /\.(js|mjs)$/.test(path)).sort();
  if (!sources.length) throw new Error('No distributed icon modules to checksum');
  const digest = createHash('sha256');
  for (const path of sources) { digest.update(relative(root, path) + '\0'); digest.update(readFileSync(path)); digest.update('\0'); }
  assets.push({ name: 'Lucide', kind: 'icon set', package: pkg.name, version: pkg.version, licence: 'ISC (retained Feather MIT notice included)',
    source: 'https://lucide.dev', npm_integrity: lock.packages['node_modules/lucide-react'].integrity,
    checksum_method: 'sha256 of sorted ESM JavaScript paths and bytes, NUL-separated', sha256: digest.digest('hex'), source_files: sources.length,
    licence_path: 'lab_web/public/licenses/lucide.txt', licence_sha256: sha(readFileSync(join(root, 'LICENSE'))) });
  assets.push({name:'COCO Lab app icon',kind:'original icon',role:'installable app',version:'1.0',licence:'Apache-2.0',source:'lab_web/public/icons/coco.svg (original repository artwork)',files:['coco.svg','coco-192.png','coco-512.png'].map(name=>{const b=readFileSync(join(web,'public/icons',name));return {path:'lab_web/public/icons/'+name,bytes:b.length,sha256:sha(b)}}),licence_path:'LICENSE',licence_sha256:sha(readFileSync(join(repo,'LICENSE')))});
  return { schema: 'lab_web.design_assets', version: '1.0', hosting: 'local Vite content-hashed font assets; no font CDN or third-party script', assets };
}
export function designAssetDoc() {
  const manifest = JSON.parse(readFileSync(output));
  return ['## Fonts and icons · Night Shift', '', 'Source of full checksums: [DESIGN_ASSETS.json](DESIGN_ASSETS.json). Packages are pinned in lab_web/package-lock.json; licences are self-hosted under public/licenses/.', '',
    '| Asset | Role | Version | Licence | Source |', '| --- | --- | --- | --- | --- |',
    ...manifest.assets.map((asset) => `| ${asset.name} | ${asset.role ?? asset.kind} | ${asset.version} | ${asset.licence} | ${asset.source} |`), '',
    ...manifest.assets.flatMap((asset) => [`**${asset.name}**`, '', ...(asset.files ?? [{ path: 'complete distributed Lucide ESM tree', sha256: asset.sha256 }]).map((file) => `- ${file.path}: \`${file.sha256}\``), `- Licence checksum: \`${asset.licence_sha256}\``, ''])].join('\n');
}
if (import.meta.url === `file://${process.argv[1]}`) {
  const manifest = designManifest();
  const text = JSON.stringify(manifest, null, 2) + '\n';
  if (process.argv.includes('--check')) {
    if (readFileSync(output, 'utf8') !== text) throw new Error('DESIGN_ASSETS.json is not current');
    for (const asset of manifest.assets) if (sha(readFileSync(join(repo, asset.licence_path))) !== asset.licence_sha256) throw new Error('Licence mismatch: ' + asset.name);
  } else {
    mkdirSync(join(web, 'public/licenses'), { recursive: true });
    writeFileSync(output, text);
    for (const asset of manifest.assets) if(asset.package) writeFileSync(join(repo, asset.licence_path), readFileSync(join(web, 'node_modules', asset.package, 'LICENSE')));
  }
  console.log('Verified licence/source/checksums: ' + manifest.assets.map((asset) => asset.name).join(', '));
}

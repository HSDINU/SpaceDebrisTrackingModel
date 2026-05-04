/**
 * Build / Docker öncesi: Dünya dokularını public/textures içine indirir (unpkg CDN).
 * Dosyalar varsa atlanır.
 */
import { existsSync, mkdirSync } from "fs";
import { writeFile } from "fs/promises";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const texturesDir = join(__dirname, "..", "public", "textures");

const FILES = [
  ["earth-blue-marble.jpg", "https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg"],
  ["earth-topology.png", "https://unpkg.com/three-globe/example/img/earth-topology.png"],
  ["earth-night-lights.jpg", "https://unpkg.com/three-globe/example/img/earth-night-lights.jpg"],
];

mkdirSync(texturesDir, { recursive: true });

for (const [name, url] of FILES) {
  const dest = join(texturesDir, name);
  if (existsSync(dest)) continue;
  process.stderr.write(`Fetching ${name}...\n`);
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`);
  const buf = Buffer.from(await res.arrayBuffer());
  await writeFile(dest, buf);
}

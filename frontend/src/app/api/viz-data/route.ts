import { existsSync, openSync, readSync, closeSync } from "fs";
import { readFileSync } from "fs";

import path from "path";
import { NextResponse } from "next/server";
import { buildVizPayload } from "@/lib/viz/buildVizPayload";
import { buildSourceSignature } from "@/lib/sourceFileSignature";
import {
  clearVizPayloadRouteCache,
  getCachedVizPayload,
  setCachedVizPayload,
} from "@/lib/viz/vizPayloadRouteCache";
import { parse } from "csv-parse/sync";

/** Repo kökü: .../SpaceDebrisTrackingModel (frontend'in bir üst dizini) */
const REPO_ROOT = path.join(process.cwd(), "..");

const SIMUL_PATH = path.join(REPO_ROOT, "data", "output", "risk_tahmin_simul.json");
const KRITIK_PATH = path.join(REPO_ROOT, "data", "output", "risk_tahmin_kritik.csv");
const TUM_PATH = path.join(REPO_ROOT, "data", "output", "risk_tahmin_tum.csv");

const SOURCE_PATHS = [SIMUL_PATH, KRITIK_PATH, TUM_PATH] as const;

/** Büyük CSV dosyalarını yalnızca ilk N byte'ını okur (satır kırpma ile) */
function readCsvHead(filePath: string, maxBytes = 4_000_000): string {
  const fd = openSync(filePath, "r");
  const buf = Buffer.alloc(maxBytes);
  const bytesRead = readSync(fd, buf, 0, maxBytes, 0);
  closeSync(fd);
  const raw = buf.toString("utf-8", 0, bytesRead);
  const lastNewline = raw.lastIndexOf("\n");
  return lastNewline > 0 ? raw.substring(0, lastNewline) : raw;
}

function buildPayloadFromDisk() {
  let simul: Record<string, unknown> | null = null;
  if (existsSync(SIMUL_PATH)) {
    try {
      const raw = readFileSync(SIMUL_PATH, "utf-8");
      simul = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      simul = null;
    }
  }

  let kritikRows: Record<string, string>[] = [];
  if (existsSync(KRITIK_PATH)) {
    try {
      const raw = readFileSync(KRITIK_PATH, "utf-8");
      kritikRows = parse(raw, {
        columns: true,
        skip_empty_lines: true,
        relax_column_count: true,
        to: 500,
      }) as Record<string, string>[];
    } catch {
      kritikRows = [];
    }
  }

  let tumRows: Record<string, string>[] | null = null;
  if (existsSync(TUM_PATH)) {
    try {
      const raw = readCsvHead(TUM_PATH, 4_000_000);
      tumRows = parse(raw, {
        columns: true,
        skip_empty_lines: true,
        relax_column_count: true,
        to: 400,
      }) as Record<string, string>[];
    } catch {
      tumRows = null;
    }
  }

  const base = buildVizPayload(simul, kritikRows, tumRows);
  return base;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const force = url.searchParams.get("force") === "1";

  const signature = buildSourceSignature([...SOURCE_PATHS]);

  if (force) {
    clearVizPayloadRouteCache();
  }

  if (!force) {
    const hit = getCachedVizPayload(signature);
    if (hit) {
      return NextResponse.json(hit, {
        headers: {
          "Cache-Control": "private, no-store, max-age=0, must-revalidate",
          "X-Viz-Data-Revision": signature,
          "X-Viz-Data-Cache": "hit",
        },
      });
    }
  }

  const base = buildPayloadFromDisk();
  const payload = { ...base, dataRevision: signature };
  setCachedVizPayload(signature, payload);

  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "private, no-store, max-age=0, must-revalidate",
      "X-Viz-Data-Revision": signature,
      "X-Viz-Data-Cache": "miss",
    },
  });
}

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

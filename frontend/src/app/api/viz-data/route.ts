import { existsSync, openSync, readSync, closeSync } from "fs";
import { readFileSync } from "fs";

import path from "path";
import { NextResponse } from "next/server";
import { buildVizPayload } from "@/lib/buildVizPayload";
import { parse } from "csv-parse/sync";

/** Repo kökü: .../SpaceDebrisTrackingModel (frontend'in bir üst dizini) */
const REPO_ROOT = path.join(process.cwd(), "..");

/** Büyük CSV dosyalarını yalnızca ilk N byte'ını okur (satır kırpma ile) */
function readCsvHead(filePath: string, maxBytes = 4_000_000): string {
  const fd = openSync(filePath, "r");
  const buf = Buffer.alloc(maxBytes);
  const bytesRead = readSync(fd, buf, 0, maxBytes, 0);
  closeSync(fd);
  const raw = buf.toString("utf-8", 0, bytesRead);
  // Son tamamlanmamış satırı kes
  const lastNewline = raw.lastIndexOf("\n");
  return lastNewline > 0 ? raw.substring(0, lastNewline) : raw;
}

export async function GET() {
  const simulPath = path.join(REPO_ROOT, "data", "output", "risk_tahmin_simul.json");
  const kritikPath = path.join(REPO_ROOT, "data", "output", "risk_tahmin_kritik.csv");
  const tumPath = path.join(REPO_ROOT, "data", "output", "risk_tahmin_tum.csv");

  let simul: Record<string, unknown> | null = null;
  if (existsSync(simulPath)) {
    try {
      const raw = readFileSync(simulPath, "utf-8");
      simul = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      simul = null;
    }
  }

  let kritikRows: Record<string, string>[] = [];
  if (existsSync(kritikPath)) {
    try {
      const raw = readFileSync(kritikPath, "utf-8");
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

  /** risk_tahmin_tum.csv 38 MB — yalnızca ilk 4 MB okunur (~400–500 satır) */
  let tumRows: Record<string, string>[] | null = null;
  if (existsSync(tumPath)) {
    try {
      const raw = readCsvHead(tumPath, 4_000_000);
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

  const payload = buildVizPayload(simul, kritikRows, tumRows);
  return NextResponse.json(payload, {
    headers: {
      "Cache-Control": "private, no-store, max-age=0, must-revalidate",
    },
  });
}

// Edge runtime yerine Node.js runtime kullan (fs modülü için)
export const runtime = "nodejs";
// Cache kullanma — her istek taze veri alır
export const dynamic = "force-dynamic";

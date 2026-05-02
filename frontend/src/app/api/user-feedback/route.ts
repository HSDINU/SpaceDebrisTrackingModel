import { appendFileSync, mkdirSync } from "fs";
import path from "path";
import { NextResponse } from "next/server";

const REPO_ROOT = path.join(process.cwd(), "..");
const OUT_FILE = path.join(REPO_ROOT, "data", "output", "user_feedback.jsonl");

type FeedbackBody = {
  vote?: "up" | "down";
  threat?: Record<string, unknown>;
  note?: string;
  hesap_utc?: string;
};

export async function POST(request: Request) {
  let body: FeedbackBody = {};
  try {
    body = (await request.json()) as FeedbackBody;
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  const vote = body.vote;
  if (vote !== "up" && vote !== "down") {
    return NextResponse.json({ ok: false, error: "vote must be up|down" }, { status: 400 });
  }

  const line = {
    ts: new Date().toISOString(),
    vote,
    hesap_utc: body.hesap_utc ?? null,
    note: body.note ?? null,
    threat: body.threat ?? null,
  };

  try {
    mkdirSync(path.dirname(OUT_FILE), { recursive: true });
    appendFileSync(OUT_FILE, `${JSON.stringify(line)}\n`, "utf-8");
  } catch (e) {
    const msg = e instanceof Error ? e.message : "write failed";
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }

  return NextResponse.json({ ok: true, path: "data/output/user_feedback.jsonl" });
}

export const runtime = "nodejs";

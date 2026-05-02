import path from "path";
import { NextResponse } from "next/server";
import { spawn } from "child_process";

const REPO_ROOT = path.join(process.cwd(), "..");
const PYTHON_CMD = process.platform === "win32" ? "python" : "python3";

type FeatureProfile =
  | "core_only"
  | "core_plus_discos"
  | "core_plus_discos_physical";

type PipelineRunBody = {
  profile?: FeatureProfile;
  train?: boolean;
  predictOnly?: boolean;
  orbitalWeight?: number;
  materialWeight?: number;
};

const VALID_PROFILES = new Set<FeatureProfile>([
  "core_only",
  "core_plus_discos",
  "core_plus_discos_physical",
]);

async function runCmd(args: string[]) {
  return await new Promise<{ code: number; output: string }>((resolve) => {
    const child = spawn(PYTHON_CMD, args, {
      cwd: REPO_ROOT,
      windowsHide: true,
      shell: false,
    });

    let output = "";
    child.stdout.on("data", (d) => (output += d.toString("utf-8")));
    child.stderr.on("data", (d) => (output += d.toString("utf-8")));
    child.on("close", (code) => resolve({ code: code ?? 1, output }));
  });
}

export async function POST(request: Request) {
  let body: PipelineRunBody = {};
  try {
    body = (await request.json()) as PipelineRunBody;
  } catch {
    body = {};
  }

  const requested = body.profile ?? "core_only";
  const profile: FeatureProfile = VALID_PROFILES.has(requested)
    ? requested
    : "core_only";
  const train = Boolean(body.train);
  const predictOnly = Boolean(body.predictOnly);
  const orbitalRaw = Number(body.orbitalWeight ?? 1);
  const materialRaw = Number(body.materialWeight ?? 1);
  const orbitalWeight = Number.isFinite(orbitalRaw) ? Math.max(0.05, orbitalRaw) : 1;
  const materialWeight = Number.isFinite(materialRaw) ? Math.max(0.05, materialRaw) : 1;

  const steps: { label: string; args: string[] }[] = [
    ...(!predictOnly
      ? [
          {
            label: "step02_build_features",
            args: ["-m", "ml_pipeline.training.step02_build_features", "--profile", profile],
          },
        ]
      : []),
    ...(!predictOnly && train
      ? [
          {
            label: "step03_train_baseline",
            args: ["-m", "ml_pipeline.training.step03_train_baseline", "--profile", profile],
          },
        ]
      : []),
    {
      label: "predict_risk",
      args: [
        "predict_risk.py",
        "--profile",
        profile,
        "--orbital-weight",
        String(orbitalWeight),
        "--material-weight",
        String(materialWeight),
      ],
    },
  ];

  const logs: Array<{ step: string; ok: boolean; output: string }> = [];
  for (const s of steps) {
    const run = await runCmd(s.args);
    logs.push({ step: s.label, ok: run.code === 0, output: run.output.slice(-12000) });
    if (run.code !== 0) {
      return NextResponse.json(
        {
          ok: false,
          activeProfile: profile,
          failedStep: s.label,
          logs,
        },
        { status: 500 },
      );
    }
  }

  return NextResponse.json({
    ok: true,
    activeProfile: profile,
    train,
    predictOnly,
    riskWeights: {
      orbital: orbitalWeight,
      material: materialWeight,
    },
    logs,
  });
}

export const runtime = "nodejs";

import { NextResponse } from "next/server";

/**
 * Ters proxy / pipeline sonrası yönlendirme öncesi hazırlık kontrolü.
 * Arayüz yerine bu uç noktayı çağırarak 200 garantisi alınır; UI’ye yönlendirme güvenli olur.
 */
export async function GET() {
  return NextResponse.json(
    { ok: true, service: "yorunge-muhafizi-frontend", ts: new Date().toISOString() },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}

export const runtime = "nodejs";

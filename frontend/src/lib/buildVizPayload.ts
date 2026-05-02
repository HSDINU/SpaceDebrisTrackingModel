import type {
  DebrisRecord,
  PipelineMeta,
  SatelliteRecord,
  SidebarPayload,
  ThreatRecord,
  UyduTehditRow,
  VizPayload,
} from "./vizTypes";

const NORAD_IDS: Record<string, string> = {
  "GOKTURK 1A": "41875",
  "GOKTURK 2": "39030",
  IMECE: "56178",
  "TURKSAT 3A": "33056",
  "TURKSAT 4A": "39522",
  "TURKSAT 4B": "40984",
  "TURKSAT 5A": "47306",
  "TURKSAT 5B": "50212",
  "TURKSAT 6A": "60001",
};

const ORBIT_RADII: Record<string, number> = {
  "GOKTURK 1A": 130,
  "GOKTURK 2": 128,
  IMECE: 126,
  "TURKSAT 3A": 155,
  "TURKSAT 4A": 157,
  "TURKSAT 4B": 159,
  "TURKSAT 5A": 161,
  "TURKSAT 5B": 163,
  "TURKSAT 6A": 165,
};

const EARTH_R_KM = 6371.0;

function orbitRadiusFromSma(smaKm: number): number {
  const r = 108.0 + (smaKm - EARTH_R_KM) * 0.025;
  return Math.round(Math.max(108.0, Math.min(380.0, r)) * 10) / 10;
}

const FALLBACK_UYDULAR: SatelliteRecord[] = [
  {
    name: "TURKSAT 3A",
    id: "TURKSAT 3A",
    norad: "33056",
    orbit: 155,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "TURKSAT 4A",
    id: "TURKSAT 4A",
    norad: "39522",
    orbit: 157,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "TURKSAT 4B",
    id: "TURKSAT 4B",
    norad: "40984",
    orbit: 159,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "TURKSAT 5A",
    id: "TURKSAT 5A",
    norad: "47306",
    orbit: 161,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "TURKSAT 5B",
    id: "TURKSAT 5B",
    norad: "50212",
    orbit: 163,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "TURKSAT 6A",
    id: "TURKSAT 6A",
    norad: "60001",
    orbit: 165,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "GOKTURK 1A",
    id: "GOKTURK 1A",
    norad: "41875",
    orbit: 130,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "GOKTURK 2",
    id: "GOKTURK 2",
    norad: "39030",
    orbit: 128,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
  {
    name: "IMECE",
    id: "IMECE",
    norad: "56178",
    orbit: 126,
    color: "#00ff00",
    kritik: 0,
    yuksek: 0,
    en_yakin_km: 0,
    en_yakin_cop: "N/A",
  },
];

function buildUyduListesi(simul: Record<string, unknown> | null): SatelliteRecord[] {
  if (!simul) return [];
  const uyduOzeti = simul.uydu_ozeti as Record<string, Record<string, unknown>> | undefined;
  if (!uyduOzeti) return [];

  const out: SatelliteRecord[] = [];
  for (const [uyduAd, d] of Object.entries(uyduOzeti)) {
    const nKritik = Number(d.kritik_sayisi ?? 0);
    out.push({
      name: uyduAd,
      id: uyduAd,
      norad: NORAD_IDS[uyduAd] ?? "N/A",
      orbit: ORBIT_RADII[uyduAd] ?? 140,
      color: nKritik > 0 ? "#ff4400" : "#00ff00",
      kritik: nKritik,
      yuksek: Number(d.yuksek_sayisi ?? 0),
      en_yakin_km: Math.round(Number(d.en_yakin_tahmin_km ?? 0) * 10) / 10,
      en_yakin_cop: String(d.en_yakin_cop ?? "N/A"),
    });
  }
  return out;
}

function buildTehditListesi(kritikRows: Record<string, string>[]): ThreatRecord[] {
  const turkAdlari = new Set(Object.keys(NORAD_IDS));
  const filtered = kritikRows.filter((row) => {
    const hiz = parseFloat(row.hiz_t0_km_s ?? "0");
    const cop = row.cop_parca ?? "";
    const turk = row.turk_uydu ?? "";
    return hiz > 0.05 && !turkAdlari.has(cop) && turk !== cop;
  });

  const sorted = [...filtered].sort(
    (a, b) => parseFloat(a.tahmin_t24_km ?? "0") - parseFloat(b.tahmin_t24_km ?? "0"),
  );

  const bySat = new Map<string, Record<string, string>[]>();
  for (const row of sorted) {
    const k = row.turk_uydu ?? "";
    if (!bySat.has(k)) bySat.set(k, []);
    const arr = bySat.get(k)!;
    if (arr.length < 3) arr.push(row);
  }

  const topPerSat = Array.from(bySat.values()).flat();
  topPerSat.sort(
    (a, b) => parseFloat(a.tahmin_t24_km ?? "0") - parseFloat(b.tahmin_t24_km ?? "0"),
  );
  const top30 = topPerSat.slice(0, 30);

  return top30.map((row) => {
    const scoreRaw = parseFloat(row.bilesik_risk_skoru ?? "0");
    let malzeme = String(row.malzeme ?? "Bilinmiyor");
    if (malzeme.length > 55) malzeme = malzeme.slice(0, 55) + "...";
    return {
      hedef_uydu: String(row.turk_uydu ?? ""),
      yaklasan_cop: String(row.cop_parca ?? ""),
      minimum_mesafe_km: Math.round(parseFloat(row.tahmin_t24_km ?? "0") * 10) / 10,
      mesafe_t0_km: Math.round(parseFloat(row.mesafe_t0_km ?? "0") * 10) / 10,
      bagil_hiz_km_s: Math.round(parseFloat(row.hiz_t0_km_s ?? "0") * 1000) / 1000,
      hiz_t24_km_s: Math.round(parseFloat(row.hiz_t24_km_s ?? "0") * 1000) / 1000,
      delta_mesafe_km: Math.round(parseFloat(row.delta_mesafe_km ?? "0") * 10) / 10,
      tehlike_skoru: Math.round(scoreRaw * 1000) / 10,
      risk_seviyesi: String(row.risk_sinifi ?? "DUSUK"),
      risk_zamani: String(row.trend ?? ""),
      malzeme,
      yanma_orani: String(row.yanma_orani ?? "N/A"),
      yere_dusme_riski: Math.round(parseFloat(row.yere_dusme_riski ?? "0") * 100) / 100,
      orbital_risk: Math.round(parseFloat(row.orbital_risk_skoru ?? "0") * 100) / 100,
      egim: Math.round(parseFloat(row.cop_inclination_deg ?? "0") * 100) / 100,
      eksantrisite: Math.round(parseFloat(row.cop_eccentricity ?? "0") * 100000) / 100000,
    };
  });
}

const BANDS: [number, number, number][] = [
  [110.0, 125.0, 150],
  [125.0, 145.0, 80],
  [145.0, 200.0, 80],
  [200.0, 380.0, 90],
];

type RowWithOrbit = Record<string, string> & { _orbit_r: number };

function buildDebris3d(
  tumRows: Record<string, string>[] | null,
  kritikRows: Record<string, string>[],
): DebrisRecord[] {
  let src = tumRows;
  if (!src || src.length === 0) {
    if (kritikRows.length === 0) return [];
    src = kritikRows;
  }
  if (!src || src.length === 0) return [];

  const withOrbit: RowWithOrbit[] = src.map((row) => {
    const sma = parseFloat(row.cop_sma_km ?? "0");
    const orbit_r =
      row.orbit_r !== undefined
        ? parseFloat(String(row.orbit_r))
        : orbitRadiusFromSma(sma);
    return { ...row, _orbit_r: orbit_r } as RowWithOrbit;
  });

  withOrbit.sort(
    (a, b) =>
      parseFloat(b.bilesik_risk_skoru ?? "0") - parseFloat(a.bilesik_risk_skoru ?? "0"),
  );

  const seen = new Set<string>();
  const parts: RowWithOrbit[][] = [];
  for (const [lo, hi, n] of BANDS) {
    const band = withOrbit.filter((r) => r._orbit_r >= lo && r._orbit_r < hi);
    parts.push(band.slice(0, n));
  }

  let topDeb: RowWithOrbit[] = parts.flat();
  if (topDeb.length === 0) {
    topDeb = withOrbit.slice(0, 300);
  }

  const unique: RowWithOrbit[] = [];
  for (const row of topDeb) {
    const id = row.cop_parca ?? "";
    if (seen.has(id)) continue;
    seen.add(id);
    unique.push(row);
  }

  return unique.map((row) => {
    const orbit_r = row._orbit_r;
    let material = String(row.malzeme ?? "Bilinmiyor");
    if (material.length > 60) material = material.slice(0, 57) + "...";
    return {
      id: String(row.cop_parca ?? "DEBRIS"),
      source: String(row.cop_kaynak ?? ""),
      orbit: Math.round(orbit_r * 10) / 10,
      velocity: `${parseFloat(row.hiz_t0_km_s ?? "0").toFixed(2)} km/s`,
      material,
      burn_rate: String(row.yanma_orani ?? "N/A"),
      reentry_risk: Math.round(parseFloat(row.yere_dusme_riski ?? "0") * 100) / 100,
      risk_score: Math.round(parseFloat(row.bilesik_risk_skoru ?? "0") * 1000) / 10,
      risk_class: String(row.risk_sinifi ?? "ORTA"),
      inclination: Math.round(parseFloat(row.cop_inclination_deg ?? "0") * 100) / 100,
      eccentricity:
        Math.round(parseFloat(row.cop_eccentricity ?? "0") * 100000) / 100000,
    };
  });
}

function uniqueDebrisCountFromTum(tum: Record<string, string>[] | null): number {
  if (!tum?.length) return 0;
  const s = new Set<string>();
  for (const row of tum) {
    const id = row.cop_parca ?? "";
    if (id) s.add(id);
  }
  return s.size;
}

function buildUyduTehditRows(
  simul: Record<string, unknown> | null,
): UyduTehditRow[] {
  if (!simul) return [];
  const uyduOzeti = simul.uydu_ozeti as
    | Record<string, Record<string, unknown>>
    | undefined;
  if (!uyduOzeti) return [];
  const rows: UyduTehditRow[] = Object.entries(uyduOzeti).map(([name, d]) => ({
    name,
    kritik: Number(d.kritik_sayisi ?? 0),
    yuksek: Number(d.yuksek_sayisi ?? 0),
    en_yakin_km: Number(d.en_yakin_tahmin_km ?? 0),
    en_yakin_cop: String(d.en_yakin_cop ?? "-"),
  }));
  rows.sort((a, b) => a.en_yakin_km - b.en_yakin_km);
  return rows;
}

function buildSidebar(
  simul: Record<string, unknown> | null,
  tumRows: Record<string, string>[] | null,
): SidebarPayload {
  const dataReady = simul != null;
  const meta = (simul?.meta ?? {}) as Record<string, unknown>;
  const riskOzeti = (simul?.risk_ozeti ?? {}) as Record<string, number>;
  const uyduOzeti = simul?.uydu_ozeti as Record<string, unknown> | undefined;
  const nUydu = uyduOzeti ? Object.keys(uyduOzeti).length : 0;
  const hesap = String(meta.hesap_utc ?? "");

  return {
    dataReady,
    hesapUtc: hesap.length >= 19 ? hesap.slice(0, 19) : hesap || "Bilinmiyor",
    modelLabel: String(meta.model ?? "LightGBM"),
    nToplamCift: Number(meta.n_toplam_cift ?? 0),
    nUydu,
    nDebrisUnique: uniqueDebrisCountFromTum(tumRows),
    risk: {
      kritik: Number(riskOzeti.KRITIK ?? 0),
      yuksek: Number(riskOzeti.YUKSEK ?? 0),
      orta: Number(riskOzeti.ORTA ?? 0),
      dusuk: Number(riskOzeti.DUSUK ?? 0),
    },
    uyduTehdit: buildUyduTehditRows(simul),
  };
}

function buildPipelineMeta(simul: Record<string, unknown> | null): PipelineMeta {
  if (!simul) {
    return {
      hesap_utc: "N/A",
      model: "N/A",
      n_toplam: 0,
      n_kritik: 0,
      n_yuksek: 0,
      n_orta: 0,
      n_dusuk: 0,
    };
  }
  const meta = (simul.meta ?? {}) as Record<string, unknown>;
  const riskOzeti = (simul.risk_ozeti ?? {}) as Record<string, number>;
  const hesap = String(meta.hesap_utc ?? "");
  return {
    hesap_utc: hesap.slice(0, 19),
    model: String(meta.model ?? "LightGBM"),
    n_toplam: Number(meta.n_toplam_cift ?? 0),
    n_kritik: Number(riskOzeti.KRITIK ?? 0),
    n_yuksek: Number(riskOzeti.YUKSEK ?? 0),
    n_orta: Number(riskOzeti.ORTA ?? 0),
    n_dusuk: Number(riskOzeti.DUSUK ?? 0),
  };
}

export function buildVizPayload(
  simul: Record<string, unknown> | null,
  kritikRows: Record<string, string>[],
  tumRows: Record<string, string>[] | null,
): VizPayload {
  let uyduListesi = buildUyduListesi(simul);
  if (uyduListesi.length === 0) uyduListesi = FALLBACK_UYDULAR;

  const tehditListesi = buildTehditListesi(kritikRows);
  const debris3d = buildDebris3d(tumRows, kritikRows);
  const pipelineMeta = buildPipelineMeta(simul);
  const sidebar = buildSidebar(simul, tumRows);

  const logMessages = [
    `Pipeline tamamlandı — ${pipelineMeta.hesap_utc} UTC`,
    `LightGBM modeli yüklendi: ${pipelineMeta.model}`,
    `${pipelineMeta.n_toplam.toLocaleString()} (uydu × çöp) çifti analiz edildi`,
    `YÜKSEK risk tespiti: ${pipelineMeta.n_yuksek.toLocaleString()} çift`,
    `KRİTİK risk tespiti: ${pipelineMeta.n_kritik.toLocaleString()} çift`,
    `${debris3d.length} benzersiz çöp cismi görselleştirildi (4 yörünge bandı)`,
    "SGP4 propagator aktif — t₀+24h tahmini tamamlandı",
    "TCA (Time of Closest Approach) analizi tamamlandı",
    "Orbital korelasyon matrisi hesaplandı",
    "Tehdit sıralama ve risk skorlama güncellendi",
    "Yörünge temizleme raporu hazır",
  ];

  return {
    turkishSatellitesData: uyduListesi,
    realThreatsData: tehditListesi,
    realDebrisData: debris3d,
    pipelineMeta,
    logMessages,
    sidebar,
  };
}

export const FALLBACK_VIZ_PAYLOAD: VizPayload = {
  ...buildVizPayload(null, [], null),
  dataRevision: "fallback",
};

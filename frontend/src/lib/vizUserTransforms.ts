import type { DebrisRecord, ThreatRecord, VizPayload } from "./vizTypes";

/** İstemci tarafı deney: orbital vs malzeme bileşik skor ağırlığı (modeli yeniden eğitmez). */
export type ExperimentWeights = {
  orbital: number;
  material: number;
};

/** DISCOS / kütle filtreleri — yalnızca görünüm ve sahne verisi (pipeline çıktısı değişmez). */
export type UserDataFilters = {
  objectClasses: string[];
  missions: string[];
  massFilterEnabled: boolean;
  massMinKg: number;
  massMaxKg: number;
  includeUnknownDiscos: boolean;
};

export const DEFAULT_EXPERIMENT_WEIGHTS: ExperimentWeights = {
  orbital: 1,
  material: 1,
};

export const DEFAULT_USER_DATA_FILTERS: UserDataFilters = {
  objectClasses: [],
  missions: [],
  massFilterEnabled: false,
  massMinKg: 0,
  massMaxKg: 15_000,
  includeUnknownDiscos: true,
};

export function blendedDisplayScore(
  orbital: number,
  material: number,
  w: ExperimentWeights,
): number {
  const wo = Math.max(0.05, w.orbital);
  const wm = Math.max(0.05, w.material);
  const blended = (wo * orbital + wm * material) / (wo + wm);
  return Math.round(blended * 1000) / 10;
}

function threatMatchesFilters(t: ThreatRecord, f: UserDataFilters): boolean {
  if (f.objectClasses.length > 0) {
    const cls = t.discos_object_class?.trim();
    const ok =
      (cls && f.objectClasses.includes(cls)) ||
      (f.includeUnknownDiscos && !cls);
    if (!ok) return false;
  }
  if (f.missions.length > 0) {
    const m = t.discos_mission?.trim();
    const ok =
      (m && f.missions.includes(m)) || (f.includeUnknownDiscos && !m);
    if (!ok) return false;
  }
  if (f.massFilterEnabled) {
    const mass = t.discos_mass_kg;
    if (mass === undefined || Number.isNaN(mass)) {
      return f.includeUnknownDiscos;
    }
    if (mass < f.massMinKg || mass > f.massMaxKg) return false;
  }
  return true;
}

function debrisMatchesFilters(d: DebrisRecord, f: UserDataFilters): boolean {
  if (f.objectClasses.length > 0) {
    const cls = d.discos_object_class?.trim();
    const ok =
      (cls && f.objectClasses.includes(cls)) ||
      (f.includeUnknownDiscos && !cls);
    if (!ok) return false;
  }
  if (f.missions.length > 0) {
    const m = d.discos_mission?.trim();
    const ok =
      (m && f.missions.includes(m)) || (f.includeUnknownDiscos && !m);
    if (!ok) return false;
  }
  if (f.massFilterEnabled) {
    const mass = d.discos_mass_kg;
    if (mass === undefined || Number.isNaN(mass)) {
      return f.includeUnknownDiscos;
    }
    if (mass < f.massMinKg || mass > f.massMaxKg) return false;
  }
  return true;
}

/**
 * Sunucu payload'ına kullanıcı deney ağırlıkları ve filtreleri uygular.
 * Sidebar / meta sayıları değiştirilmez; sahne ve tehdit listesi buna göre güncellenir.
 */
export function applyUserVizTransforms(
  base: VizPayload,
  experiment: ExperimentWeights,
  filters: UserDataFilters,
): VizPayload {
  const realThreatsData = base.realThreatsData
    .filter((t) => threatMatchesFilters(t, filters))
    .map((t) => ({
      ...t,
      tehlike_skoru: blendedDisplayScore(
        t.orbital_risk,
        t.yere_dusme_riski,
        experiment,
      ),
    }));

  const realDebrisData = base.realDebrisData
    .filter((d) => debrisMatchesFilters(d, filters))
    .map((d) => {
      if (d.orbital_risk === undefined) return { ...d };
      return {
        ...d,
        risk_score: blendedDisplayScore(
          d.orbital_risk,
          d.reentry_risk,
          experiment,
        ),
      };
    });

  return {
    ...base,
    realThreatsData,
    realDebrisData,
  };
}

export function buildFilterOptionsFromPayload(base: VizPayload): {
  classes: string[];
  missions: string[];
} {
  const cls = new Set<string>();
  const mis = new Set<string>();
  for (const t of base.realThreatsData) {
    const c = t.discos_object_class?.trim();
    if (c) cls.add(c);
    const m = t.discos_mission?.trim();
    if (m) mis.add(m);
  }
  for (const d of base.realDebrisData) {
    const c = d.discos_object_class?.trim();
    if (c) cls.add(c);
    const m = d.discos_mission?.trim();
    if (m) mis.add(m);
  }
  return {
    classes: [...cls].sort(),
    missions: [...mis].sort(),
  };
}

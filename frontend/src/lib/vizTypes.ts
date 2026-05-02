export type SatelliteRecord = {
  name: string;
  id: string;
  norad: string;
  orbit: number;
  color: string;
  kritik: number;
  yuksek: number;
  en_yakin_km: number;
  en_yakin_cop: string;
};

export type ThreatRecord = {
  hedef_uydu: string;
  yaklasan_cop: string;
  minimum_mesafe_km: number;
  mesafe_t0_km: number;
  bagil_hiz_km_s: number;
  hiz_t24_km_s: number;
  delta_mesafe_km: number;
  tehlike_skoru: number;
  risk_seviyesi: string;
  risk_zamani: string;
  malzeme: string;
  yanma_orani: string;
  yere_dusme_riski: number;
  orbital_risk: number;
  egim: number;
  eksantrisite: number;
};

export type DebrisRecord = {
  id: string;
  source: string;
  orbit: number;
  velocity: string;
  material: string;
  burn_rate: string;
  reentry_risk: number;
  risk_score: number;
  risk_class: string;
  inclination: number;
  eccentricity: number;
};

export type PipelineMeta = {
  hesap_utc: string;
  model: string;
  n_toplam: number;
  n_kritik: number;
  n_yuksek: number;
  n_orta: number;
  n_dusuk: number;
};

/** Streamlit `st.sidebar` ile aynı kaynak (simul.json + tum.csv) */
export type UyduTehditRow = {
  name: string;
  kritik: number;
  yuksek: number;
  en_yakin_km: number;
  en_yakin_cop: string;
};

export type SidebarPayload = {
  dataReady: boolean;
  hesapUtc: string;
  modelLabel: string;
  nToplamCift: number;
  nUydu: number;
  nDebrisUnique: number;
  risk: {
    kritik: number;
    yuksek: number;
    orta: number;
    dusuk: number;
  };
  uyduTehdit: UyduTehditRow[];
};

export type VizPayload = {
  turkishSatellitesData: SatelliteRecord[];
  realThreatsData: ThreatRecord[];
  realDebrisData: DebrisRecord[];
  pipelineMeta: PipelineMeta;
  logMessages: string[];
  sidebar: SidebarPayload;
  /**
   * Kaynak dosya imzası (mtime+size). Aynı kalırsa 3D sahne yeniden kurulmaz;
   * API her yanıtta döner.
   */
  dataRevision?: string;
};

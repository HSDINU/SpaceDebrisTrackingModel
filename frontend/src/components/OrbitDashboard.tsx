"use client";

import {
  startTransition,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { HudScanIcon, HudSettingsIcon } from "@/components/HudHeaderIcons";
import PipelineSidebar from "@/components/PipelineSidebar";
import { FALLBACK_VIZ_PAYLOAD } from "@/lib/buildVizPayload";
import {
  mountOrbitScene,
  type OrbitSceneHandle,
  type VizSimSettings,
} from "@/lib/orbitEngine";
import type { VizPayload } from "@/lib/vizTypes";

const DEFAULT_VIZ_SETTINGS: VizSimSettings = {
  riskThreshold: 1000,
  debrisSizeMultiplier: 1,
  orbitSpeedMultiplier: 1,
  showLines: true,
  showOrbitRings: false,
  earthRotate: true,
};

export default function OrbitDashboard() {
  const rootRef = useRef<HTMLDivElement>(null);
  const selectionPanelRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<OrbitSceneHandle | null>(null);
  const [payload, setPayload] = useState<VizPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [pipelineDrawerOpen, setPipelineDrawerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [vizForm, setVizForm] = useState<VizSimSettings>(DEFAULT_VIZ_SETTINGS);

  const fetchVizData = useCallback(
    (opts?: { signal?: AbortSignal; force?: boolean }) => {
      const { signal, force } = opts ?? {};
      setLoadError(null);
      const q = new URLSearchParams();
      q.set("t", String(Date.now()));
      if (force) q.set("force", "1");
      return fetch(`/api/viz-data?${q}`, {
        cache: "no-store",
        signal,
      })
        .then((r) => {
          if (!r.ok) throw new Error(`${r.status}`);
          return r.json() as Promise<VizPayload>;
        })
        .then((data) => {
          startTransition(() => setPayload(data));
        })
        .catch((err: unknown) => {
          const aborted =
            err instanceof DOMException && err.name === "AbortError";
          if (aborted) return;
          setLoadError(
            "Veri yüklenemedi. Pipeline çıktısı ve API yolunu kontrol edin.",
          );
        });
    },
    [],
  );

  useEffect(() => {
    const ac = new AbortController();
    void fetchVizData({ signal: ac.signal });
    return () => ac.abort();
  }, [fetchVizData]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    void fetchVizData({ force: true }).finally(() => setRefreshing(false));
  }, [fetchVizData]);

  /** Aynı kalırsa Three.js sahnesi yeniden kurulmaz (takılma azalır). */
  const sceneDataRevision = useMemo(() => {
    if (payload == null) return "no-payload";
    return (
      payload.dataRevision ??
      `legacy:${payload.pipelineMeta.hesap_utc}:${payload.pipelineMeta.n_toplam}`
    );
  }, [payload]);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1101px)");
    const close = () => {
      if (mq.matches) setPipelineDrawerOpen(false);
    };
    mq.addEventListener("change", close);
    close();
    return () => mq.removeEventListener("change", close);
  }, []);

  useEffect(() => {
    if (!settingsOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSettingsOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settingsOpen]);

  /** İki rAF: layout ölçümü (orbit-host yüksekliği) kesinleşsin; Strict Mode'da cleanup güvenli olsun.
   *  Bağımlılık: yalnızca `sceneDataRevision` — veri dosyaları değişmedikçe sahne dispose edilmez. */
  useLayoutEffect(() => {
    if (!rootRef.current) return;

    const vizData = payload ?? FALLBACK_VIZ_PAYLOAD;

    let cancelled = false;
    let dispose: (() => void) | undefined;
    let innerRaf = 0;
    sceneRef.current = null;

    const outerRaf = requestAnimationFrame(() => {
      innerRaf = requestAnimationFrame(() => {
        if (cancelled || !rootRef.current) return;
        const root = rootRef.current;

        const host = root.querySelector("[data-orbit-host]") as HTMLElement | null;
        const radarWindows = root.querySelector("#radar-windows") as HTMLElement | null;
        const criticalThreatsList = root.querySelector(
          "#critical-threats-list",
        ) as HTMLElement | null;
        const conjunctionCount = root.querySelector(
          "#conjunction-count",
        ) as HTMLElement | null;
        const multiCollisionAlert = root.querySelector(
          "#multi-collision-alert",
        ) as HTMLElement | null;
        const logContainer = root.querySelector("#log-container") as HTMLElement | null;
        const fpsDisplay = root.querySelector("#fps-display") as HTMLElement | null;
        const utcClock = root.querySelector("#utc-clock") as HTMLElement | null;
        const emergencyBtn = root.querySelector("#emergency-btn") as HTMLElement | null;
        const selectionPanel = root.querySelector("#selection-panel") as HTMLElement | null;
        const panelTitle = root.querySelector("#panel-title") as HTMLElement | null;
        const panelTypeTag = root.querySelector("#panel-type-tag") as HTMLElement | null;
        const panelContent = root.querySelector("#panel-content-area") as HTMLElement | null;
        const totalPairsDisplay = root.querySelector(
          "#total-pairs-display",
        ) as HTMLElement | null;
        const logModelTag = root.querySelector("#log-model-tag") as HTMLElement | null;
        const initLogTime = root.querySelector("#init-log-time") as HTMLElement | null;
        const initLogMsg = root.querySelector("#init-log-msg") as HTMLElement | null;
        const riskThresholdDisplay = root.querySelector(
          "#risk-threshold-display",
        ) as HTMLElement | null;

        if (
          !host ||
          !radarWindows ||
          !criticalThreatsList ||
          !conjunctionCount ||
          !multiCollisionAlert ||
          !selectionPanel ||
          !panelTitle ||
          !panelTypeTag ||
          !panelContent
        ) {
          return;
        }

        const scene = mountOrbitScene(
          host,
          {
            radarWindows,
            criticalThreatsList,
            conjunctionCount,
            multiCollisionAlert,
            logContainer,
            fpsDisplay,
            utcClock,
            emergencyBtn,
            selectionPanel,
            panelTitle,
            panelTypeTag,
            panelContent,
            totalPairsDisplay,
            logModelTag,
            initLogTime,
            initLogMsg,
            riskThresholdDisplay,
          },
          vizData,
        );
        sceneRef.current = scene;
        dispose = scene.dispose;
      });
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(outerRaf);
      cancelAnimationFrame(innerRaf);
      dispose?.();
      sceneRef.current = null;
    };
    // payload bu effect içinde yalnızca revision değiştiği render anındaki değeri kullanır
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sahne yalnızca sceneDataRevision değişince kurulur
  }, [sceneDataRevision]);

  const metaChip =
    payload != null
      ? `ML→ YÜKSEK: ${payload.pipelineMeta.n_yuksek.toLocaleString()} | KRİTİK: ${payload.pipelineMeta.n_kritik.toLocaleString()}`
      : "…";

  return (
    <div ref={rootRef} className="hud-root">
      <div
        id="multi-collision-alert"
        className="multi-collision-alert animate-alarm hidden"
      >
        <span className="flex items-center gap-3">
          ÇOK HEDEFLİ ÇARPIŞMA UYARISI: AŞIRI YAKLAŞMA TESPİT EDİLDİ
        </span>
      </div>

      <header className="hud-header">
        <div className="hud-header-row">
          <div className="hud-title-wrap">
            <button
              type="button"
              className="hud-icon-btn"
              aria-label="Pipeline sidebar"
              aria-expanded={pipelineDrawerOpen}
              onClick={() => setPipelineDrawerOpen((o) => !o)}
            >
              ☰
            </button>
            <h1 className="hud-title">YÖRÜNGE MUHAFIZI</h1>
            <span className="hud-subtitle">YÖRÜNGE ANALİZİ</span>
          </div>
          <div className="hud-header-tools">
            <button
              type="button"
              className="hud-header-tool"
              title="Yeni tarama"
              aria-label="Yeni tarama"
              onClick={() => sceneRef.current?.triggerScan()}
            >
              <HudScanIcon className="hud-header-tool-svg" />
            </button>
            <button
              type="button"
              className="hud-header-tool"
              title="Sistem ayarları"
              aria-label="Sistem ayarları"
              onClick={() => {
                const snap =
                  sceneRef.current?.getSettingsSnapshot() ??
                  DEFAULT_VIZ_SETTINGS;
                setVizForm(snap);
                setSettingsOpen(true);
              }}
            >
              <HudSettingsIcon className="hud-header-tool-svg" />
            </button>
          </div>
        </div>
        <div id="conjunction-count" className="hud-chip hud-status-strip">
          {loadError ? "VERİ HATASI" : metaChip}
        </div>
      </header>

      <aside className="left-rail">
        <div className="left-rail-top">TEHDİTLER</div>
        <div className="left-rail-mid">
          <span id="utc-clock" className="utc-label">
            UTC
          </span>
          <button type="button" id="emergency-btn" className="emergency-btn">
            ACİL MÜDAHALE
          </button>
        </div>
      </aside>

      <button
        type="button"
        className={`pipeline-sidebar-backdrop${pipelineDrawerOpen ? " is-visible" : ""}`}
        aria-label="Sidebar kapat"
        onClick={() => setPipelineDrawerOpen(false)}
      />

      <main className="hud-main">
        <aside
          className={`pipeline-sidebar${pipelineDrawerOpen ? " is-drawer-open" : ""}`}
        >
          <PipelineSidebar
            sidebar={payload?.sidebar ?? null}
            loadError={loadError != null}
            onRefresh={handleRefresh}
            refreshing={refreshing}
          />
        </aside>

        <div className="hud-main-body">
          <section className="left-panel">
            <div className="panel-card">
              <div className="panel-heading">
                <div className="panel-title">SİSTEM KAYDI</div>
                <span id="log-model-tag" className="log-model-tag">
                  …
                </span>
              </div>
              <div id="log-container" className="log-list hud-log-scroll">
                <div className="log-line">
                  <span id="init-log-time" className="log-time">
                    [--:--:--]
                  </span>
                  <span id="init-log-msg">Pipeline bağlantısı kuruluyor...</span>
                </div>
              </div>
            </div>

            <div className="panel-card grow-card">
              <div className="panel-title danger">KRİTİK SEKTÖR</div>
              <div
                id="critical-threats-list"
                className="critical-list"
              >
                <p className="critical-placeholder">Tehdit verisi yükleniyor...</p>
              </div>
            </div>
          </section>

          <section className="scene-area">
            <div data-orbit-host className="orbit-host"></div>

            <div className="threat-row-wrap">
              <div id="radar-windows" className="threat-row" />
            </div>

            <div className="bottom-status">
              <span>KAMERA: WASD + FARE</span>
              <span>
                TOPLAM ÇİFT:{" "}
                <span id="total-pairs-display">
                  {payload?.pipelineMeta.n_toplam.toLocaleString() ?? "—"}
                </span>
              </span>
              <span>
                YÜKSEK EŞİK:{" "}
                <span id="risk-threshold-display">1,000 KM</span>
              </span>
              <span id="fps-display">60 FPS</span>
            </div>
          </section>
        </div>
      </main>

      <div
        ref={selectionPanelRef}
        id="selection-panel"
        className="selection-panel-hud hidden"
      >
        <div className="selection-head">
          <div>
            <h3 id="panel-title" className="panel-hud-title">
              NESNE_KİMLİĞİ
            </h3>
            <p id="panel-type-tag" className="panel-hud-tag">
              SINIFLANDIRMA: BİLİNMİYOR
            </p>
          </div>
          <button
            type="button"
            className="selection-close"
            aria-label="Kapat"
            onClick={() => selectionPanelRef.current?.classList.add("hidden")}
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <div id="panel-content-area" className="selection-body" />
      </div>

      {settingsOpen ? (
        <div
          className="viz-settings-overlay"
          role="presentation"
          onClick={() => setSettingsOpen(false)}
        >
          <div
            className="viz-settings-panel"
            role="dialog"
            aria-labelledby="viz-settings-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="viz-settings-head">
              <h2 id="viz-settings-title" className="viz-settings-title">
                <span className="material-symbols-outlined viz-settings-title-icon">
                  settings
                </span>
                SİSTEM AYARLARI
              </h2>
              <button
                type="button"
                className="viz-settings-close"
                aria-label="Kapat"
                onClick={() => setSettingsOpen(false)}
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>

            <div className="viz-settings-body">
              <label className="viz-settings-field">
                <div className="viz-settings-label-row">
                  <span>Risk eşiği (yakınlık / çizgiler)</span>
                  <span className="viz-settings-value">
                    {vizForm.riskThreshold.toLocaleString()} km
                  </span>
                </div>
                <input
                  type="range"
                  min={500}
                  max={10000}
                  step={500}
                  value={vizForm.riskThreshold}
                  onChange={(e) =>
                    setVizForm((f) => ({
                      ...f,
                      riskThreshold: Number(e.target.value),
                    }))
                  }
                  className="viz-settings-range"
                />
                <div className="viz-settings-range-hint">
                  <span>500 km</span>
                  <span>10,000 km</span>
                </div>
              </label>

              <label className="viz-settings-field">
                <div className="viz-settings-label-row">
                  <span>Debris boyutu</span>
                  <span className="viz-settings-value">
                    {vizForm.debrisSizeMultiplier.toFixed(1)}×
                  </span>
                </div>
                <input
                  type="range"
                  min={0.5}
                  max={3}
                  step={0.5}
                  value={vizForm.debrisSizeMultiplier}
                  onChange={(e) =>
                    setVizForm((f) => ({
                      ...f,
                      debrisSizeMultiplier: Number(e.target.value),
                    }))
                  }
                  className="viz-settings-range"
                />
                <div className="viz-settings-range-hint">
                  <span>0.5×</span>
                  <span>3.0×</span>
                </div>
              </label>

              <label className="viz-settings-field">
                <div className="viz-settings-label-row">
                  <span>Yörünge hızı</span>
                  <span className="viz-settings-value">
                    {vizForm.orbitSpeedMultiplier.toFixed(1)}×
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={4}
                  step={0.5}
                  value={vizForm.orbitSpeedMultiplier}
                  onChange={(e) =>
                    setVizForm((f) => ({
                      ...f,
                      orbitSpeedMultiplier: Number(e.target.value),
                    }))
                  }
                  className="viz-settings-range"
                />
                <div className="viz-settings-range-hint">
                  <span>0 durdur</span>
                  <span>4.0× hızlı</span>
                </div>
              </label>

              <div className="viz-settings-checks">
                <label className="viz-settings-check">
                  <input
                    type="checkbox"
                    checked={vizForm.showLines}
                    onChange={(e) =>
                      setVizForm((f) => ({ ...f, showLines: e.target.checked }))
                    }
                  />
                  Tehdit çizgileri
                </label>
                <label className="viz-settings-check">
                  <input
                    type="checkbox"
                    checked={vizForm.showOrbitRings}
                    onChange={(e) =>
                      setVizForm((f) => ({
                        ...f,
                        showOrbitRings: e.target.checked,
                      }))
                    }
                  />
                  Yörünge halkaları (LEO / MEO / GEO)
                </label>
                <label className="viz-settings-check">
                  <input
                    type="checkbox"
                    checked={vizForm.earthRotate}
                    onChange={(e) =>
                      setVizForm((f) => ({
                        ...f,
                        earthRotate: e.target.checked,
                      }))
                    }
                  />
                  Dünya rotasyonu
                </label>
              </div>
            </div>

            <button
              type="button"
              className="viz-settings-apply"
              onClick={() => {
                sceneRef.current?.applyVizSettings(vizForm);
                setSettingsOpen(false);
              }}
            >
              Uygula
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

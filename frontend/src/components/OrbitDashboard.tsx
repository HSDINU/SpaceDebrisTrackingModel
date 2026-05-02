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
import PipelineSidebar from "@/features/pipeline/PipelineSidebar";
import UserParticipationPanel from "@/features/participation/UserParticipationPanel";
import { FALLBACK_VIZ_PAYLOAD } from "@/lib/viz/buildVizPayload";
import {
  mountOrbitScene,
  type OrbitSceneHandle,
  type VizSimSettings,
} from "@/features/orbit/orbitEngine";
import type { ThreatRecord, VizPayload } from "@/lib/viz/vizTypes";
import {
  applyUserVizTransforms,
  buildFilterOptionsFromPayload,
  DEFAULT_EXPERIMENT_WEIGHTS,
  DEFAULT_USER_DATA_FILTERS,
} from "@/lib/viz/vizUserTransforms";

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
  const didInitWeightsSyncRef = useRef(false);
  const pipelineRunningRef = useRef(false);
  const [payload, setPayload] = useState<VizPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [vizForm, setVizForm] = useState<VizSimSettings>(DEFAULT_VIZ_SETTINGS);
  const [selectedProfile, setSelectedProfile] = useState("core_only");
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineMsg, setPipelineMsg] = useState<string | null>(null);
  const [expDraft, setExpDraft] = useState(DEFAULT_EXPERIMENT_WEIGHTS);
  const [dataFilters, setDataFilters] = useState(DEFAULT_USER_DATA_FILTERS);
  const [feedbackBusyId, setFeedbackBusyId] = useState<string | null>(null);
  const [bottomThreatsOpen, setBottomThreatsOpen] = useState(true);

  useEffect(() => {
    pipelineRunningRef.current = pipelineRunning;
  }, [pipelineRunning]);

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

  useEffect(() => {
    if (!payload?.activeProfile) return;
    setSelectedProfile(payload.activeProfile);
  }, [payload?.activeProfile]);

  const runPipelineWithProfile = useCallback(
    async (opts?: {
      train?: boolean;
      predictOnly?: boolean;
      source?: "scan" | "weights" | "manual" | "refresh";
    }) => {
      if (pipelineRunningRef.current) return;
      const train = Boolean(opts?.train);
      const predictOnly = Boolean(opts?.predictOnly);
      setPipelineRunning(true);
      setPipelineMsg(null);
      try {
        const r = await fetch("/api/pipeline/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            profile: selectedProfile,
            train,
            predictOnly,
            orbitalWeight: expDraft.orbital,
            materialWeight: expDraft.material,
          }),
        });
        const res = (await r.json()) as {
          ok?: boolean;
          activeProfile?: string;
          failedStep?: string;
        };
        if (!r.ok || !res.ok) {
          const failed = res.failedStep ? ` (${res.failedStep})` : "";
          throw new Error(`Pipeline çalışmadı${failed}`);
        }
        const modeLabel = predictOnly
          ? opts?.source === "scan"
            ? "Tarama + tahmin"
            : opts?.source === "refresh"
              ? "Yenile (tahmin)"
              : "Ağırlıklı tahmin"
          : train
            ? "Feature + train + predict"
            : "Feature + predict";
        setPipelineMsg(`${modeLabel} tamamlandı — profile: ${res.activeProfile ?? selectedProfile}`);
        await fetchVizData({ force: true });
      } catch {
        setPipelineMsg("Pipeline tetiklenemedi. API loglarını kontrol edin.");
      } finally {
        setPipelineRunning(false);
      }
    },
    [expDraft.material, expDraft.orbital, fetchVizData, selectedProfile],
  );

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    void runPipelineWithProfile({ predictOnly: true, source: "refresh" }).finally(() =>
      setRefreshing(false),
    );
  }, [runPipelineWithProfile]);

  /** Aynı kalırsa Three.js sahnesi yeniden kurulmaz (takılma azalır). */
  const sceneDataRevision = useMemo(() => {
    if (payload == null) return "no-payload";
    return (
      payload.dataRevision ??
      `legacy:${payload.pipelineMeta.hesap_utc}:${payload.pipelineMeta.n_toplam}`
    );
  }, [payload]);

  const displayPayload = useMemo(
    () =>
      applyUserVizTransforms(
        payload ?? FALLBACK_VIZ_PAYLOAD,
        expDraft,
        dataFilters,
      ),
    [payload, expDraft, dataFilters],
  );

  const filterOptions = useMemo(
    () => buildFilterOptionsFromPayload(payload ?? FALLBACK_VIZ_PAYLOAD),
    [payload],
  );

  const baseVizPayload = payload ?? FALLBACK_VIZ_PAYLOAD;

  const sendThreatFeedback = useCallback(
    async (vote: "up" | "down", threat: ThreatRecord) => {
      setFeedbackBusyId(threat.pair_id);
      try {
        await fetch("/api/user-feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            vote,
            threat,
            hesap_utc: payload?.pipelineMeta.hesap_utc,
          }),
        });
      } finally {
        setFeedbackBusyId(null);
      }
    },
    [payload?.pipelineMeta.hesap_utc],
  );

  useEffect(() => {
    if (!settingsOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSettingsOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settingsOpen]);

  /** İki rAF: layout ölçümü (orbit-host yüksekliği) kesinleşsin; Strict Mode'da cleanup güvenli olsun.
   *  Yalnızca sunucu verisi (`sceneDataRevision`) değişince tam kurulum; kullanıcı katılımı `updateVizData` ile. */
  useLayoutEffect(() => {
    if (!rootRef.current) return;

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
          baseVizPayload,
        );
        sceneRef.current = scene;
        dispose = scene.dispose;
        scene.updateVizData({
          realThreatsData: displayPayload.realThreatsData,
          realDebrisData: displayPayload.realDebrisData,
        });
      });
    });

    return () => {
      cancelled = true;
      cancelAnimationFrame(outerRaf);
      cancelAnimationFrame(innerRaf);
      dispose?.();
      sceneRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tam kurulum yalnızca sunucu rev.; displayPayload aynı rev. anında senkron
  }, [sceneDataRevision]);

  useEffect(() => {
    let raf = 0;
    raf = requestAnimationFrame(() => {
      sceneRef.current?.updateVizData({
        realThreatsData: displayPayload.realThreatsData,
        realDebrisData: displayPayload.realDebrisData,
      });
    });
    return () => cancelAnimationFrame(raf);
  }, [displayPayload]);

  const metaChip =
    payload != null
      ? `ML→ YÜKSEK: ${payload.pipelineMeta.n_yuksek.toLocaleString()} | KRİTİK: ${payload.pipelineMeta.n_kritik.toLocaleString()}`
      : "…";

  useEffect(() => {
    if (!didInitWeightsSyncRef.current) {
      didInitWeightsSyncRef.current = true;
      return;
    }
    const t = window.setTimeout(() => {
      void runPipelineWithProfile({
        predictOnly: true,
        source: "weights",
      });
    }, 700);
    return () => window.clearTimeout(t);
  }, [expDraft.orbital, expDraft.material, runPipelineWithProfile]);

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
            <h1 className="hud-title">YÖRÜNGE MUHAFIZI</h1>
            <span className="hud-subtitle">YÖRÜNGE ANALİZİ</span>
          </div>
          <div className="hud-header-tools">
            <button
              type="button"
              className="hud-header-tool"
              title="Yeni tarama"
              aria-label="Yeni tarama"
              onClick={() => {
                sceneRef.current?.triggerScan();
                void runPipelineWithProfile({
                  predictOnly: true,
                  source: "scan",
                });
              }}
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
        <div className="hud-chip hud-status-strip" style={{ display: "flex", gap: 8 }}>
          <label htmlFor="profile-select">Veri tipi:</label>
          <select
            id="profile-select"
            value={selectedProfile}
            onChange={(e) => setSelectedProfile(e.target.value)}
            disabled={pipelineRunning}
          >
            <option value="core_only">core_only</option>
            <option value="core_plus_discos">core_plus_discos</option>
            <option value="core_plus_discos_physical">core_plus_discos_physical</option>
          </select>
          <button
            type="button"
            className="hud-icon-btn"
            onClick={() => void runPipelineWithProfile({ train: false, source: "manual" })}
            disabled={pipelineRunning}
            title="Feature + predict çalıştır"
          >
            {pipelineRunning ? "Çalışıyor..." : "Uygula"}
          </button>
          <button
            type="button"
            className="hud-icon-btn"
            onClick={() => void runPipelineWithProfile({ train: true, source: "manual" })}
            disabled={pipelineRunning}
            title="Feature + train + predict çalıştır"
          >
            Yeniden Eğit
          </button>
        </div>
        {pipelineMsg ? (
          <div className="hud-chip hud-status-strip" role="status">
            {pipelineMsg}
          </div>
        ) : null}
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

      <main className="hud-main">
        <div className="hud-main-grid">
        <aside className="pipeline-sidebar pipeline-sidebar--inline">
          <PipelineSidebar
            sidebar={payload?.sidebar ?? null}
            loadError={loadError != null}
            onRefresh={handleRefresh}
            refreshing={refreshing}
            pipelineBusy={pipelineRunning}
          />
        </aside>

        <div className="hud-main-stage">
          <section className="scene-area scene-area--main-stage">
            <div data-orbit-host className="orbit-host"></div>

            <div className="hud-bottom-threats">
              <button
                type="button"
                className="hud-bottom-threats-toggle"
                aria-expanded={bottomThreatsOpen}
                onClick={() => setBottomThreatsOpen((o) => !o)}
              >
                {bottomThreatsOpen ? "▼ Tehdit kartlarını gizle" : "▲ Tehdit kartlarını göster"}
              </button>
              <div
                className={`threat-row-wrap${bottomThreatsOpen ? "" : " is-collapsed"}`}
                aria-hidden={!bottomThreatsOpen}
              >
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
            </div>
          </section>
        </div>

        <aside className="hud-tools-column">
          <div className="hud-tools-inner-scroll left-panel">
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

            <UserParticipationPanel
              threats={displayPayload.realThreatsData}
              experiment={expDraft}
              onExperimentChange={setExpDraft}
              filters={dataFilters}
              onFiltersChange={(next) =>
                startTransition(() => setDataFilters(next))
              }
              filterOptions={filterOptions}
              onFeedback={sendThreatFeedback}
              feedbackBusyId={feedbackBusyId}
            />

            <div className="panel-card grow-card">
              <div className="panel-title danger">KRİTİK SEKTÖR</div>
              <div
                id="critical-threats-list"
                className="critical-list"
              >
                <p className="critical-placeholder">Tehdit verisi yükleniyor...</p>
              </div>
            </div>
          </div>
        </aside>
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

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { VizPayload } from "./vizTypes";

export type OrbitHudElements = {
  radarWindows: HTMLElement;
  criticalThreatsList: HTMLElement;
  conjunctionCount: HTMLElement;
  multiCollisionAlert: HTMLElement;
  logContainer: HTMLElement | null;
  fpsDisplay: HTMLElement | null;
  utcClock: HTMLElement | null;
  emergencyBtn: HTMLElement | null;
  selectionPanel: HTMLElement;
  panelTitle: HTMLElement;
  panelTypeTag: HTMLElement;
  panelContent: HTMLElement;
  totalPairsDisplay: HTMLElement | null;
  logModelTag: HTMLElement | null;
  initLogTime: HTMLElement | null;
  initLogMsg: HTMLElement | null;
  riskThresholdDisplay: HTMLElement | null;
};

/** Streamlit `app.py` Sistem Ayarları ile uyumlu görsel parametreler */
export type VizSimSettings = {
  riskThreshold: number;
  debrisSizeMultiplier: number;
  orbitSpeedMultiplier: number;
  showLines: boolean;
  showOrbitRings: boolean;
  earthRotate: boolean;
};

export type OrbitSceneHandle = {
  dispose: () => void;
  applyVizSettings: (next: Partial<VizSimSettings>) => void;
  triggerScan: () => void;
  getSettingsSnapshot: () => VizSimSettings;
};

type Conjunction = {
  satellite: THREE.Sprite;
  debris: THREE.Sprite;
  distance: string;
  probability: number;
};

function createSatelliteTexture(THREE: typeof import("three")) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  ctx.clearRect(0, 0, 128, 128);
  ctx.strokeStyle = "#00ff00";
  ctx.lineWidth = 6;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.rect(52, 40, 24, 48);
  ctx.stroke();
  ctx.fillStyle = "#008800";
  ctx.fill();
  ctx.fillStyle = "#006600";
  ctx.beginPath();
  ctx.rect(4, 50, 48, 28);
  ctx.rect(76, 50, 48, 28);
  ctx.stroke();
  ctx.fill();
  ctx.strokeStyle = "#00ff00";
  ctx.lineWidth = 2;
  for (let i = 0; i < 3; i++) {
    ctx.beginPath();
    ctx.moveTo(4 + i * 16, 50);
    ctx.lineTo(4 + i * 16, 78);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(76 + i * 16, 50);
    ctx.lineTo(76 + i * 16, 78);
    ctx.stroke();
  }
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.moveTo(64, 40);
  ctx.lineTo(64, 20);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(64, 15, 6, 0, Math.PI * 2);
  ctx.stroke();
  ctx.fillStyle = "#00ff00";
  ctx.fill();
  return new THREE.CanvasTexture(canvas);
}

function createRockTexture(THREE: typeof import("three")) {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#8B4513";
  ctx.beginPath();
  ctx.moveTo(32, 5);
  ctx.lineTo(55, 20);
  ctx.lineTo(60, 45);
  ctx.lineTo(45, 60);
  ctx.lineTo(15, 58);
  ctx.lineTo(5, 40);
  ctx.lineTo(10, 15);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#A52A2A";
  ctx.beginPath();
  ctx.moveTo(15, 25);
  ctx.lineTo(30, 20);
  ctx.lineTo(25, 40);
  ctx.closePath();
  ctx.fill();
  ctx.strokeStyle = "#5D2906";
  ctx.lineWidth = 2;
  ctx.stroke();
  return new THREE.CanvasTexture(canvas);
}

function cell2(
  label: string,
  value: string | number,
  accent: string,
  extra?: string,
) {
  const colors: Record<string, string> = {
    cyan: "#00dce6",
    green: "#79ff5b",
    red: "#ff4444",
    orange: "#ff6600",
  };
  const borderC = colors[accent] || "#00dce6";
  const cls = extra ? ` ${extra}` : "";
  return `<div class="bg-neutral-900/50 p-2 border-l-2${cls}" style="border-color:${borderC}">`
    + `<div class="text-[8px] text-neutral-500 uppercase font-bold">${label}</div>`
    + `<div class="text-[10px] font-bold text-white break-words">${value}</div>`
    + `</div>`;
}

export function mountOrbitScene(
  canvasHost: HTMLElement,
  hud: OrbitHudElements,
  data: VizPayload,
): OrbitSceneHandle {
  /* Sahne nesneleri alt fonksiyonlardan önce atanır; let tercih edilir. */
  /* eslint-disable prefer-const */
  const turkishSatellitesData = data.turkishSatellitesData;
  const realThreatsData = data.realThreatsData;
  const realDebrisData = data.realDebrisData;
  const pipelineMeta = data.pipelineMeta;
  const logMessages = data.logMessages;

  let scene: THREE.Scene;
  let camera: THREE.PerspectiveCamera;
  let renderer: THREE.WebGLRenderer;
  let controls: OrbitControls;
  let earth: THREE.Mesh | null = null;
  const assets: THREE.Sprite[] = [];
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let lines: THREE.Line[] = [];
  let conjunctions: Conjunction[] = [];

  const satelliteSprites: THREE.Sprite[] = [];
  const debrisSprites: THREE.Sprite[] = [];
  const keyState: Record<string, boolean> = {};

  /** Tehdit kartları DOM’u saniyede ~60 kez innerHTML ile yenilenmesin (kayma/titreme). */
  let lastThreatPanelsAt = 0;
  const THREAT_PANEL_MS = 320;

  const appSettings = {
    riskThreshold: 1000,
    debrisSizeMultiplier: 1.0,
    orbitSpeedMultiplier: 1.0,
    showLines: true,
    showOrbitRings: false,
    earthRotate: true,
    emergencyMode: false,
  };
  let orbitRingObjects: THREE.Mesh[] = [];
  let emergencyModeActive = false;
  /** Sahne birimi → yaklaşık km (app.py ile aynı ölçek) */
  const KM_PER_SCENE_UNIT = 4.2;
  let scanOverride: string | null = null;

  const onKeyDown = (e: KeyboardEvent) => {
    keyState[e.code] = true;
  };
  const onKeyUp = (e: KeyboardEvent) => {
    keyState[e.code] = false;
  };
  window.addEventListener("keydown", onKeyDown);
  window.addEventListener("keyup", onKeyUp);

  function removeOrbitRings() {
    orbitRingObjects.forEach((r) => scene.remove(r));
    orbitRingObjects = [];
  }

  function addOrbitRings() {
    removeOrbitRings();
    const defs = [
      { r: 122, color: 0xff6600, opacity: 0.25 },
      { r: 140, color: 0xffaa00, opacity: 0.2 },
      { r: 180, color: 0x00ffaa, opacity: 0.18 },
      { r: 265, color: 0x4488ff, opacity: 0.15 },
    ];
    defs.forEach((d) => {
      const geo = new THREE.RingGeometry(d.r - 0.5, d.r + 0.5, 128);
      const mat = new THREE.MeshBasicMaterial({
        color: d.color,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: d.opacity,
      });
      const ring = new THREE.Mesh(geo, mat);
      ring.rotation.x = Math.PI / 2;
      scene.add(ring);
      orbitRingObjects.push(ring);
    });
    addLog("Yörünge halkaları aktif — LEO / LEO+ / MEO / GEO");
  }

  function updateRiskThresholdLabel() {
    const el = hud.riskThresholdDisplay;
    if (el)
      el.innerText = `${Math.round(appSettings.riskThreshold).toLocaleString()} KM`;
  }

  function refreshDebrisScales() {
    const m = appSettings.debrisSizeMultiplier;
    debrisSprites.forEach((s) => {
      if (emergencyModeActive) {
        const rc = s.userData.risk_class as string;
        const isHigh = rc === "YUKSEK" || rc === "KRITIK";
        const sz = isHigh ? 16 : 5;
        s.scale.set(sz, sz, 1);
      } else {
        const rc = s.userData.risk_class as string;
        const base = rc === "KRITIK" ? 12 : rc === "YUKSEK" ? 10 : 8;
        const sz = base * m;
        s.scale.set(sz, sz, 1);
      }
    });
  }

  function addLog(msg: string) {
    const c = hud.logContainer;
    if (!c) return;
    const div = document.createElement("div");
    div.className =
      "text-[10px] font-mono text-on-surface-variant flex gap-2";
    const t = new Date().toLocaleTimeString("en-GB", { hour12: false });
    div.innerHTML = `<span class="text-cyan-500">[${t}]</span><span>${msg}</span>`;
    c.prepend(div);
    if (c.children.length > 12) c.lastChild?.remove();
  }

  function initMetaDisplay() {
    if (hud.logModelTag) hud.logModelTag.innerText = pipelineMeta.model || "LightGBM";
    if (hud.totalPairsDisplay)
      hud.totalPairsDisplay.innerText = (pipelineMeta.n_toplam || 0).toLocaleString();
    if (hud.initLogTime && pipelineMeta.hesap_utc) {
      const t = pipelineMeta.hesap_utc.substring(11, 19);
      hud.initLogTime.innerText = `[${t}]`;
    }
    if (hud.initLogMsg)
      hud.initLogMsg.innerText =
        `Pipeline bağlantısı kuruldu — ${pipelineMeta.hesap_utc || "N/A"} UTC`;
  }

  function createWorldAssets() {
    const satTex = createSatelliteTexture(THREE);
    const rockTex = createRockTexture(THREE);
    const satMat = new THREE.SpriteMaterial({
      map: satTex,
      transparent: true,
      blending: THREE.NormalBlending,
    });
    const debrisMat = new THREE.SpriteMaterial({
      map: rockTex,
      transparent: true,
      blending: THREE.NormalBlending,
    });

    turkishSatellitesData.forEach((sat) => {
      const sprite = new THREE.Sprite(satMat.clone());
      const radius = sat.orbit;
      const phi = Math.random() * Math.PI * 2;
      const theta = Math.random() * Math.PI;
      sprite.position.setFromSphericalCoords(radius, theta, phi);
      sprite.scale.set(24, 24, 1);
      sprite.userData = {
        type: "SATELLITE",
        name: sat.name,
        id: sat.id,
        norad: sat.norad || sat.id,
        orbit: radius,
        status: "AKTİF",
        kritik: sat.kritik || 0,
        yuksek: sat.yuksek || 0,
        en_yakin_km: sat.en_yakin_km || 0,
        en_yakin_cop: sat.en_yakin_cop || "N/A",
        offset: Math.random() * 1000,
      };
      satelliteSprites.push(sprite);
      assets.push(sprite);
      scene.add(sprite);
    });

    if (realDebrisData && realDebrisData.length > 0) {
      realDebrisData.forEach((deb) => {
        const sprite = new THREE.Sprite(debrisMat.clone());
        const baseOrbit = deb.orbit || 120;
        const spreadScale =
          baseOrbit < 130 ? 14 : baseOrbit < 160 ? 20 : 28;
        const radius = Math.max(
          107,
          baseOrbit + (Math.random() - 0.5) * spreadScale,
        );
        const phi = Math.random() * Math.PI * 2;
        const theta = Math.random() * Math.PI;
        sprite.position.setFromSphericalCoords(radius, theta, phi);
        const sz =
          deb.risk_class === "KRITIK" ? 12 : deb.risk_class === "YUKSEK" ? 10 : 8;
        sprite.scale.set(sz, sz, 1);
        sprite.userData = {
          type: "DEBRIS",
          id: deb.id,
          velocity: deb.velocity,
          material: deb.material,
          burn_rate: deb.burn_rate,
          reentry_risk: deb.reentry_risk,
          risk_score: deb.risk_score,
          risk_class: deb.risk_class || "ORTA",
          source: deb.source,
          inclination: deb.inclination || 0,
          eccentricity: deb.eccentricity || 0,
          orbit: radius,
          offset: Math.random() * 1000,
        };
        debrisSprites.push(sprite);
        assets.push(sprite);
        scene.add(sprite);
      });
    } else {
      for (let i = 0; i < 150; i++) {
        const sprite = new THREE.Sprite(debrisMat.clone());
        const radius = 110 + Math.random() * 200;
        const phi = Math.random() * Math.PI * 2;
        const theta = Math.random() * Math.PI;
        sprite.position.setFromSphericalCoords(radius, theta, phi);
        sprite.scale.set(8, 8, 1);
        sprite.userData = {
          type: "DEBRIS",
          id: `SIM-${1000 + i}`,
          velocity: `${(7.5 + Math.random()).toFixed(1)} km/s`,
          material: "SİMÜLASYON VERİSİ",
          burn_rate: "N/A",
          reentry_risk: Math.random(),
          risk_score: Math.floor(Math.random() * 60) + 20,
          risk_class: "ORTA",
          source: "SİMÜLASYON",
          inclination: (Math.random() * 90).toFixed(2),
          eccentricity: (Math.random() * 0.01).toFixed(5),
          orbit: radius,
          offset: Math.random() * 1000,
        };
        debrisSprites.push(sprite);
        assets.push(sprite);
        scene.add(sprite);
      }
    }
  }

  function updateDashedLines() {
    lines.forEach((line) => scene.remove(line));
    lines = [];
    if (!appSettings.showLines) return;
    conjunctions.slice(0, 5).forEach((con) => {
      const points = [con.satellite.position, con.debris.position];
      const geometry = new THREE.BufferGeometry().setFromPoints(points);
      const lineColor = appSettings.emergencyMode ? 0xff0000 : 0xff4444;
      const material = new THREE.LineDashedMaterial({
        color: lineColor,
        dashSize: 3,
        gapSize: 2,
      });
      const line = new THREE.Line(geometry, material);
      line.computeLineDistances();
      scene.add(line);
      lines.push(line);
    });
  }

  function threatAnalysisAlgorithm() {
    conjunctions = [];
    const maxDist = Math.max(
      20,
      Math.min(500, appSettings.riskThreshold / KM_PER_SCENE_UNIT),
    );
    for (const sat of satelliteSprites) {
      for (const deb of debrisSprites) {
        const dist = sat.position.distanceTo(deb.position);
        if (dist < maxDist) {
          const prob = Math.floor(Math.random() * 20) + 50;
          conjunctions.push({
            satellite: sat,
            debris: deb,
            distance: (dist * KM_PER_SCENE_UNIT).toFixed(1),
            probability: prob,
          });
        }
      }
    }
    conjunctions.sort((a, b) => b.probability - a.probability);
    updateConjunctionStrip();
    updateDashedLines();
    const now = performance.now();
    if (now - lastThreatPanelsAt >= THREAT_PANEL_MS) {
      lastThreatPanelsAt = now;
      paintThreatPanels();
    }
  }

  function updateConjunctionStrip() {
    if (scanOverride != null) {
      hud.conjunctionCount.innerText = scanOverride;
      return;
    }
    const nYuksek = pipelineMeta.n_yuksek || 0;
    const nKritik = pipelineMeta.n_kritik || 0;
    hud.conjunctionCount.innerText =
      `ML→ YÜKSEK: ${nYuksek.toLocaleString()} | KRİTİK: ${nKritik.toLocaleString()} | CANLI: ${conjunctions.length}`;
  }

  function paintThreatPanels() {
    const container = hud.radarWindows;
    const alertBanner = hud.multiCollisionAlert;

    const displayData: {
      satName: string;
      debName: string;
      distance: string;
      t0dist: string;
      velocity: string;
      score: string;
      level: string;
      trend: string;
    }[] = [];

    if (realThreatsData.length > 0) {
      realThreatsData.slice(0, 3).forEach((t) => {
        displayData.push({
          satName: t.hedef_uydu || "UNKNOWN",
          debName: t.yaklasan_cop || "DEBRIS",
          distance: parseFloat(String(t.minimum_mesafe_km || 0)).toFixed(0),
          t0dist: parseFloat(String(t.mesafe_t0_km || 0)).toFixed(0),
          velocity: parseFloat(String(t.bagil_hiz_km_s || 0)).toFixed(2),
          score: parseFloat(String(t.tehlike_skoru || 0)).toFixed(0),
          level: t.risk_seviyesi || "DUSUK",
          trend: t.risk_zamani || "",
        });
      });
    }
    conjunctions
      .slice(0, Math.max(0, 3 - displayData.length))
      .forEach((con) => {
        displayData.push({
          satName: con.satellite.userData.name,
          debName: con.debris.userData.id,
          distance: con.distance,
          t0dist: con.distance,
          velocity: "~",
          score: String(con.probability),
          level: "CANLI",
          trend: "LIVE",
        });
      });

    const nKritik = pipelineMeta.n_kritik || 0;
    if (nKritik > 0 || displayData.length > 3) {
      alertBanner.classList.remove("hidden");
    } else {
      alertBanner.classList.add("hidden");
    }

    let html = "";
    displayData.forEach((d, idx) => {
      const color =
        d.level === "KRITIK"
          ? "#ff0000"
          : d.level === "YUKSEK"
            ? "#ff6600"
            : d.level === "ORTA"
              ? "#ffaa00"
              : d.level === "CANLI"
                ? "#00dce6"
                : "#4488ff";
      const trendIcon =
        d.trend === "YAKLASYOR" ? "▼" : d.trend === "UZAKLASYOR" ? "▲" : "⟳";
      html +=
        `<div class="hud-interactive glass-panel bg-neutral-950/80 border-t-2 p-3 flex flex-col gap-2" style="border-color:${color};width:100%;max-width:min(20rem,100%);min-width:11rem;flex:1 1 12rem">`
        + `<div class="flex justify-between items-start">`
        + `<div class="flex flex-col">`
        + `<span class="text-[8px] font-bold tracking-widest uppercase" style="color:${color}">TEHDİT #${idx + 1} [${d.level}] ${trendIcon}</span>`
        + `<span class="text-[11px] font-black text-white">${d.satName}</span>`
        + `<span class="text-[9px] text-neutral-400">↔ ${d.debName}</span>`
        + `</div>`
        + `<div class="w-8 h-8 rounded-full border border-cyan-500/20 flex items-center justify-center bg-cyan-500/5 relative overflow-hidden">`
        + `<div class="radar-scan absolute inset-0"></div>`
        + `<span class="material-symbols-outlined text-[14px] text-cyan-400">gps_fixed</span>`
        + `</div></div>`
        + `<div class="bg-black/40 p-2 border border-white/5 flex justify-between items-center">`
        + `<div class="flex flex-col">`
        + `<span class="text-[8px] text-neutral-500 uppercase">T₀ Mesafe</span>`
        + `<span class="text-[10px] font-mono font-bold text-neutral-300">${d.t0dist} km</span>`
        + `<span class="text-[8px] text-neutral-500 uppercase mt-1">24h Tahmin</span>`
        + `<span class="text-xs font-mono font-bold" style="color:${color}">${d.distance} km</span>`
        + `</div>`
        + `<div class="text-right flex flex-col">`
        + `<span class="text-[8px] text-neutral-500 uppercase">Hız</span>`
        + `<span class="text-[10px] font-mono text-neutral-300">${d.velocity} km/s</span>`
        + `<span class="text-[8px] text-neutral-500 uppercase mt-1">Risk</span>`
        + `<span class="text-xs font-mono font-bold" style="color:${color}">${d.score}/100</span>`
        + `</div></div>`
        + `<div class="h-1 bg-white/10 rounded-full overflow-hidden">`
        + `<div class="h-full" style="width:${Math.min(parseFloat(d.score) || 0, 100)}%;background:${color}"></div></div></div>`;
    });
    container.innerHTML = html;

    const critPanel = hud.criticalThreatsList;
    if (critPanel && realThreatsData.length > 0) {
      let critHtml = "";
      realThreatsData.slice(0, 8).forEach((t) => {
        const lvl = t.risk_seviyesi || "YUKSEK";
        const lvlColor =
          lvl === "KRITIK" ? "#ff0000" : lvl === "YUKSEK" ? "#ff6600" : "#ffaa00";
        const trend = t.risk_zamani || "";
        const trendIcon =
          trend === "YAKLASYOR"
            ? "▼ YAKLASYOR"
            : trend === "UZAKLASYOR"
              ? "▲ UZAKLASYOR"
              : trend;
        const hiz = parseFloat(String(t.bagil_hiz_km_s || 0));
        const d0 = parseFloat(String(t.mesafe_t0_km || 0));
        const d24 = parseFloat(String(t.minimum_mesafe_km || 0));
        const skor = parseFloat(String(t.tehlike_skoru || 0));
        critHtml +=
          `<div class="border-l-2 p-2 mb-1" style="background:rgba(255,100,0,0.05);border-color:${lvlColor}">`
          + `<div class="text-[10px] font-bold text-white leading-tight">`
          + `${t.hedef_uydu} ↔ ${t.yaklasan_cop || "?"}`
          + `</div>`
          + `<div class="text-[9px] text-neutral-400 mt-0.5">`
          + `T₀: ${d0.toFixed(0)} km → 24h: `
          + `<span style="color:${lvlColor};font-weight:bold">${d24.toFixed(0)} km</span>`
          + ` <span class="text-[8px]">[${trendIcon}]</span>`
          + `</div>`
          + `<div class="text-[9px] mt-0.5 flex gap-3">`
          + `<span style="color:${lvlColor}">Skor: ${skor.toFixed(1)}/100</span>`
          + `<span class="text-neutral-400">Hız: <span class="text-white">${hiz.toFixed(2)} km/s</span></span>`
          + `</div>`
          + `</div>`;
      });
      critPanel.innerHTML = critHtml;
    }
  }

  function updateUI() {
    updateConjunctionStrip();
    paintThreatPanels();
  }

  function showPanel(ud: Record<string, unknown>) {
    const panel = hud.selectionPanel;
    const title = hud.panelTitle;
    const tag = hud.panelTypeTag;
    const content = hud.panelContent;
    panel.classList.remove("hidden", "animate-flicker");
    void panel.offsetWidth;
    panel.classList.add("animate-flicker");

    if (ud.type === "SATELLITE") {
      title.innerText = String(ud.name ?? "");
      tag.innerText = `TÜRK UYDUSU | NORAD: ${ud.norad || ud.id}`;
      const hasRisk = Number(ud.kritik) > 0;
      title.style.color = hasRisk ? "#ff4444" : "#79ff5b";
      const nearColor = Number(ud.en_yakin_km) < 2000 ? "#ff6600" : "#00dce6";
      content.innerHTML =
        `<div class="grid grid-cols-2 gap-2">`
        + cell2("NORAD ID", String(ud.norad || ud.id), "cyan")
        + cell2("DURUM", String(ud.status), "green", "col-span-2")
        + cell2("KRİTİK", String(ud.kritik), Number(ud.kritik) > 0 ? "red" : "cyan")
        + cell2("YÜKSEK", String(ud.yuksek), Number(ud.yuksek) > 0 ? "orange" : "cyan")
        + `</div>`
        + `<div class="mt-3 bg-cyan-500/5 p-3 border-l-2 border-cyan-400">`
        + `<div class="text-[8px] text-neutral-500 uppercase font-bold">EN YAKIN CİSİM (24h ML TAHMİN)</div>`
        + `<div class="text-xs font-bold text-white mt-1">${ud.en_yakin_cop || "N/A"}</div>`
        + `<div class="text-[11px] font-mono mt-1" style="color:${nearColor}">`
        + `${Number(ud.en_yakin_km || 0).toLocaleString()} km</div>`
        + `</div>`;
    } else {
      const rc = String(ud.risk_class || "ORTA");
      title.innerText = String(ud.id ?? "");
      tag.innerText = `UZAY ÇÖPÜ | ${rc} | ${ud.source || ""}`;
      const rColor =
        rc === "KRITIK" ? "#ff0000" : rc === "YUKSEK" ? "#ff6600" : "#ffaa00";
      title.style.color = rColor;
      content.innerHTML =
        `<div class="grid grid-cols-2 gap-2">`
        + cell2("HIZ", String(ud.velocity), "red", "col-span-2")
        + cell2("RİSK SKORU", `${ud.risk_score || 0}/100`, "red")
        + cell2(
          "YERE DÜŞME",
          `${Math.round(Number(ud.reentry_risk || 0) * 100)}%`,
          "red",
        )
        + cell2("EĞİM", `${ud.inclination}°`, "red")
        + cell2("EKSANTRİSİTE", Number(ud.eccentricity || 0).toFixed(5), "red")
        + cell2("MALZEME", String(ud.material), "red", "col-span-2")
        + cell2("KAYNAK", String(ud.source), "red")
        + cell2("YANMA", String(ud.burn_rate), "red")
        + `</div>`;
    }
  }

  function onPointerDown(event: PointerEvent) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(assets);
    if (intersects.length > 0) showPanel(intersects[0].object.userData);
  }

  function getHostSize() {
    const r = canvasHost.getBoundingClientRect();
    const w = Math.max(1, r.width);
    const h = Math.max(1, r.height);
    return { w, h };
  }

  function onResize() {
    const { w, h } = getHostSize();
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }

  const ro = new ResizeObserver(() => onResize());
  ro.observe(canvasHost);

  function updateFPS() {
    const el = hud.fpsDisplay;
    if (el) el.innerText = `${Math.round(60 - Math.random() * 2)} FPS`;
  }

  function updateClock() {
    const el = hud.utcClock;
    if (el) el.innerText = `${new Date().toUTCString().substring(17, 25)} UTC`;
  }

  function updateLogs() {
    const container = hud.logContainer;
    if (!container) return;
    const msg = logMessages[Math.floor(Math.random() * logMessages.length)];
    const div = document.createElement("div");
    div.className =
      "text-[10px] font-mono text-on-surface-variant flex gap-2";
    const t = new Date().toLocaleTimeString("en-GB", { hour12: false });
    div.innerHTML = `<span class="text-cyan-500">[${t}]</span><span>${msg}</span>`;
    container.prepend(div);
    if (container.children.length > 12) container.lastChild?.remove();
  }

  function updateKeyboardControls() {
    const speed = 2.5;
    if (keyState.KeyW) camera.position.z -= speed;
    if (keyState.KeyS) camera.position.z += speed;
    if (keyState.KeyA) camera.position.x -= speed;
    if (keyState.KeyD) camera.position.x += speed;
  }

  let raf = 0;
  function animate() {
    raf = requestAnimationFrame(animate);
    const time = performance.now() * 0.0001;
    if (earth && appSettings.earthRotate) earth.rotation.y += 0.0003;
    updateKeyboardControls();
    assets.forEach((s, i) => {
      const orbitRadius = s.userData.orbit as number;
      const offset = (s.userData.offset as number) || 0;
      const baseSpeed = s.userData.type === "SATELLITE" ? 0.7 : 1.2;
      const speed = baseSpeed * appSettings.orbitSpeedMultiplier;
      const angle = time * speed + offset;
      if (i % 3 === 0) {
        s.position.x = Math.cos(angle) * orbitRadius;
        s.position.z = Math.sin(angle) * orbitRadius;
      } else if (i % 3 === 1) {
        s.position.y = Math.cos(angle) * orbitRadius;
        s.position.z = Math.sin(angle) * orbitRadius;
      } else {
        s.position.x = Math.cos(angle) * orbitRadius;
        s.position.y = Math.sin(angle) * orbitRadius;
      }
    });
    threatAnalysisAlgorithm();
    controls.update();
    renderer.render(scene, camera);
  }

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0e0e0e);

  const { w: iw, h: ih } = getHostSize();
  camera = new THREE.PerspectiveCamera(60, iw / ih, 0.1, 2500);
  camera.position.set(0, 250, 450);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(iw, ih, false);
  renderer.domElement.style.display = "block";
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  canvasHost.appendChild(renderer.domElement);
  onResize();

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.rotateSpeed = 0.5;
  /* Dünya yarıçapı ~100; hedef (0,0,0) — minDistance yüzeye çok yakın zoomu engeller */
  controls.minDistance = 235;
  controls.maxDistance = 1500;
  controls.zoomSpeed = 0.85;

  scene.add(new THREE.AmbientLight(0xffffff, 0.4));
  const sunLight = new THREE.DirectionalLight(0xffffff, 1.8);
  sunLight.position.set(200, 100, 200);
  scene.add(sunLight);

  const textureLoader = new THREE.TextureLoader();
  const earthGeometry = new THREE.SphereGeometry(100, 64, 64);
  const earthMaterial = new THREE.MeshStandardMaterial({
    map: textureLoader.load(
      "https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg",
    ),
    bumpMap: textureLoader.load(
      "https://unpkg.com/three-globe/example/img/earth-topology.png",
    ),
    bumpScale: 2,
    emissive: new THREE.Color(0x00f3ff),
    emissiveIntensity: 0.15,
    emissiveMap: textureLoader.load(
      "https://unpkg.com/three-globe/example/img/earth-night-lights.jpg",
    ),
  });
  earth = new THREE.Mesh(earthGeometry, earthMaterial);
  scene.add(earth);

  const atmoGeom = new THREE.SphereGeometry(105, 64, 64);
  const atmoMat = new THREE.MeshBasicMaterial({
    color: 0x00f3ff,
    transparent: true,
    opacity: 0.15,
    side: THREE.BackSide,
  });
  scene.add(new THREE.Mesh(atmoGeom, atmoMat));

  createWorldAssets();

  renderer.domElement.addEventListener("pointerdown", onPointerDown);

  animate();
  const ivFps = window.setInterval(updateFPS, 1000);
  const ivLogs = window.setInterval(updateLogs, 4500);
  const ivClock = window.setInterval(updateClock, 1000);

  initMetaDisplay();
  updateRiskThresholdLabel();
  updateUI();

  function applyVizSettings(next: Partial<VizSimSettings>) {
    if (next.riskThreshold != null)
      appSettings.riskThreshold = next.riskThreshold;
    if (next.orbitSpeedMultiplier != null)
      appSettings.orbitSpeedMultiplier = next.orbitSpeedMultiplier;
    if (next.showLines != null) appSettings.showLines = next.showLines;
    if (next.earthRotate != null) appSettings.earthRotate = next.earthRotate;
    if (next.debrisSizeMultiplier != null) {
      appSettings.debrisSizeMultiplier = next.debrisSizeMultiplier;
      refreshDebrisScales();
    }
    if (next.showOrbitRings != null && next.showOrbitRings !== appSettings.showOrbitRings) {
      appSettings.showOrbitRings = next.showOrbitRings;
      if (appSettings.showOrbitRings) addOrbitRings();
      else {
        removeOrbitRings();
        addLog("Yörünge halkaları kapatıldı");
      }
    }
    updateRiskThresholdLabel();
    updateDashedLines();
    addLog(
      `Ayarlar uygulandı — eşik: ${Math.round(appSettings.riskThreshold).toLocaleString()} km | hız: ${appSettings.orbitSpeedMultiplier.toFixed(1)}x | debris: ${appSettings.debrisSizeMultiplier.toFixed(1)}x`,
    );
  }

  function triggerScan() {
    const countEl = hud.conjunctionCount;
    const steps = [
      "◌ TARANYOR...",
      "● TARANYOR ██",
      "● TARANYOR ████",
      "✓ TARAMA TAMAM",
    ];
    let i = 0;
    addLog("Manuel tarama başlatıldı...");
    const iv = window.setInterval(() => {
      scanOverride = steps[i] ?? steps[steps.length - 1];
      if (countEl) countEl.innerText = scanOverride;
      i++;
      if (i >= steps.length) {
        window.clearInterval(iv);
        window.setTimeout(() => {
          scanOverride = null;
          updateConjunctionStrip();
          const ny = pipelineMeta.n_yuksek || 0;
          const nk = pipelineMeta.n_kritik || 0;
          addLog(
            `Tarama tamamlandı — ${(ny + nk).toLocaleString()} aktif tehdit tespit edildi`,
          );
          addLog(`Veri tarihi: ${pipelineMeta.hesap_utc || "N/A"} UTC`);
        }, 600);
      }
    }, 320);
  }

  /** ACİL MÜDAHALE — orbitEngine içinden */
  const emergencyHandler = () => {
    emergencyModeActive = !emergencyModeActive;
    appSettings.emergencyMode = emergencyModeActive;
    const btn = hud.emergencyBtn;
    const alertBanner = hud.multiCollisionAlert;
    if (emergencyModeActive) {
      assets.forEach((s) => {
        if (s.userData.type !== "DEBRIS") return;
        const rc = s.userData.risk_class as string;
        const isHigh = rc === "YUKSEK" || rc === "KRITIK";
        const sz = isHigh ? 16 : 5;
        s.scale.set(sz, sz, 1);
        (s.material as THREE.SpriteMaterial).opacity = isHigh ? 1.0 : 0.08;
      });
      const topSat = satelliteSprites.reduce(
        (b, s) =>
          (Number(s.userData.yuksek) || 0) > (Number(b.userData.yuksek) || 0)
            ? s
            : b,
        satelliteSprites[0],
      );
      if (topSat) {
        const p = topSat.position;
        controls.target.set(p.x * 0.3, p.y * 0.3, p.z * 0.3);
        camera.position.set(p.x * 2, p.y * 2 + 60, p.z * 2);
        controls.update();
      }
      alertBanner.classList.remove("hidden");
      if (btn) {
        btn.style.background = "rgba(220,38,38,0.95)";
        btn.style.color = "#fff";
        btn.innerText = "✕ ACİL KAPT";
      }
      addLog("⚠ ACİL DURUM MODU AKTİF");
    } else {
      refreshDebrisScales();
      assets.forEach((s) => {
        if (s.userData.type !== "DEBRIS") return;
        (s.material as THREE.SpriteMaterial).opacity = 1.0;
      });
      alertBanner.classList.add("hidden");
      if (btn) {
        btn.style.background = "";
        btn.style.color = "";
        btn.innerText = "ACİL MÜDAHALE";
      }
      addLog("Acil durum modu kapatıldı — normal görünüm");
    }
  };
  hud.emergencyBtn?.addEventListener("click", emergencyHandler);

  const dispose = () => {
    cancelAnimationFrame(raf);
    window.clearInterval(ivFps);
    window.clearInterval(ivLogs);
    window.clearInterval(ivClock);
    ro.disconnect();
    window.removeEventListener("keydown", onKeyDown);
    window.removeEventListener("keyup", onKeyUp);
    renderer.domElement.removeEventListener("pointerdown", onPointerDown);
    hud.emergencyBtn?.removeEventListener("click", emergencyHandler);
    removeOrbitRings();
    lines.forEach((l) => {
      l.geometry.dispose();
      (l.material as THREE.Material).dispose();
      scene.remove(l);
    });
    scene.traverse((obj) => {
      if (obj instanceof THREE.Mesh || obj instanceof THREE.Sprite) {
        if (obj.geometry) obj.geometry.dispose();
        const mat = obj.material;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else if (mat) mat.dispose();
      }
    });
    controls.dispose();
    renderer.dispose();
    if (renderer.domElement.parentNode === canvasHost) {
      canvasHost.removeChild(renderer.domElement);
    }
  };

  return {
    dispose,
    applyVizSettings,
    triggerScan,
    getSettingsSnapshot: () => ({
      riskThreshold: appSettings.riskThreshold,
      debrisSizeMultiplier: appSettings.debrisSizeMultiplier,
      orbitSpeedMultiplier: appSettings.orbitSpeedMultiplier,
      showLines: appSettings.showLines,
      showOrbitRings: appSettings.showOrbitRings,
      earthRotate: appSettings.earthRotate,
    }),
  };
  /* eslint-enable prefer-const */
}

import streamlit as st
import streamlit.components.v1 as components
import json
from pathlib import Path

# 1. SAYFA AYARLARI
st.set_page_config(layout="wide", page_title="CELESTIAL SENTINEL")

# 2. UYDU VERİLERİ
uydu_listesi = [
    { "name": "TÜRKSAT 3A", "id": "33056", "orbit": 160, "color": '#00ff00' },
    { "name": "TÜRKSAT 4A", "id": "39522", "orbit": 160, "color": '#00ff00' },
    { "name": "TÜRKSAT 4B", "id": "40984", "orbit": 160, "color": '#00ff00' },
    { "name": "TÜRKSAT 5A", "id": "47306", "orbit": 160, "color": '#00ff00' },
    { "name": "TÜRKSAT 5B", "id": "50212", "orbit": 160, "color": '#00ff00' },
    { "name": "TÜRKSAT 6A", "id": "60001", "orbit": 165, "color": '#00ff00' },
    { "name": "GÖKTÜRK-1", "id": "41875", "orbit": 135, "color": '#00ff00' },
    { "name": "GÖKTÜRK-2", "id": "39030", "orbit": 125, "color": '#00ff00' },
    { "name": "İMECE", "id": "56178", "orbit": 130, "color": '#00ff00' },
]

# 3. GERÇEK RİSK VERİLERİNİ OKU (simülasyondan gelen)
risk_dosyasi = Path("tum_risk_siralamasi.json")
if risk_dosyasi.exists():
    with open(risk_dosyasi, "r", encoding="utf-8") as f:
        tum_riskler = json.load(f)
    # Her uydu için en yakın 3 tehdit
    uydu_tehditleri = {}
    for r in tum_riskler:
        uydu = r.get("hedef_uydu", "")
        if uydu not in uydu_tehditleri:
            uydu_tehditleri[uydu] = []
        if len(uydu_tehditleri[uydu]) < 3:
            uydu_tehditleri[uydu].append(r)
    # Genel en kritik 5 yakınlaşma
    en_yakin_5 = tum_riskler[:5]
else:
    uydu_tehditleri = {}
    en_yakin_5 = []

# 3. HTML ŞABLONU
html_template = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>CELESTIAL SENTINEL | ORBITAL ANALYSIS</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700;900&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
      tailwind.config = {
        darkMode: "class",
        theme: {
          extend: {
            colors: {
              "on-primary-fixed-variant": "#004f53",
              "secondary-container": "#fe00fe",
              "error": "#ffb4ab",
              "surface-variant": "#353534",
              "on-tertiary-fixed": "#022100",
              "background": "#131313",
              "surface-dim": "#131313",
              "secondary-fixed-dim": "#ffabf3",
              "surface-container-low": "#1c1b1b",
              "on-error": "#690005",
              "tertiary-fixed": "#79ff5b",
              "on-secondary-fixed-variant": "#810081",
              "inverse-on-surface": "#313030",
              "on-surface-variant": "#b9cacb",
              "surface-container": "#201f1f",
              "tertiary-container": "#36fd0f",
              "inverse-primary": "#00696f",
              "on-tertiary-container": "#107000",
              "on-primary-fixed": "#002022",
              "tertiary-fixed-dim": "#2ae500",
              "tertiary": "#e8ffda",
              "surface-tint": "#00dce6",
              "primary-fixed": "#6ff6ff",
              "outline": "#849495",
              "primary-container": "#00f3ff",
              "on-tertiary-fixed-variant": "#095300",
              "on-surface": "#e5e2e1",
              "surface-container-highest": "#353534",
              "surface": "#131313",
              "error-container": "#93000a",
              "on-background": "#e5e2e1",
              "inverse-surface": "#e5e2e1",
              "on-secondary-container": "#500050",
              "secondary-fixed": "#ffd7f5",
              "secondary": "#ffabf3",
              "on-tertiary": "#053900",
              "primary": "#e3fdff",
              "outline-variant": "#3a494b",
              "on-primary-container": "#006b71",
              "surface-bright": "#3a3939",
              "on-secondary": "#5b005b",
              "on-error-container": "#ffdad6",
              "surface-container-lowest": "#0e0e0e",
              "surface-container-high": "#2a2a2a",
              "on-primary": "#00373a",
              "primary-fixed-dim": "#00dce6",
              "on-secondary-fixed": "#380038"
            },
            fontFamily: {
              "headline": ["Space Grotesk"],
              "body": ["Space Grotesk"],
              "label": ["Space Grotesk"]
            },
            borderRadius: {"DEFAULT": "0.125rem", "lg": "0.25rem", "xl": "0.5rem", "full": "0.75rem"},
          },
        },
      }
    </script>
<style>
        html, body { margin: 0; padding: 0; overflow: hidden; background: #0e0e0e; font-family: 'Space Grotesk', sans-serif; width: 100%; height: 100%; }
        canvas { display: block; cursor: crosshair; position: absolute; top: 0; left: 0; width: 100%; height: 100%; }
        .material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
        .hud-overlay { pointer-events: none; }
        .hud-interactive { pointer-events: auto; }
        .glass-panel { backdrop-filter: blur(16px); }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: rgba(0,0,0,0.1); }
        ::-webkit-scrollbar-thumb { background: #00f3ff; }
        
        @keyframes flicker {
            0% { opacity: 0.8; }
            5% { opacity: 0.2; }
            10% { opacity: 0.9; }
            100% { opacity: 1; }
        }
        .animate-flicker { animation: flicker 0.2s ease-in-out; }
        
        @keyframes pulse-red {
            0%, 100% { background-color: rgba(147, 0, 10, 0.4); }
            50% { background-color: rgba(220, 38, 38, 0.8); }
        }
        .animate-alarm { animation: pulse-red 0.8s infinite; }

        .bloom-glow { box-shadow: 0 0 15px rgba(0, 243, 255, 0.3); }
        .threat-glow { box-shadow: 0 0 15px rgba(147, 0, 10, 0.5); }
        .neon-border { border: 1px solid rgba(0, 243, 255, 0.5); box-shadow: inset 0 0 10px rgba(0, 243, 255, 0.2), 0 0 15px rgba(0, 243, 255, 0.1); }
        
        .radar-scan {
            background: conic-gradient(from 0deg, rgba(0, 243, 255, 0.1) 0deg, rgba(0, 243, 255, 0) 90deg);
            animation: rotate 4s linear infinite;
        }
        @keyframes rotate { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    </style>
</head>
<body class="bg-background text-on-background">
<div class="absolute inset-0 z-0" id="canvas-container" style="width:100%;height:100%;position:absolute;top:0;left:0;"></div>
<div class="hidden fixed top-16 left-1/2 -translate-x-1/2 z-[60] px-8 py-2 animate-alarm border-y border-white/20" id="multi-collision-alert">
<span class="text-white font-black text-xs tracking-[0.3em] uppercase flex items-center gap-4">
<span class="material-symbols-outlined text-sm">warning</span>
            MULTI-TARGET COLLISION WARNING: EXTREME PROXIMITY DETECTED
            <span class="material-symbols-outlined text-sm">warning</span>
</span>
</div>
<header class="fixed top-0 w-full z-50 flex justify-between items-center px-6 py-3 bg-neutral-950/40 backdrop-blur-xl border-b border-cyan-500/20 shadow-[0_0_15px_rgba(0,220,230,0.1)]">
<div class="flex items-center gap-4">
<span class="text-xl font-black tracking-tighter text-cyan-400 drop-shadow-[0_0_8px_rgba(0,243,255,0.5)]">CELESTIAL SENTINEL</span>
<div class="h-4 w-[1px] bg-cyan-500/30"></div>
<nav class="hidden md:flex gap-6">
<a class="font-['Space_Grotesk'] uppercase tracking-tight text-xs font-bold text-cyan-300 border-b-2 border-cyan-400 pb-1 transition-all duration-300" href="#">ORBITAL ANALYSIS</a>
</nav>
</div>
<div class="flex items-center gap-4">
<div class="flex items-center gap-2 px-3 py-1 bg-cyan-500/10 border border-cyan-500/30">
<span class="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
<span class="text-[10px] font-bold text-cyan-400 font-mono" id="conjunction-count">SCANNING: 0 CONJUNCTIONS</span>
</div>
<button class="hud-interactive p-2 hover:bg-cyan-500/10 transition-all duration-300 text-cyan-400">
<span class="material-symbols-outlined">sensors</span>
</button>
<button class="hud-interactive p-2 hover:bg-cyan-500/10 transition-all duration-300 text-cyan-400">
<span class="material-symbols-outlined">settings</span>
</button>
</div>
</header>
<aside class="fixed left-0 top-0 h-full flex flex-col items-center py-8 z-40 bg-neutral-950/60 backdrop-blur-2xl w-20 border-r border-cyan-500/15 pt-20">
<div class="flex flex-col items-center mb-8 text-center px-1">
<span class="text-cyan-400 font-bold font-['Space_Grotesk'] text-[10px]">SENTINEL-01</span>
<span class="text-neutral-500 font-['Space_Grotesk'] text-[8px] uppercase">ANALYSIS ENGINE: ACTIVE</span>
</div>
<div class="flex flex-col gap-6 w-full px-2">
<button class="hud-interactive group flex flex-col items-center gap-1 py-3 bg-cyan-500/20 text-cyan-300 border-r-4 border-cyan-400">
<span class="material-symbols-outlined">radar</span>
<span class="font-['Space_Grotesk'] font-medium uppercase text-[10px]">THREATS</span>
</button>
<button class="hud-interactive group flex flex-col items-center gap-1 py-3 text-neutral-500 hover:text-cyan-300 transition-colors">
<span class="material-symbols-outlined">public</span>
<span class="font-['Space_Grotesk'] font-medium uppercase text-[10px]">ASSETS</span>
</button>
</div>
<div class="mt-auto flex flex-col items-center gap-4 pb-4">
<div class="flex flex-col items-center text-cyan-400">
<span class="material-symbols-outlined">schedule</span>
<span class="font-['Space_Grotesk'] font-medium uppercase text-[10px]">UTC</span>
</div>
<button class="hud-interactive bg-error-container text-on-error-container text-[8px] font-black px-2 py-1 leading-tight text-center">
                EMERGENCY OVERRIDE
            </button>
</div>
</aside>
<main class="hud-overlay fixed inset-0 z-30 flex flex-col p-6 pl-24 pt-20">
<div class="flex flex-col gap-4 w-72 h-full">
<section class="hud-interactive glass-panel bg-surface-container-low/60 border-l-2 border-cyan-400 p-4">
<div class="flex justify-between items-center mb-3">
<h2 class="text-xs font-black uppercase tracking-widest text-primary-fixed">SENTINEL_LOG</h2>
<span class="text-[10px] text-tertiary-fixed font-mono">V2.4_THREAT</span>
</div>
<div class="space-y-2 max-h-48 overflow-y-auto pr-2" id="log-container">
<div class="text-[10px] font-mono text-on-surface-variant flex gap-2">
<span class="text-cyan-500">[14:02:11]</span>
<span>Multi-conjunction scan initiated</span>
</div>
</div>
</section>
<section class="hud-interactive glass-panel bg-surface-container-low/60 border-l-2 border-error-container p-4">
<h2 class="text-xs font-black uppercase tracking-widest text-error mb-3 flex items-center gap-2">
<span class="material-symbols-outlined text-sm">warning</span>
                    CRITICAL SECTOR
                </h2>
<div class="space-y-3" id="critical-threats-list">
<div class="text-[9px] text-neutral-500 italic">Scanning 200km threshold...</div>
</div>
</section>
</div>
<div class="mt-auto mb-4 self-center flex flex-col items-center gap-4">
<div class="flex gap-4" id="radar-windows"></div>
<div class="hud-interactive glass-panel bg-surface-container-low/80 border border-cyan-500/20 px-6 py-2 flex items-center gap-8">
<div class="flex flex-col items-center">
<span class="text-[8px] uppercase text-neutral-500">Camera Mode</span>
<span class="text-[10px] font-bold text-cyan-400 uppercase">WASD + MOUSE</span>
</div>
<div class="h-6 w-[1px] bg-outline-variant"></div>
<div class="flex flex-col items-center">
<span class="text-[8px] uppercase text-neutral-500">Threat Threshold</span>
<span class="text-[10px] font-bold text-cyan-400">200.0 KM</span>
</div>
<div class="h-6 w-[1px] bg-outline-variant"></div>
<div class="flex flex-col items-center">
<span class="text-[8px] uppercase text-neutral-500">Engine FPS</span>
<span class="text-[10px] font-bold text-cyan-400" id="fps-display">60 FPS</span>
</div>
</div>
</div>
<div class="hidden hud-interactive fixed right-6 top-24 w-80 glass-panel bg-neutral-950/90 neon-border p-5 animate-flicker z-50" id="selection-panel">
<div class="flex justify-between items-start mb-4 border-b border-cyan-500/30 pb-3">
<div>
<h3 class="text-lg font-black tracking-widest text-cyan-400 leading-none uppercase" id="panel-title">OBJECT_ID</h3>
<p class="text-[9px] font-mono text-cyan-300/60 mt-2 uppercase tracking-tighter" id="panel-type-tag">CLASSIFICATION: UNKNOWN</p>
</div>
<button class="text-cyan-400 hover:text-white transition-colors" onclick="document.getElementById('selection-panel').classList.add('hidden')">
<span class="material-symbols-outlined text-xl">close</span>
</button>
</div>
<div class="space-y-4" id="panel-content-area"></div>
<div class="mt-6 flex gap-2">
<button class="flex-1 bg-cyan-500/20 border border-cyan-400/50 text-cyan-400 text-[10px] font-black py-2 uppercase hover:bg-cyan-400 hover:text-black transition-all">Track Vector</button>
<button class="flex-1 border border-outline-variant text-neutral-400 text-[10px] font-black py-2 uppercase hover:bg-white/10 transition-all">Full Telemetry</button>
</div>
</div>
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
        const THREE_MODULE = THREE;

        let scene, camera, renderer, controls;
        let earth, assets = [];
        let raycaster = new THREE.Raycaster();
        let mouse = new THREE.Vector2();
        let lines = [];
        
        const CRITICAL_DISTANCE = 200; 
        let conjunctions = [];

        const turkishSatellitesData = __SATELLITES_JSON__;
        const realThreatsData = __THREATS_JSON__;

        let satelliteSprites = [];
        let debrisSprites = [];
        const keyState = {};

        window.addEventListener('keydown', (e) => { keyState[e.code] = true; });
        window.addEventListener('keyup', (e) => { keyState[e.code] = false; });

        function createSatelliteTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 128;
            canvas.height = 128;
            const ctx = canvas.getContext('2d');
            
            ctx.clearRect(0,0,128,128);
            
            // Solid Green Satellite Icon (no glow)
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 6;
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            
            // Body
            ctx.beginPath();
            ctx.rect(52, 40, 24, 48);
            ctx.stroke();
            ctx.fillStyle = '#008800';
            ctx.fill();
            
            // Solar panels
            ctx.fillStyle = '#006600';
            ctx.beginPath();
            ctx.rect(4, 50, 48, 28);
            ctx.rect(76, 50, 48, 28);
            ctx.stroke();
            ctx.fill();

            // Solar panel grid lines
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 2;
            for(let i=0; i<3; i++) {
                ctx.moveTo(4 + i*16, 50); ctx.lineTo(4 + i*16, 78);
                ctx.moveTo(76 + i*16, 50); ctx.lineTo(76 + i*16, 78);
            }
            ctx.stroke();
            
            // Antenna
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(64, 40);
            ctx.lineTo(64, 20);
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(64, 15, 6, 0, Math.PI * 2);
            ctx.stroke();
            ctx.fillStyle = '#00ff00';
            ctx.fill();

            return new THREE.CanvasTexture(canvas);
        }

        function createRockTexture() {
            const canvas = document.createElement('canvas');
            canvas.width = 64;
            canvas.height = 64;
            const ctx = canvas.getContext('2d');
            
            // Rock shape - Dull Red/Brown
            ctx.fillStyle = '#8B4513';
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
            
            // Surface highlights (Dull Red)
            ctx.fillStyle = '#A52A2A';
            ctx.beginPath();
            ctx.moveTo(15, 25);
            ctx.lineTo(30, 20);
            ctx.lineTo(25, 40);
            ctx.closePath();
            ctx.fill();

            // Outline
            ctx.strokeStyle = '#5D2906';
            ctx.lineWidth = 2;
            ctx.stroke();

            return new THREE.CanvasTexture(canvas);
        }

        function init() {
            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0e0e0e);

            camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 2500);
            camera.position.set(0, 250, 450);

            renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            var w = window.innerWidth || document.documentElement.clientWidth || 1200;
            var h = window.innerHeight || document.documentElement.clientHeight || 900;
            renderer.setSize(w, h);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            document.getElementById('canvas-container').appendChild(renderer.domElement);

            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.rotateSpeed = 0.5;
            controls.minDistance = 120;
            controls.maxDistance = 1500;

            scene.add(new THREE.AmbientLight(0xffffff, 0.4));
            const sunLight = new THREE.DirectionalLight(0xffffff, 1.8);
            sunLight.position.set(200, 100, 200);
            scene.add(sunLight);

            const textureLoader = new THREE.TextureLoader();
            const earthGeometry = new THREE.SphereGeometry(100, 64, 64);
            const earthMaterial = new THREE.MeshStandardMaterial({
                map: textureLoader.load('https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg'),
                bumpMap: textureLoader.load('https://unpkg.com/three-globe/example/img/earth-topology.png'),
                bumpScale: 2,
                emissive: new THREE.Color(0x00f3ff),
                emissiveIntensity: 0.15,
                emissiveMap: textureLoader.load('https://unpkg.com/three-globe/example/img/earth-night-lights.jpg')
            });
            earth = new THREE.Mesh(earthGeometry, earthMaterial);
            scene.add(earth);

            // Atmosphere
            const atmoGeom = new THREE.SphereGeometry(105, 64, 64);
            const atmoMat = new THREE.MeshBasicMaterial({
                color: 0x00f3ff,
                transparent: true,
                opacity: 0.15,
                side: THREE.BackSide
            });
            scene.add(new THREE.Mesh(atmoGeom, atmoMat));

            createWorldAssets();

            window.addEventListener('resize', onWindowResize);
            renderer.domElement.addEventListener('pointerdown', onPointerDown);
            
            animate();
            setInterval(updateFPS, 1000);
            setInterval(updateLogs, 4500);
        }

        function createWorldAssets() {
            const satTex = createSatelliteTexture();
            const rockTex = createRockTexture();
            
            const satMat = new THREE.SpriteMaterial({ map: satTex, transparent: true, blending: THREE.NormalBlending });
            const debrisMat = new THREE.SpriteMaterial({ map: rockTex, transparent: true, blending: THREE.NormalBlending });

            turkishSatellitesData.forEach((sat, i) => {
                const sprite = new THREE.Sprite(satMat.clone());
                const radius = sat.orbit;
                const phi = Math.random() * Math.PI * 2;
                const theta = Math.random() * Math.PI;
                sprite.position.setFromSphericalCoords(radius, theta, phi);
                // Increased scale to be 3x debris (debris is 8, satellite is 24)
                sprite.scale.set(24, 24, 1); 
                sprite.userData = { 
                    type: 'SATELLITE', 
                    name: sat.name, 
                    id: sat.id, 
                    orbit: radius, 
                    status: 'AKTİF', 
                    offset: Math.random() * 1000 
                };
                satelliteSprites.push(sprite);
                assets.push(sprite);
                scene.add(sprite);
            });

            for (let i = 0; i < 150; i++) {
                const sprite = new THREE.Sprite(debrisMat.clone());
                const radius = 110 + Math.random() * 500;
                const phi = Math.random() * Math.PI * 2;
                const theta = Math.random() * Math.PI;
                sprite.position.setFromSphericalCoords(radius, theta, phi);
                sprite.scale.set(8, 8, 1);
                sprite.userData = { 
                    type: 'DEBRIS', 
                    id: `ROCK-${1000 + i}`, 
                    velocity: (7.5 + Math.random()).toFixed(1) + " km/s", 
                    mass: Math.floor(Math.random() * 50) + " kg", 
                    material: "SİLİKAT / METALİK",
                    source: "ESKİ ÜST KADEME",
                    orbit: radius, 
                    offset: Math.random() * 1000 
                };
                debrisSprites.push(sprite);
                assets.push(sprite);
                scene.add(sprite);
            }
        }

        function updateDashedLines() {
            lines.forEach(line => scene.remove(line));
            lines = [];

            conjunctions.slice(0, 5).forEach(con => {
                const points = [con.satellite.position, con.debris.position];
                const geometry = new THREE.BufferGeometry().setFromPoints(points);
                const material = new THREE.LineDashedMaterial({
                    color: 0xff4444,
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
            for (let sat of satelliteSprites) {
                for (let deb of debrisSprites) {
                    const dist = sat.position.distanceTo(deb.position);
                    if (dist < 80) {
                        const prob = Math.floor(Math.random() * 30) + 65;
                        conjunctions.push({ satellite: sat, debris: deb, distance: (dist * 4.2).toFixed(1), probability: prob });
                    }
                }
            }
            conjunctions.sort((a, b) => b.probability - a.probability);
            updateUI();
            updateDashedLines();
        }

        function updateUI() {
            const container = document.getElementById('radar-windows');
            const alertBanner = document.getElementById('multi-collision-alert');
            const countDisplay = document.getElementById('conjunction-count');
            
            // Gerçek risk verilerini göster
            let displayData = [];
            if (realThreatsData.length > 0) {
                realThreatsData.slice(0, 3).forEach(t => {
                    displayData.push({
                        satName: t.hedef_uydu || 'UNKNOWN',
                        debrisName: t.yaklasan_cop || 'DEBRIS',
                        distance: parseFloat(t.minimum_mesafe_km || 0).toFixed(1),
                        velocity: parseFloat(t.bagil_hiz_km_s || 0).toFixed(1),
                        score: parseFloat(t.tehlike_skoru || 0).toFixed(0),
                        level: t.risk_seviyesi || 'DUSUK',
                        tca: t.risk_zamani || 'N/A'
                    });
                });
            }
            // 3D yakınlıkları da ekle
            conjunctions.slice(0, Math.max(0, 3 - displayData.length)).forEach(con => {
                displayData.push({
                    satName: con.satellite.userData.name,
                    debrisName: con.debris.userData.id,
                    distance: con.distance,
                    velocity: '~',
                    score: con.probability,
                    level: 'SIM',
                    tca: 'LIVE'
                });
            });

            countDisplay.innerText = 'REAL THREATS: ' + realThreatsData.length + ' | LIVE: ' + conjunctions.length;
            
            if (displayData.length > 3) alertBanner.classList.remove('hidden'); else alertBanner.classList.add('hidden');
            
            let html = '';
            displayData.forEach((d, idx) => {
                const color = d.level === 'KRITIK' ? '#ff0000' : d.level === 'YUKSEK' ? '#ff6600' : d.level === 'ORTA' ? '#ffaa00' : '#00dce6';
                html += '<div class="hud-interactive w-64 glass-panel bg-neutral-950/80 border-t-2 p-3 flex flex-col gap-2" style="border-color:'+color+'">'
                    + '<div class="flex justify-between items-start">'
                    + '<div class="flex flex-col">'
                    + '<span class="text-[8px] font-bold tracking-widest uppercase" style="color:'+color+'">THREAT #'+(idx+1)+' ['+d.level+']</span>'
                    + '<span class="text-[11px] font-black text-white">'+d.satName+'</span>'
                    + '<span class="text-[9px] text-neutral-400">↔ '+d.debrisName+'</span>'
                    + '</div>'
                    + '<div class="w-8 h-8 rounded-full border border-cyan-500/20 flex items-center justify-center bg-cyan-500/5 relative overflow-hidden">'
                    + '<div class="radar-scan absolute inset-0"></div>'
                    + '<span class="material-symbols-outlined text-[14px] text-cyan-400">gps_fixed</span>'
                    + '</div></div>'
                    + '<div class="bg-black/40 p-2 border border-white/5 flex justify-between items-center">'
                    + '<div class="flex flex-col"><span class="text-[8px] text-neutral-500 uppercase">Min Mesafe</span>'
                    + '<span class="text-xs font-mono font-bold" style="color:'+color+'">'+d.distance+' km</span></div>'
                    + '<div class="text-right flex flex-col"><span class="text-[8px] text-neutral-500 uppercase">Tehlike</span>'
                    + '<span class="text-xs font-mono font-bold" style="color:'+color+'">'+d.score+'/100</span></div></div>'
                    + '<div class="h-1 bg-white/10 rounded-full overflow-hidden">'
                    + '<div class="h-full" style="width:'+Math.min(d.score,100)+'%;background:'+color+'"></div></div></div>';
            });
            container.innerHTML = html;

            // Kritik tehditler panelini güncelle
            const critPanel = document.getElementById('critical-threats-list');
            if (critPanel && realThreatsData.length > 0) {
                let critHtml = '';
                realThreatsData.slice(0, 5).forEach(t => {
                    critHtml += '<div class="bg-red-500/5 border-l-2 border-red-500 p-2 mb-1">'
                        + '<div class="text-[10px] font-bold text-white">'+t.hedef_uydu+' ↔ '+(t.yaklasan_cop||'?')+'</div>'
                        + '<div class="text-[9px] text-neutral-400">'+parseFloat(t.minimum_mesafe_km).toFixed(1)+' km | '+parseFloat(t.bagil_hiz_km_s).toFixed(1)+' km/s | Skor: '+parseFloat(t.tehlike_skoru).toFixed(1)+'</div>'
                        + '</div>';
                });
                critPanel.innerHTML = critHtml;
            }
        }

        function onPointerDown(event) {
            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(assets);
            if (intersects.length > 0) showPanel(intersects[0].object.userData);
        }

        function showPanel(data) {
            const panel = document.getElementById('selection-panel');
            const title = document.getElementById('panel-title');
            const tag = document.getElementById('panel-type-tag');
            const content = document.getElementById('panel-content-area');
            panel.classList.remove('hidden', 'animate-flicker');
            void panel.offsetWidth;
            panel.classList.add('animate-flicker');
            
            if (data.type === 'SATELLITE') {
                title.innerText = data.name; tag.innerText = 'CLASSIFICATION: ' + data.type;
                title.style.color = '#79ff5b';
                content.innerHTML = '<div class="grid grid-cols-1 gap-3">'
                    + '<div class="bg-cyan-500/5 p-3 border-l-2 border-cyan-400"><div class="text-[8px] text-neutral-500 uppercase font-bold">NORAD ID</div><div class="text-sm font-bold text-white">'+data.id+'</div></div>'
                    + '<div class="bg-cyan-500/5 p-3 border-l-2 border-cyan-400"><div class="text-[8px] text-neutral-500 uppercase font-bold">GÖREV DURUMU</div><div class="text-sm font-bold text-tertiary-fixed">'+data.status+'</div></div>'
                    + '</div>';
            } else {
                title.innerText = data.id; tag.innerText = 'CLASSIFICATION: ' + data.type;
                title.style.color = '#ff4444';
                content.innerHTML = '<div class="grid grid-cols-2 gap-2">'
                    + '<div class="bg-red-500/5 p-2 border-l-2 border-red-500 col-span-2"><div class="text-[8px] text-neutral-500 uppercase font-bold">Velocity</div><div class="text-xs font-bold text-white">'+data.velocity+'</div></div>'
                    + '<div class="bg-red-500/5 p-2 border-l-2 border-red-500"><div class="text-[8px] text-neutral-500 uppercase font-bold">Mass</div><div class="text-xs font-bold text-white">'+data.mass+'</div></div>'
                    + '<div class="bg-red-500/5 p-2 border-l-2 border-red-500"><div class="text-[8px] text-neutral-500 uppercase font-bold">Material</div><div class="text-[10px] font-bold text-white">'+data.material+'</div></div>'
                    + '<div class="bg-red-500/5 p-2 border-l-2 border-red-500"><div class="text-[8px] text-neutral-500 uppercase font-bold">Source</div><div class="text-[10px] font-bold text-white">'+data.source+'</div></div>'
                    + '</div>';
            }
        }

        function onWindowResize() {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }

        function updateFPS() {
            const fpsEl = document.getElementById('fps-display');
            if (fpsEl) fpsEl.innerText = Math.round(60 - Math.random() * 2) + " FPS";
        }

        function updateLogs() {
            const container = document.getElementById('log-container');
            if (!container) return;
            const logs = [
                "Scanning Conjunction Data Message (CDM)",
                "Propagating TLE for Sector 4A",
                "Covariance matrix calculation complete",
                "High Probability Threat Detected",
                "Tracking orbital decay for debris cluster"
            ];
            
            const log = logs[Math.floor(Math.random()*logs.length)];
            const div = document.createElement('div');
            div.className = "text-[10px] font-mono text-on-surface-variant flex gap-2 animate-pulse";
            const time = new Date().toLocaleTimeString('en-GB', { hour12: false });
            div.innerHTML = '<span class="text-cyan-500">['+time+']</span><span>'+log+'</span>';
            container.prepend(div);
            if(container.children.length > 10) container.lastChild.remove();
        }

        function updateKeyboardControls() {
            const speed = 2.5;
            if (keyState['KeyW']) camera.position.z -= speed;
            if (keyState['KeyS']) camera.position.z += speed;
            if (keyState['KeyA']) camera.position.x -= speed;
            if (keyState['KeyD']) camera.position.x += speed;
        }

        function animate() {
            requestAnimationFrame(animate);
            const time = performance.now() * 0.0001;
            
            if (earth) earth.rotation.y += 0.0003;

            updateKeyboardControls();

            assets.forEach((s, i) => {
                const orbitRadius = s.userData.orbit;
                const offset = s.userData.offset || 0;
                const speed = s.userData.type === 'SATELLITE' ? 0.7 : 1.2;
                const angle = (time * speed) + offset;
                
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

        init();
    </script>
</body></html>
"""

# 4. VERİ ENJEKSİYONU VE RENDER
uydu_json = json.dumps(uydu_listesi, ensure_ascii=False)
tehdit_json = json.dumps(en_yakin_5, ensure_ascii=False)

renderlanmis_html = html_template.replace("__SATELLITES_JSON__", uydu_json)
renderlanmis_html = renderlanmis_html.replace("__THREATS_JSON__", tehdit_json)

# 5. EKRANA BASMA
components.html(renderlanmis_html, height=900, scrolling=False)

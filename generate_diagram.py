"""
Space Debris Tracking Model — Mimari Diyagram Üretici
Çalıştır: python generate_diagram.py
Çıktı:    architecture_diagram.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.font_manager as fm

EMOJI_FONT = "Segoe UI Emoji"
_ep = fm.FontProperties(family=EMOJI_FONT)

# ── Renk paleti ───────────────────────────────────────────────────────────────
C_BG       = "#FFFFFF"
C_SRC      = "#1A73E8"   # veri kaynakları — mavi
C_PIPE     = "#7B2FBE"   # pipeline — mor
C_FILE     = "#00875A"   # dosyalar — yeşil
C_DASH     = "#E37400"   # dashboard — turuncu
C_DOCKER   = "#2496ED"   # Docker — Docker mavisi
C_GCP      = "#4285F4"   # Google Cloud — mavi
C_K8S      = "#326CE5"   # Kubernetes — k8s mavisi
C_RUN      = "#34A853"   # Cloud Run / çıktı — yeşil
C_GRAY     = "#5F6368"
C_DARK     = "#1C1C1C"
C_WHITE    = "#FFFFFF"

fig, ax = plt.subplots(figsize=(24, 20))
fig.patch.set_facecolor(C_BG)
ax.set_facecolor(C_BG)
ax.set_xlim(0, 24)
ax.set_ylim(0, 20)
ax.axis("off")

# ── Yardımcı fonksiyonlar ──────────────────────────────────────────────────────

def box(x, y, w, h, color, text, fs=9, tc=C_WHITE,
        icon=None, sub=None, alpha=1.0, border_only=False):
    fc = "none" if border_only else color
    p = FancyBboxPatch(
        (x - w/2, y - h/2), w, h,
        boxstyle="round,pad=0.05,rounding_size=0.25",
        linewidth=2 if border_only else 1.5,
        edgecolor=color, facecolor=fc, alpha=alpha, zorder=3
    )
    ax.add_patch(p)
    text_color = color if border_only else tc
    if icon:
        ax.text(x, y + 0.2, icon, ha="center", va="center",
                fontsize=fs + 8, zorder=4, fontproperties=_ep)
        ty = y - 0.2
    else:
        ty = y + (0.08 if sub else 0)
    ax.text(x, ty, text, ha="center", va="center",
            fontsize=fs, color=text_color, fontweight="bold",
            zorder=4, linespacing=1.4)
    if sub:
        ax.text(x, y - h/2 + 0.28, sub, ha="center", va="center",
                fontsize=6.8, color=text_color, alpha=0.85,
                zorder=4, style="italic")

def badge(x, y, label, color=C_FILE, w=2.4):
    p = FancyBboxPatch(
        (x - w/2, y - 0.22), w, 0.44,
        boxstyle="round,pad=0.04,rounding_size=0.12",
        linewidth=1.2, edgecolor=color, facecolor=color + "22", zorder=3
    )
    ax.add_patch(p)
    ax.text(x, y, label, ha="center", va="center",
            fontsize=7, color=color, fontweight="bold", zorder=4)

def arrow(x1, y1, x2, y2, color=C_GRAY, rad=0.0, lw=1.8, style="-|>"):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle=style, color=color, lw=lw,
            connectionstyle=f"arc3,rad={rad}",
            mutation_scale=14,
        ),
        zorder=2
    )

def hline(y, x1=0.5, x2=23.5, color="#E8E8E8", lw=1):
    ax.plot([x1, x2], [y, y], color=color, lw=lw, zorder=1)

def layer_label(x, y, text, color):
    ax.text(x, y, text, ha="left", va="center",
            fontsize=8.5, color=color, fontweight="bold",
            alpha=0.7, style="italic", zorder=5)

def container(x0, y0, x1, y1, color, label=""):
    p = FancyBboxPatch(
        (x0, y0), x1 - x0, y1 - y0,
        boxstyle="round,pad=0.1,rounding_size=0.3",
        linewidth=2, edgecolor=color,
        facecolor=color + "10", zorder=1
    )
    ax.add_patch(p)
    if label:
        ax.text(x0 + 0.18, y1 - 0.22, label, ha="left", va="center",
                fontsize=7.5, color=color, fontweight="bold",
                alpha=0.8, zorder=2)

# ═══════════════════════════════════════════════════════════════════════════════
# BAŞLIK
# ═══════════════════════════════════════════════════════════════════════════════
ax.text(12, 19.55,
        "Space Debris Tracking & Risk Prediction — Sistem Mimarisi",
        ha="center", va="center", fontsize=17, fontweight="bold", color=C_DARK)
hline(19.2)

# ═══════════════════════════════════════════════════════════════════════════════
# KATMAN 1 — VERİ KAYNAKLARI
# ═══════════════════════════════════════════════════════════════════════════════
layer_label(0.6, 18.75, "① VERİ KAYNAKLARI", C_SRC)

box(4.0, 18.1, 3.2, 1.0, C_SRC, "Space-Track.org", fs=10,
    icon="🛰️", sub="TLE Katalog API")
badge(4.0, 17.4, "cop_verileri.json", C_SRC, w=2.6)

box(9.5, 18.1, 3.2, 1.0, C_SRC, "Manuel TLE\nGüncelleme", fs=9,
    icon="✏️", sub="turk_uydulari.json")
badge(9.5, 17.4, "turk_uydulari.json", C_SRC, w=2.6)

# kaynaklar → pipeline
arrow(4.0, 17.18, 6.5, 15.85, C_SRC, rad=0.15)
arrow(9.5, 17.18, 6.5, 15.85, C_SRC, rad=-0.15)

# ═══════════════════════════════════════════════════════════════════════════════
# KATMAN 2 — ML PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
layer_label(0.6, 16.1, "② ML PIPELINE  (main.py)", C_PIPE)
container(0.3, 8.8, 13.0, 15.7, C_PIPE, "ML Pipeline  ·  main.py")

STEPS = [
    ("📄", "Step 0", "cop_verileri_to_csv.py",   "cop_verileri_enriched.csv"),
    ("🧹", "Step 1", "step00_clean_data.py",      "cop_verileri_cleaned.csv"),
    ("⚙️",  "Step 2", "build_real_encounters.py   [SGP4]",
                                                   "encounters_24h.csv  (156k satır)"),
    ("📊", "Step 3", "step02_build_features.py",  "ml_features_24h.csv  (22 özellik)"),
    ("🤖", "Step 4", "step03_train_baseline.py   [LightGBM]",
                                                   "lightgbm_risk_modeli.pkl  ·  R²=0.981"),
    ("🎯", "Step 5", "predict_risk.py",
     "risk_tahmin_tum.csv (156k) · risk_tahmin_kritik.csv (2,259) · simul.json"),
]

sy0    = 15.2
s_gap  = 1.1

for i, (icon, step, name, out) in enumerate(STEPS):
    sy = sy0 - i * s_gap
    ax.text(1.1, sy, icon, ha="center", va="center",
            fontsize=15, zorder=4, fontproperties=_ep)
    box(6.5, sy, 10.4, 0.62, C_PIPE, f"{step}:  {name}", fs=8.5)
    badge(6.5, sy - 0.53, out, C_FILE, w=10.0)
    if i < len(STEPS) - 1:
        arrow(6.5, sy - 0.62/2, 6.5, sy - s_gap + 0.62/2,
              C_PIPE, rad=0.0, lw=1.4)

# pipeline → dashboard oku
arrow(13.0, 11.9, 14.2, 11.9, C_PIPE, rad=0.0, lw=2.2)

# ═══════════════════════════════════════════════════════════════════════════════
# KATMAN 3 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
layer_label(13.6, 13.5, "③ DASHBOARD  (app.py / Streamlit)", C_DASH)
container(13.8, 9.6, 23.5, 13.3, C_DASH, "app.py  ·  Streamlit")

DASH_SUB = [
    (16.5, 12.2, "🐍", "Python Layer",     "Veri oku → JSON enjekte"),
    (19.5, 12.2, "🌐", "Three.js / HUD",   "3D Küre + Orbit Yolları"),
    (22.5, 12.2, "📋", "Sidebar",          "Metrik + Risk Özeti"),
]
for dx, dy, ic, ti, su in DASH_SUB:
    box(dx, dy, 3.6, 1.2, C_DASH, ti, fs=9, icon=ic, sub=su)

arrow(18.3, 12.2, 18.7, 12.2, C_DASH)
arrow(21.3, 12.2, 21.7, 12.2, C_DASH)

# sub → local output oku
arrow(16.5, 11.6, 18.5, 10.5, C_DASH, rad=0.15)
arrow(19.5, 11.6, 18.5, 10.5, C_DASH, rad=0.0)
arrow(22.5, 11.6, 18.5, 10.5, C_DASH, rad=-0.15)

# ── Yerel çıktı
box(18.5, 10.0, 4.2, 0.82, C_RUN, "localhost:8501", fs=10,
    icon="🌍", sub="Streamlit Web Dashboard")

# ═══════════════════════════════════════════════════════════════════════════════
# KATMAN 4 — CLOUD DEPLOYMENT (Docker → Artifact Registry → K8s → Cloud Run)
# ═══════════════════════════════════════════════════════════════════════════════
layer_label(0.6, 8.3, "④ CLOUD DEPLOYMENT  (Google Cloud)", C_GCP)
hline(8.55, color="#BBDEFB", lw=1.5)

# GCP container arka plan
container(0.3, 1.8, 23.5, 8.3, C_GCP, "Google Cloud Platform  ·  us-central1")

# ── 4a. Docker Build
box(2.4, 7.2, 3.4, 1.1, C_DOCKER, "Docker\nImage Build", fs=9,
    icon="🐋", sub="python:3.11-slim  ·  Multi-stage")

# ── 4b. Artifact Registry
box(6.8, 7.2, 3.8, 1.1, C_GCP, "Artifact Registry", fs=9,
    icon="📦", sub="yorunge-repo\nus-central1-docker.pkg.dev")

# ── 4c. Kubernetes (GKE) Instance
box(11.8, 7.2, 3.8, 1.1, C_K8S, "Kubernetes\n(GKE Instance)", fs=9,
    icon="☸️", sub="Container Orchestration\nPod / Node yönetimi")

# ── 4d. Cloud Run Service
box(17.0, 7.2, 3.8, 1.1, C_RUN, "Cloud Run\nService", fs=9,
    icon="☁️", sub="Managed · Serverless\nmin-instances=0  max=1")

# ── 4e. Public URL
box(21.8, 7.2, 2.8, 1.1, "#0F9D58", "Public URL", fs=9,
    icon="🔗", sub="*.run.app\nHTTPS · Port 8501")

# Docker → Registry → K8s → Cloud Run → URL okları
arrow(4.1, 7.2, 4.9, 7.2, C_DOCKER, lw=1.8)
arrow(8.7, 7.2, 9.9, 7.2, C_GCP,    lw=1.8)
arrow(13.7, 7.2, 15.1, 7.2, C_K8S,  lw=1.8)
arrow(18.9, 7.2, 20.4, 7.2, C_RUN,  lw=1.8)

# ── Spec badge'leri (her kutunun altında)
badge(2.4,  6.5, "Dockerfile  ·  docker build", C_DOCKER, w=3.4)
badge(6.8,  6.5, "docker push  ·  image:latest", C_GCP,   w=3.6)
badge(11.8, 6.5, "gcloud container clusters", C_K8S,      w=3.6)
badge(17.0, 6.5, "gcloud run deploy  ·  2Gi RAM  ·  1 CPU", C_RUN, w=4.6)
badge(21.8, 6.5, "allow-unauthenticated", "#0F9D58",      w=3.0)

# ── CI/CD akış oku (soldan sağa büyük)
ax.annotate("", xy=(23.3, 5.8), xytext=(0.8, 5.8),
            arrowprops=dict(
                arrowstyle="-|>", color="#BBDEFB", lw=3,
                connectionstyle="arc3,rad=0.0", mutation_scale=20,
            ), zorder=1)
ax.text(12, 5.72, "deploy-gcloud.ps1  ·  CI / CD akışı",
        ha="center", va="center", fontsize=8, color=C_GCP,
        fontweight="bold", alpha=0.7)

# ── GCP Servis detayları
GCP_SERVICES = [
    (3.5,  4.9, "🔒 IAM & Auth",        "gcloud auth login\nService Account"),
    (8.5,  4.9, "🌐 VPC / Network",     "us-central1  ·  Iowa\nFree Tier bölgesi"),
    (13.5, 4.9, "📈 Cloud Monitoring",  "Health Check  ·  Logs\nuptime monitoring"),
    (18.5, 4.9, "🔄 Auto Scaling",      "0 → N instances\nCold start: ~15sn"),
    (22.5, 4.9, "💰 Maliyet",           "~$0/gün (Free Tier)\n~$1-2/gün (always-on)"),
]
for gx, gy, gt, gs in GCP_SERVICES:
    box(gx, gy, 4.2, 1.3, C_GCP, gt, fs=8.5, icon=None,
        sub=gs, border_only=True, tc=C_GCP)

# ── App → Docker oku (dashboard → deployment katmanı)
arrow(18.5, 9.59, 2.4, 7.76, C_DOCKER, rad=-0.3, lw=2,
      style="-|>")
ax.text(9.0, 9.0, "docker build & push", ha="center", va="center",
        fontsize=8, color=C_DOCKER, style="italic",
        rotation=355, alpha=0.85)

# ═══════════════════════════════════════════════════════════════════════════════
# PERFORMANS BANDI
# ═══════════════════════════════════════════════════════════════════════════════
perf = FancyBboxPatch(
    (0.3, 0.12), 23.2, 0.9,
    boxstyle="round,pad=0.06,rounding_size=0.2",
    linewidth=1, edgecolor="#E0E0E0", facecolor="#F8F9FA", zorder=1
)
ax.add_patch(perf)

PERF = [
    (3.5,  "⏱",  "Pipeline: ~3-5 dk",        C_PIPE),
    (8.0,  "🔮", "Tahmin: ~2 dk",             C_SRC),
    (12.5, "⚡",  "Dashboard yükleme: ~5 sn", C_RUN),
    (17.5, "🐋",  "Docker build: ~10-15 dk",  C_DOCKER),
    (22.0, "☁️",  "Cloud Run deploy: ~2 dk",  C_GCP),
]
for px, ic, pt, pc in PERF:
    ax.text(px, 0.6, ic + "  " + pt, ha="center", va="center",
            fontsize=8.2, color=pc, fontweight="bold", fontproperties=_ep)

for sep_x in [5.5, 10.5, 15.0, 19.8]:
    ax.plot([sep_x, sep_x], [0.18, 0.96], color="#E0E0E0", lw=1)

# ── Kaydet ────────────────────────────────────────────────────────────────────
plt.tight_layout(pad=0)
plt.savefig("architecture_diagram.png", dpi=180, bbox_inches="tight",
            facecolor=C_BG)
print("✅ architecture_diagram.png oluşturuldu.")

"""
Space Debris Tracking Model — Ana Giriş Noktası
================================================
Türk uydularına yakın uzay çöplerini tespit eden ve
t+24h mesafe tahminini gerçekleştiren ML pipeline.

Kullanım:
  python main.py                     # Tam pipeline (eğitim yok → sadece tahmin)
  python main.py --train             # Eğitim dahil tam pipeline
  python main.py --rebuild           # Verileri yeniden oluştur + eğit
  python main.py --predict-only      # Sadece tahmin (model mevcut olmalı)
  python main.py --viz               # Tahmin + görselleştirme
  python main.py --validate          # TCA doğrulama
  python main.py --all               # Her şey
  python main.py --status            # Pipeline durumu

Adımlar:
  0  cop_verileri_to_csv       → enriched CSV oluştur
  1  step00_clean_data         → istatistiki temizleme
  2  build_real_encounters     → SGP4 t0+t24+TCA hesabı
  3  step02_build_features     → feature engineering
  4  step03_train_baseline     → LightGBM eğitimi
  5  predict_risk              → simülasyon çıktısı
  6  visualize_results         → grafik raporu
  7  validate_tca              → çarpışma rotası doğrulama
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── Dosya yolları ──────────────────────────────────────────
PATHS = {
    # Kaynak veriler
    "cop_json":          ROOT / "cop_verileri.json",
    "turk_json":         ROOT / "turk_uydulari.json",
    # İşlenmiş veriler
    "enriched":          ROOT / "data" / "processed" / "cop_verileri_enriched.csv",
    "cleaned":           ROOT / "data" / "processed" / "cop_verileri_cleaned.csv",
    "encounters":        ROOT / "data" / "processed" / "encounters_24h.csv",
    "features":          ROOT / "data" / "processed" / "ml_features_24h.csv",
    # Model
    "model":             ROOT / "lightgbm_risk_modeli.pkl",
    "model_report":      ROOT / "data" / "processed" / "ml_step03_report.json",
    # Tahmin çıktıları
    "risk_tum":          ROOT / "data" / "output" / "risk_tahmin_tum.csv",
    "risk_kritik":       ROOT / "data" / "output" / "risk_tahmin_kritik.csv",
    "risk_json":         ROOT / "data" / "output" / "risk_tahmin_simul.json",
    # Görseller
    "plots_dir":         ROOT / "data" / "output" / "plots",
    # TCA doğrulama
    "tca_csv":           ROOT / "data" / "output" / "tca_validation.csv",
}

BANNER = """
╔══════════════════════════════════════════════════════╗
║   🛰️  Space Debris Tracking Model                   ║
║   Türk Uyduları × 17,414 Uzay Çöpü — 24h Tahmin    ║
╚══════════════════════════════════════════════════════╝
"""


# ── Yardımcı yordamlar ─────────────────────────────────────

def sep(title: str = "", char: str = "─", width: int = 58):
    if title:
        print(f"\n{char * 3} {title} {char * max(0, width - len(title) - 5)}")
    else:
        print(char * width)


def run_step(label: str, module: str | None = None,
             script: str | None = None) -> tuple[bool, float]:
    """Bir pipeline adımını çalıştırır. (başarı, süre) döndürür."""
    sep(label)
    start = time.perf_counter()

    if module:
        cmd = [sys.executable, "-m", module]
    elif script:
        cmd = [sys.executable, str(ROOT / script)]
    else:
        raise ValueError("module veya script belirtilmeli")

    result = subprocess.run(cmd, cwd=ROOT)
    elapsed = time.perf_counter() - start
    ok = result.returncode == 0

    status = "✅" if ok else "❌"
    print(f"\n{status} {label}: {'%.1f' % elapsed}s")
    return ok, elapsed


def check_file(key: str, label: str) -> bool:
    p = PATHS[key]
    exists = p.exists()
    size_str = ""
    if exists and p.is_file():
        size_kb = p.stat().st_size / 1024
        size_str = f" ({size_kb:.0f} KB)" if size_kb < 1024 else f" ({size_kb/1024:.1f} MB)"
    marker = "✅" if exists else "❌"
    print(f"  {marker} {label:<30} {size_str}")
    return exists


def show_status():
    """Pipeline dosyalarının mevcut durumunu göster."""
    sep("PIPELINE DURUMU")
    checks = [
        ("cop_json",     "Çöp TLE verisi (kaynak)"),
        ("turk_json",    "Türk uyduları (kaynak)"),
        ("enriched",     "Enriched CSV"),
        ("cleaned",      "Temizlenmiş CSV"),
        ("encounters",   "Karşılaşma tablosu (t0+t24+TCA)"),
        ("features",     "Feature matrisi"),
        ("model",        "LightGBM model"),
        ("model_report", "Model raporu"),
        ("risk_tum",     "Risk tahmin — tüm çiftler"),
        ("risk_kritik",  "Risk tahmin — kritik çiftler"),
        ("risk_json",    "Risk JSON (simülasyon)"),
        ("tca_csv",      "TCA doğrulama"),
    ]
    all_ok = all(check_file(k, l) for k, l in checks)

    plot_count = len(list(PATHS["plots_dir"].glob("*.png"))) if PATHS["plots_dir"].exists() else 0
    marker = "✅" if plot_count > 0 else "❌"
    print(f"  {marker} {'Görselleştirme grafikleri':<30} ({plot_count} PNG)")

    # Model metrikleri
    if PATHS["model_report"].exists():
        sep("MODEL METRİKLERİ")
        with open(PATHS["model_report"], encoding="utf-8") as f:
            rpt = json.load(f)
        lgb = rpt.get("lightgbm", {})
        naive = rpt.get("baseline_naive", {})
        print(f"  {'Metrik':<20} {'Naive':>12} {'LightGBM':>12}")
        print(f"  {'-'*46}")
        print(f"  {'RMSE (km)':<20} {naive.get('rmse', '?'):>12.2f} {lgb.get('test_rmse', '?'):>12.2f}")
        print(f"  {'R²':<20} {naive.get('r2', '?'):>12.6f} {lgb.get('test_r2', '?'):>12.6f}")
        cv_rmse = lgb.get('cv_rmse_mean', '?')
        cv_std  = lgb.get('cv_rmse_std', '?')
        print(f"  {'CV RMSE (km)':<20} {'':>12} {f'{cv_rmse:.2f} ±{cv_std:.2f}':>12}")

    # Risk özeti
    if PATHS["risk_json"].exists():
        sep("GÜNCEL RİSK ÖZETİ")
        with open(PATHS["risk_json"], encoding="utf-8") as f:
            sim = json.load(f)
        ozet = sim.get("risk_ozeti", {})
        meta = sim.get("meta", {})
        print(f"  Hesap zamanı : {meta.get('hesap_utc', '?')[:19]} UTC")
        print(f"  Toplam çift  : {meta.get('n_toplam_cift', '?'):,}")
        for sev, cnt in ozet.items():
            bar = "█" * min(30, int(30 * cnt / meta.get("n_toplam_cift", 1)))
            pct = 100 * cnt / max(meta.get("n_toplam_cift", 1), 1)
            print(f"  {sev:<8} {cnt:>7,} ({pct:>5.1f}%)  {bar}")

        sep("UYDU BAZLI EN YAKIN ÇÖPLER")
        uydu_oz = sim.get("uydu_ozeti", {})
        print(f"  {'UYDU':<16} {'KRİTİK':>7} {'YÜKSEK':>7} {'EN YAKIN':>10}  {'CİSİM'}")
        print(f"  {'-'*70}")
        for uydu, d in sorted(uydu_oz.items(), key=lambda x: x[1]["en_yakin_tahmin_km"]):
            print(f"  {uydu:<16} {d['kritik_sayisi']:>7} {d['yuksek_sayisi']:>7} "
                  f"{d['en_yakin_tahmin_km']:>9.1f}km  ← {d['en_yakin_cop']}")

    return all_ok


def confirm_train() -> bool:
    """Kullanıcıdan eğitim onayı istenir."""
    print("\n⚠️  Eğitim ~2-3 dakika sürecek.")
    try:
        ans = input("   Devam edilsin mi? [E/h]: ").strip().lower()
        return ans in ("", "e", "y", "evet", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ── Ana pipeline ───────────────────────────────────────────

def pipeline_full(train: bool = False, rebuild: bool = False,
                  viz: bool = False, validate: bool = False) -> int:
    """Belirlenen bayraklara göre pipeline adımlarını çalıştırır."""
    timings: dict[str, float] = {}
    errors: list[str] = []
    t_start = time.perf_counter()

    def step(label: str, module: str | None = None,
             script: str | None = None, required: bool = True) -> bool:
        ok, elapsed = run_step(label, module=module, script=script)
        timings[label] = elapsed
        if not ok:
            errors.append(label)
            if required:
                print(f"\n💥 Pipeline '{label}' adımında durdu.")
                return False
        return True

    # 0. Enriched CSV
    if rebuild or not PATHS["enriched"].exists():
        if not step("0. Enriched CSV", script="cop_verileri_to_csv.py"):
            return 1

    # 1. Temizleme
    if rebuild or not PATHS["cleaned"].exists():
        if not step("1. Veri Temizleme", module="ml_pipeline.data.step00_clean_data"):
            return 1

    # 2. Karşılaşma tablosu (TCA dahil)
    if rebuild or not PATHS["encounters"].exists():
        if not step("2. Karşılaşma + TCA", module="ml_pipeline.build_real_encounters"):
            return 1

    # 3. Feature engineering
    if rebuild or not PATHS["features"].exists():
        if not step("3. Feature Engineering", module="ml_pipeline.training.step02_build_features"):
            return 1

    # 4. Model eğitimi
    if train or rebuild or not PATHS["model"].exists():
        if train or rebuild or confirm_train():
            if not step(
                "4. Model Eğitimi (LightGBM)",
                module="ml_pipeline.training.step03_train_baseline",
            ):
                return 1
        else:
            print("   ⏭  Eğitim atlandı — mevcut model kullanılacak.")
    else:
        sep("4. Model Eğitimi")
        print("   ⏭  Model mevcut (lightgbm_risk_modeli.pkl) — eğitim atlandı.")
        print("   ℹ️  Yeniden eğitmek için: python main.py --train")

    # 5. Risk tahmini
    if not step("5. Risk Tahmini", script="predict_risk.py"):
        return 1

    # 6. Görselleştirme (isteğe bağlı)
    if viz:
        step("6. Görselleştirme", module="ml_pipeline.analysis.visualize_results", required=False)

    # 7. TCA doğrulama (isteğe bağlı)
    if validate:
        step("7. TCA Doğrulama", module="ml_pipeline.analysis.validate_tca", required=False)

    # ── Özet ───────────────────────────────────────────────
    total = time.perf_counter() - t_start
    sep("PIPELINE ÖZETI", char="═")
    for label, elapsed in timings.items():
        status = "❌" if label in [e for e in errors] else "✅"
        print(f"  {status} {label:<40} {elapsed:>6.1f}s")
    print(f"\n  Toplam süre: {total:.1f}s")

    if errors:
        print(f"\n❌ {len(errors)} adım başarısız: {', '.join(errors)}")
        return 1

    print("\n✅ Pipeline başarıyla tamamlandı.")
    print(f"   📁 Çıktılar: {ROOT / 'data' / 'output'}")
    return 0


# ── CLI ────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Space Debris Tracking Model — 24h Risk Tahmini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python main.py                    # Hızlı mod: mevcut model ile tahmin
  python main.py --train            # Model yeniden eğit + tahmin yap
  python main.py --rebuild          # Ham veriden baştan oluştur + eğit
  python main.py --predict-only     # Sadece risk tahmini güncelle
  python main.py --viz              # Tahmin + görsel rapor
  python main.py --all              # Her şey (eğitim + viz + TCA)
  python main.py --status           # Dosya ve model durumu
        """,
    )
    p.add_argument("--train",        action="store_true", help="Modeli yeniden eğit")
    p.add_argument("--rebuild",      action="store_true", help="Ham veriden baştan oluştur")
    p.add_argument("--predict-only", action="store_true", help="Sadece risk tahmini")
    p.add_argument("--viz",          action="store_true", help="Görselleştirme ekle")
    p.add_argument("--validate",     action="store_true", help="TCA doğrulama çalıştır")
    p.add_argument("--all",          action="store_true", help="Tam pipeline (eğitim+viz+TCA)")
    p.add_argument("--status",       action="store_true", help="Dosya ve model durumunu göster")
    return p


def main() -> int:
    print(BANNER)
    print(f"Zaman: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Proje: {ROOT}")

    args = build_parser().parse_args()

    # Durum göster
    if args.status:
        show_status()
        return 0

    # Sadece tahmin
    if args.predict_only:
        if not PATHS["model"].exists():
            print("\n❌ Model bulunamadı. Önce eğitin: python main.py --train")
            return 1
        if not PATHS["features"].exists():
            print("\n❌ Feature dosyası bulunamadı. Önce: python main.py --rebuild")
            return 1
        _, _ = run_step("Risk Tahmini", script="predict_risk.py")
        show_status()
        return 0

    # Tam pipeline
    train   = args.train or args.all
    rebuild = args.rebuild
    viz     = args.viz or args.all
    validate = args.validate or args.all

    code = pipeline_full(train=train, rebuild=rebuild, viz=viz, validate=validate)

    if code == 0:
        sep("DURUM", char="═")
        show_status()

    return code


if __name__ == "__main__":
    sys.exit(main())

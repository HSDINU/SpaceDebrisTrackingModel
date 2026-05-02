"""
DISCOSweb API ile çöp (ve isteğe bağlı Türk uydu) NORAD listesini zenginleştir.

Çıktılar:
  data/processed/discos_object_destination_flat.csv — DISCOS nesne + destination-orbit alanları
  data/processed/cop_verileri_cleaned_discos.csv — cleaned ile norad_id üzerinden sol birleşim (varsa)

Önkoşul:
  DISCOS_API_TOKEN ortam değişkeni (Bearer). https://discosweb.esoc.esa.int/
  API sürümü: DiscosWeb-Api-Version 2 (discos_client içinde).

ESA veri kullanımı ve atıf: DISCOSweb şartlarına uyun.

Çalıştırma (repo kökü):
  $env:DISCOS_API_TOKEN = '<token>'   # PowerShell
  python -m ml_pipeline.step_discos_enrich

İsteğe bağlı — sadece ilk N NORAD (hızlı deneme):
  python -m ml_pipeline.step_discos_enrich --max-objects 200
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from ml_pipeline.discos_client import (
    fetch_objects_with_destination_orbits,
    flatten_object_destination_rows,
    get_token_from_env,
)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_turk_norads(root: Path) -> list[int]:
    p = root / "turk_uydulari.json"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    out: list[int] = []
    for sat in data:
        nid = sat.get("norad_id")
        if nid is None and sat.get("tle_line1"):
            parts = str(sat["tle_line1"]).split()
            if len(parts) > 1:
                nid = parts[1].rstrip("U")
        if nid is not None and str(nid).strip().isdigit():
            out.append(int(str(nid).strip()))
    return out


def main() -> int:
    root = project_root()
    ap = argparse.ArgumentParser(description="DISCOSweb ile NORAD zenginleştirme")
    ap.add_argument(
        "--max-objects",
        type=int,
        default=0,
        help="0 = tümü; aksi halde en fazla bu kadar benzersiz NORAD",
    )
    ap.add_argument(
        "--skip-merge",
        action="store_true",
        help="cleaned CSV ile birleştirmeyi atla",
    )
    args = ap.parse_args()

    print("=" * 60)
    print("DISCOSweb zenginleştirme (objects + destination-orbits)")
    print("=" * 60)

    try:
        get_token_from_env()
    except RuntimeError as e:
        print(e)
        return 1

    cleaned_path = root / "data" / "processed" / "cop_verileri_cleaned.csv"
    enriched_fallback = root / "data" / "processed" / "cop_verileri_enriched.csv"
    out_flat = root / "data" / "processed" / "discos_object_destination_flat.csv"
    out_merged = root / "data" / "processed" / "cop_verileri_cleaned_discos.csv"
    out_merged.parent.mkdir(parents=True, exist_ok=True)

    satnos: list[int] = []
    if cleaned_path.exists():
        df_c = pd.read_csv(cleaned_path, encoding="utf-8-sig", usecols=["norad_id"])
        satnos.extend(df_c["norad_id"].dropna().astype(int).tolist())
        print(f"NORAD (cleaned): {len(set(satnos)):,} benzersiz")
    elif enriched_fallback.exists():
        df_e = pd.read_csv(enriched_fallback, encoding="utf-8-sig", usecols=["norad_id"])
        satnos.extend(df_e["norad_id"].dropna().astype(int).tolist())
        print(f"NORAD (enriched, cleaned yok): {len(set(satnos)):,} benzersiz")
    else:
        print(f"HATA: {cleaned_path} veya {enriched_fallback} bulunamadı.")
        return 1

    turk = load_turk_norads(root)
    if turk:
        satnos.extend(turk)
        print(f"Türk uydu NORAD eklendi: +{len(set(turk))} kayıt dosyasından")

    satnos = sorted(set(satnos))
    if args.max_objects > 0:
        satnos = satnos[: args.max_objects]
        print(f"--max-objects: ilk {len(satnos)} NORAD kullanılıyor")

    print(f"API sorgusu: {len(satnos):,} NORAD (chunk'lı)")
    raw = fetch_objects_with_destination_orbits(satnos)
    flat = flatten_object_destination_rows(raw)
    df_discos = pd.DataFrame(flat)
    df_discos.to_csv(out_flat, index=False, encoding="utf-8-sig")
    print(f"Yazıldı: {out_flat} ({len(df_discos):,} satır)")

    matched = df_discos["norad_id"].notna().sum()
    with_dest = (df_discos["destination_orbit_id"].notna()).sum()
    print(f"Özet: {matched:,} satırda norad_id; {with_dest:,} destination-orbit satırı")

    if args.skip_merge or not cleaned_path.exists():
        print("Birleştirme atlandı.")
        return 0

    df_clean = pd.read_csv(cleaned_path, encoding="utf-8-sig")
    df_dedup = df_discos.sort_values(
        ["norad_id", "destination_orbit_id"], na_position="last"
    ).drop_duplicates(subset=["norad_id"], keep="first")

    r = df_dedup.copy()
    r = r.rename(columns={c: f"discos_{c}" for c in r.columns if c != "norad_id"})
    merged = df_clean.merge(r, on="norad_id", how="left")

    merged.to_csv(out_merged, index=False, encoding="utf-8-sig")
    print(f"Birleşik: {out_merged} ({len(merged):,} satır)")
    if "discos_object_id" in merged.columns:
        hit = merged["discos_object_id"].notna()
        print(f"DISCOS eşleşmesi: {int(hit.sum()):,} / {len(merged):,} satır")
    return 0


if __name__ == "__main__":
    sys.exit(main())

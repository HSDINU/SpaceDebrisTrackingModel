"""
ESA DISCOSweb JSON:API v2 ince istemci.

Belgeler: https://discosweb.esoc.esa.int/apidocs/v2
Kimlik: Space Debris User Account ile kişisel erişim token'ı.
Ortam: DISCOS_API_TOKEN (Bearer). Repo kökünde .env içinde
  DISCOS_API_TOKEN=... satırı da okunur (python-dotenv). Asla .env'i commit etmeyin.

Kaynak atıf şablonu için bkz. ESA DISCOSweb şartları.
"""
from __future__ import annotations

import os
import random
import re
import time
from pathlib import Path
from typing import Any

import requests
from requests.exceptions import ChunkedEncodingError, ConnectionError, Timeout

_ENV_BOOTSTRAPPED = False


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _bootstrap_env_from_dotenv() -> None:
    """Repo kökündeki .env / .env.local dosyalarını yükle (DISCOS_API_TOKEN vb.)."""
    global _ENV_BOOTSTRAPPED
    if _ENV_BOOTSTRAPPED:
        return
    _ENV_BOOTSTRAPPED = True
    root = _project_root()
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[misc, assignment]
    for name in (".env", ".env.local"):
        env_file = root / name
        if env_file.is_file() and load_dotenv is not None:
            load_dotenv(env_file, override=False)


def _parse_token_from_env_file(path: Path) -> str:
    """BOM / export / tırnak sorunlarında yedek: DISCOS_API_TOKEN=... satırını oku."""
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    keys = ("DISCOS_API_TOKEN", "DISCOS_TOKEN", "DISCOS_WEB_TOKEN")
    assign = re.compile(r"^([^=#]+?)\s*=\s*(.*)$")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("export "):
            s = s[7:].strip()
        m = assign.match(s)
        if not m:
            continue
        key = m.group(1).strip()
        val = m.group(2).strip().strip('"').strip("'")
        if key in keys and val:
            return val
    return ""

BASE_URL = "https://discosweb.esoc.esa.int/api"
# (bağlantı süresi, okuma süresi) — uzun JSON yanıtları için okuma cömert
REQUEST_TIMEOUT = (20.0, 120.0)
PAGE_SIZE = 100
# Küçük chunk: kısa URL, sunucu/WAF için daha az agresif
CHUNK_SATNOS = 35
CHUNK_PAUSE_SEC = 0.45
GET_MAX_ATTEMPTS = 6


def _headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.api+json",
        "Authorization": f"Bearer {token}",
        "DiscosWeb-Api-Version": "2",
        "User-Agent": "SpaceDebrisTrackingModel/1.0 (ESA DISCOS research; Python requests)",
        "Connection": "close",
    }


def _session_get(
    sess: requests.Session,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    timeout: tuple[float, float] = REQUEST_TIMEOUT,
) -> requests.Response:
    """Bağlantı kopması / reset için üstel geri çekilme ile GET."""
    last: Exception | None = None
    for attempt in range(GET_MAX_ATTEMPTS):
        try:
            return sess.get(url, headers=headers, params=params, timeout=timeout)
        except (ConnectionError, Timeout, ChunkedEncodingError) as e:
            last = e
            if attempt >= GET_MAX_ATTEMPTS - 1:
                break
            wait = min(90.0, (2**attempt) + random.uniform(0.0, 0.75))
            time.sleep(wait)
    assert last is not None
    raise last


def get_token_from_env() -> str:
    _bootstrap_env_from_dotenv()
    t = (os.environ.get("DISCOS_API_TOKEN") or "").strip().strip('"').strip("'")
    root = _project_root()
    if not t:
        for name in (".env", ".env.local"):
            t = _parse_token_from_env_file(root / name)
            if t:
                os.environ.setdefault("DISCOS_API_TOKEN", t)
                break
        t = (os.environ.get("DISCOS_API_TOKEN") or "").strip().strip('"').strip("'")
    if not t:
        env_path = root / ".env"
        hint = (
            f"DISCOS_API_TOKEN tanımlı değil. Seçenekler:\n"
            f"  • Repo kökünde .env veya .env.local içinde şu satırlardan biri:\n"
            f"      DISCOS_API_TOKEN=...\n"
            f"      (alternatif anahtarlar: DISCOS_TOKEN, DISCOS_WEB_TOKEN)\n"
            f"    Beklenen konum: {env_path}\n"
            f"  • PowerShell: $env:DISCOS_API_TOKEN = '<token>'\n"
        )
        if env_path.is_file():
            try:
                sz = env_path.stat().st_size
            except OSError:
                sz = -1
            if sz == 0:
                hint += (
                    "  • .env dosyası diskte 0 byte — editördeki satırı Ctrl+S ile kaydedin.\n"
                )
            try:
                import dotenv  # noqa: F401
            except ImportError:
                hint += (
                    "  • python-dotenv yüklü değil: pip install python-dotenv\n"
                )
        raise RuntimeError(hint)
    return t


def get_json(
    path: str,
    *,
    token: str | None = None,
    params: dict[str, Any] | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    tok = token or get_token_from_env()
    url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
    sess = session or requests.Session()
    r = _session_get(sess, url, headers=_headers(tok), params=params or {})
    if r.status_code == 429:
        time.sleep(2.0)
        r = _session_get(sess, url, headers=_headers(tok), params=params or {})
    if r.status_code >= 400:
        body = (r.text or "")[:1500]
        raise RuntimeError(f"DISCOS HTTP {r.status_code} {r.reason}: {body}")
    return r.json()


def fetch_objects_with_destination_orbits(
    satnos: list[int],
    *,
    token: str | None = None,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """
    NORAD (satno) listesi için /objects toplu sorgu (resordan ile aynı parametreler).

    Not: Toplu uçta ``include=destination-orbits`` ve ``page[number]`` DISCOS v2'de 400
    döndürebiliyor. Bu yüzden yalnızca ``filter`` + ``page[size]`` kullanılır; sayfalama
    ``links.next`` ile. Destination-orbit ayrıntıları ``included`` içinde gelmez; kütle /
    boyut vb. nesne ``attributes`` dolu kalır. İlişki kimlikleri varsa flatten aşamasında
    yakalanır (öznitelik olmadan).
    """
    tok = token or get_token_from_env()
    out: list[dict[str, Any]] = []

    # Tekilleştir, sırala (deterministik chunk)
    uniq = sorted({int(s) for s in satnos if s is not None and int(s) > 0})
    for i in range(0, len(uniq), CHUNK_SATNOS):
        chunk = uniq[i : i + CHUNK_SATNOS]
        sat_list = ",".join(str(s) for s in chunk)
        params: dict[str, Any] = {
            "filter": f"in(satno,({sat_list}))",
            "page[size]": PAGE_SIZE,
        }
        # Her chunk'ta yeni oturum: keep-alive ile sunucunun bağlantıyı kesmesi sık görülüyor
        chunk_sess = session or requests.Session()
        try:
            next_url: str | None = None
            while True:
                hdrs = _headers(tok)
                if next_url:
                    r = _session_get(chunk_sess, next_url, headers=hdrs)
                else:
                    r = _session_get(
                        chunk_sess,
                        f"{BASE_URL}/objects",
                        headers=hdrs,
                        params=params,
                    )
                if r.status_code == 429:
                    time.sleep(3.0 + random.uniform(0, 1.0))
                    r = _session_get(chunk_sess, r.url, headers=hdrs)
                if r.status_code >= 400:
                    body = (r.text or "")[:1500]
                    raise RuntimeError(f"DISCOS HTTP {r.status_code} {r.reason}: {body}")
                doc = r.json()
                rows = doc.get("data") or []
                included = doc.get("included") or []
                for row in rows:
                    out.append({"object": row, "included": included})
                next_url = (doc.get("links") or {}).get("next")
                if not next_url:
                    break
        finally:
            if session is None:
                chunk_sess.close()
        time.sleep(CHUNK_PAUSE_SEC + random.uniform(0, 0.2))

    return out


def _pick_included(
    included: list[dict[str, Any]], type_name: str, res_id: str
) -> dict[str, Any] | None:
    for inc in included:
        if inc.get("type") == type_name and str(inc.get("id")) == str(res_id):
            return inc
    return None


def flatten_object_destination_rows(
    fetch_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Her nesne için: özellikler + ilişkili destination-orbit(ler) düz satır."""
    flat: list[dict[str, Any]] = []
    for pack in fetch_rows:
        obj = pack["object"]
        included = pack.get("included") or []
        attr = obj.get("attributes") or {}
        oid = str(obj.get("id", ""))
        rels = obj.get("relationships") or {}
        rel = rels.get("destination-orbits") or rels.get("destinationOrbits") or {}
        rel_data = rel.get("data")
        links: list[dict[str, str]] = []
        if isinstance(rel_data, list):
            links = [x for x in rel_data if isinstance(x, dict)]
        elif isinstance(rel_data, dict) and rel_data.get("id"):
            links = [rel_data]

        satno = attr.get("satno")
        base = {
            "object_id": oid,
            "norad_id": int(satno) if satno is not None else None,
            "cospar_id": attr.get("cosparId"),
            "discos_name": attr.get("name"),
            "object_class": attr.get("objectClass"),
            "mission": attr.get("mission"),
            "mass_kg": attr.get("mass"),
            "shape": attr.get("shape"),
            "length_m": attr.get("length"),
            "height_m": attr.get("height"),
            "depth_m": attr.get("depth"),
            "diameter_m": attr.get("diameter"),
            "span_m": attr.get("span"),
            "x_sect_max_m2": attr.get("xSectMax"),
            "x_sect_min_m2": attr.get("xSectMin"),
            "x_sect_avg_m2": attr.get("xSectAvg"),
            "destination_orbit_count": len(links),
        }

        if not links:
            flat.append({**base, "destination_orbit_id": None})
            continue

        for ref in links:
            rid = str(ref.get("id", ""))
            rtype = ref.get("type") or "destination-orbits"
            inc = _pick_included(included, rtype, rid)
            oa = (inc or {}).get("attributes") or {}
            flat.append(
                {
                    **base,
                    "destination_orbit_id": rid or None,
                    "dest_epoch": oa.get("epoch"),
                    "dest_sma_m": oa.get("sma"),
                    "dest_inc_deg": oa.get("inc"),
                    "dest_ecc": oa.get("ecc"),
                    "dest_raan_deg": oa.get("raan"),
                    "dest_arg_per_deg": oa.get("aPer"),
                    "dest_mean_anomaly_deg": oa.get("mAno"),
                    "dest_frame": oa.get("frame"),
                }
            )
    return flat

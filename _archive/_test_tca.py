from ml_pipeline.build_real_encounters import compute_tca, TCA_STEP_MIN, TCA_THRESHOLD_KM
print("TCA fonksiyonu import OK")
print(f"TCA_STEP_MIN = {TCA_STEP_MIN} dakika")
print(f"TCA_THRESHOLD_KM = {TCA_THRESHOLD_KM:,} km")

import json
from datetime import datetime, timezone
from sgp4.api import Satrec

with open("cop_verileri.json", encoding="utf-8") as f:
    cops = json.load(f)
with open("turk_uydulari.json", encoding="utf-8") as f:
    turk = json.load(f)

s_sat = Satrec.twoline2rv(turk[1]["tle_line1"], turk[1]["tle_line2"])  # GOKTURK 2
s_cop = Satrec.twoline2rv(cops[0]["tle_line1"], cops[0]["tle_line2"])  # COSMOS 1408 DEB

t0 = datetime.now(timezone.utc)
tca_km, tca_h = compute_tca(s_sat, s_cop, t0)
print(f"TCA: {tca_km:.1f} km @ t+{tca_h:.1f}h")
print(f"  {turk[1]['name']} vs {cops[0]['isim']}")
print("CALISIR")

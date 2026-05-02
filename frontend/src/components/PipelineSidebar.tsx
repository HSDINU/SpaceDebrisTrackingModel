"use client";

import type { SidebarPayload } from "@/lib/viz/vizTypes";

type Props = {
  sidebar: SidebarPayload | null;
  loadError: boolean;
  onRefresh: () => void;
  refreshing: boolean;
  /** ML pipeline çalışırken yenileyi kapat (çift tetiklemeyi önler) */
  pipelineBusy?: boolean;
};

function ProgressBar({ pct }: { pct: number }) {
  const w = Math.min(100, Math.max(0, pct * 100));
  return (
    <div className="ps-progress-track">
      <div className="ps-progress-fill" style={{ width: `${w}%` }} />
    </div>
  );
}

export default function PipelineSidebar({
  sidebar,
  loadError,
  onRefresh,
  refreshing,
  pipelineBusy = false,
}: Props) {
  const refreshDisabled = refreshing || pipelineBusy;
  if (loadError) {
    return (
      <div className="ps-inner">
        <p className="ps-warn">Pipeline çıktısı okunamadı.</p>
        <p className="ps-hint">
          <code className="ps-code">python main.py --all</code> ile veri üretin,
          ardından yenileyin.
        </p>
        <button
          type="button"
          className="ps-refresh"
          onClick={onRefresh}
          disabled={refreshDisabled}
        >
          🔄 Verileri yenile
        </button>
      </div>
    );
  }

  if (!sidebar) {
    return (
      <div className="ps-inner">
        <p className="ps-muted">Veri yükleniyor…</p>
      </div>
    );
  }

  if (!sidebar.dataReady) {
    return (
      <div className="ps-inner">
        <p className="ps-warn">Pipeline çıktısı bulunamadı.</p>
        <p className="ps-hint">
          Önce ML pipeline çalıştırın:{" "}
          <code className="ps-code">python main.py --all</code>
        </p>
        <button
          type="button"
          className="ps-refresh"
          onClick={onRefresh}
          disabled={refreshDisabled}
        >
          🔄 Verileri yenile
        </button>
      </div>
    );
  }

  const { nToplamCift, risk } = sidebar;
  const pct = (v: number) => (nToplamCift > 0 ? v / nToplamCift : 0);

  return (
    <div className="ps-inner">
      <div className="ps-brand">
        <h2 className="ps-brand-title">🛰️ YÖRÜNGE MUHAFIZI</h2>
        <p className="ps-brand-caption">
          Space Debris Risk Monitor — LightGBM 24h Pipeline
        </p>
      </div>

      <button
        type="button"
        className="ps-refresh"
        onClick={onRefresh}
        disabled={refreshDisabled}
      >
        {refreshing || pipelineBusy ? "⏳ Yükleniyor…" : "🔄 Verileri Yenile"}
      </button>

      <hr className="ps-rule" />

      <section className="ps-section">
        <h3 className="ps-h3">📡 Pipeline Durumu</h3>
        <p className="ps-line">
          <span className="ps-label">Son güncelleme:</span>{" "}
          <code className="ps-mono">{sidebar.hesapUtc} UTC</code>
        </p>
        <p className="ps-line">
          <span className="ps-label">Model:</span>{" "}
          <code className="ps-mono">{sidebar.modelLabel}</code>
        </p>
        <div className="ps-metrics3">
          <div className="ps-metric">
            <span className="ps-metric-label">Toplam Çift</span>
            <span className="ps-metric-val">
              {sidebar.nToplamCift.toLocaleString()}
            </span>
          </div>
          <div className="ps-metric">
            <span className="ps-metric-label">Uydu</span>
            <span className="ps-metric-val">{sidebar.nUydu}</span>
          </div>
          <div className="ps-metric">
            <span className="ps-metric-label">Debris</span>
            <span className="ps-metric-val">
              {sidebar.nDebrisUnique > 0
                ? sidebar.nDebrisUnique.toLocaleString()
                : "—"}
            </span>
          </div>
        </div>
      </section>

      <hr className="ps-rule" />

      <section className="ps-section">
        <h3 className="ps-h3">⚠️ Risk Özeti</h3>
        <div className="ps-risk-grid">
          <div className="ps-risk-cell">
            <span className="ps-dot ps-dot-kritik" />
            <span className="ps-risk-label">KRİTİK</span>
            <span className="ps-risk-num">{risk.kritik.toLocaleString()}</span>
          </div>
          <div className="ps-risk-cell">
            <span className="ps-dot ps-dot-yuksek" />
            <span className="ps-risk-label">YÜKSEK</span>
            <span className="ps-risk-num">{risk.yuksek.toLocaleString()}</span>
          </div>
          <div className="ps-risk-cell">
            <span className="ps-dot ps-dot-orta" />
            <span className="ps-risk-label">ORTA</span>
            <span className="ps-risk-num">{risk.orta.toLocaleString()}</span>
          </div>
          <div className="ps-risk-cell">
            <span className="ps-dot ps-dot-dusuk" />
            <span className="ps-risk-label">DÜŞÜK</span>
            <span className="ps-risk-num">{risk.dusuk.toLocaleString()}</span>
          </div>
        </div>

        {nToplamCift > 0 && (
          <div className="ps-progress-block">
            {(
              [
                ["YÜKSEK", risk.yuksek, "🟠"],
                ["ORTA", risk.orta, "🟡"],
                ["DÜŞÜK", risk.dusuk, "🟢"],
              ] as const
            ).map(([label, val, emoji]) => (
              <div key={label} className="ps-progress-item">
                <p className="ps-progress-cap">
                  {emoji} {label}:{" "}
                  <strong>{pct(val).toLocaleString(undefined, { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 })}</strong>{" "}
                  ({val.toLocaleString()})
                </p>
                <ProgressBar pct={pct(val)} />
              </div>
            ))}
          </div>
        )}
      </section>

      <hr className="ps-rule" />

      <section className="ps-section ps-section--grow">
        <h3 className="ps-h3">🛰️ Uydu Tehdit Durumu</h3>
        <div className="ps-expander-list">
          {sidebar.uyduTehdit.map((u) => {
            const badge =
              u.kritik > 0 ? "🔴" : u.yuksek > 0 ? "🟠" : "🟢";
            return (
              <details key={u.name} className="ps-details">
                <summary className="ps-summary">
                  {badge} {u.name} — {u.en_yakin_km.toLocaleString(undefined, { maximumFractionDigits: 0 })} km
                </summary>
                <div className="ps-details-body">
                  <div className="ps-details-metrics">
                    <div>
                      <span className="ps-dim">Kritik</span>
                      <strong>{u.kritik}</strong>
                    </div>
                    <div>
                      <span className="ps-dim">Yüksek</span>
                      <strong>{u.yuksek.toLocaleString()}</strong>
                    </div>
                    <div>
                      <span className="ps-dim">En yakın</span>
                      <strong>
                        {u.en_yakin_km.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })}{" "}
                        km
                      </strong>
                    </div>
                  </div>
                  <p className="ps-cop">
                    <span className="ps-dim">Cisim:</span> {u.en_yakin_cop}
                  </p>
                </div>
              </details>
            );
          })}
        </div>
      </section>
    </div>
  );
}

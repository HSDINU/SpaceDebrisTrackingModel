"use client";

import type { ThreatRecord } from "@/lib/vizTypes";
import type {
  ExperimentWeights,
  UserDataFilters,
} from "@/lib/vizUserTransforms";

type Props = {
  threats: ThreatRecord[];
  experiment: ExperimentWeights;
  onExperimentChange: (next: ExperimentWeights) => void;
  filters: UserDataFilters;
  onFiltersChange: (next: UserDataFilters) => void;
  filterOptions: { classes: string[]; missions: string[] };
  onFeedback: (vote: "up" | "down", threat: ThreatRecord) => void;
  feedbackBusyId: string | null;
};

function toggleInList(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((x) => x !== value) : [...list, value];
}

export default function UserParticipationPanel({
  threats,
  experiment,
  onExperimentChange,
  filters,
  onFiltersChange,
  filterOptions,
  onFeedback,
  feedbackBusyId,
}: Props) {
  return (
    <div className="panel-card" style={{ marginTop: 8 }}>
      <div className="panel-title">KULLANICI KATILIMI</div>
      <div className="panel-heading" style={{ marginBottom: 8 }}>
        <span className="log-model-tag" style={{ fontSize: 11 }}>
          Deney ağırlıkları backend tahmine bağlı — filtreler canlı görünümde uygulanır
        </span>
      </div>

      <div className="viz-settings-body" style={{ gap: 12, display: "flex", flexDirection: "column" }}>
        <label className="viz-settings-field">
          <div className="viz-settings-label-row">
            <span>Orbital ağırlık (görünen skor)</span>
            <span className="viz-settings-value">{experiment.orbital.toFixed(1)}×</span>
          </div>
          <input
            type="range"
            min={0.1}
            max={3}
            step={0.1}
            value={experiment.orbital}
            onChange={(e) =>
              onExperimentChange({
                ...experiment,
                orbital: Number(e.target.value),
              })
            }
            className="viz-settings-range"
          />
        </label>

        <label className="viz-settings-field">
          <div className="viz-settings-label-row">
            <span>Malzeme / yere düşme ağırlığı</span>
            <span className="viz-settings-value">{experiment.material.toFixed(1)}×</span>
          </div>
          <input
            type="range"
            min={0.1}
            max={3}
            step={0.1}
            value={experiment.material}
            onChange={(e) =>
              onExperimentChange({
                ...experiment,
                material: Number(e.target.value),
              })
            }
            className="viz-settings-range"
          />
        </label>

        <div>
          <div className="panel-title" style={{ fontSize: 12, marginBottom: 6 }}>
            DISCOS sınıfı
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, maxHeight: 72, overflowY: "auto" }}>
            {filterOptions.classes.length === 0 ? (
              <span style={{ opacity: 0.7, fontSize: 12 }}>Veri yok — önce tahmin + DISCOS birleşimi</span>
            ) : (
              filterOptions.classes.map((c) => {
                const on = filters.objectClasses.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    className="user-participation-btn"
                    style={{
                      fontSize: 11,
                      opacity: on ? 1 : 0.65,
                      border: on ? "1px solid #0fa" : "1px solid #333",
                    }}
                    onClick={() =>
                      onFiltersChange({
                        ...filters,
                        objectClasses: toggleInList(filters.objectClasses, c),
                      })
                    }
                  >
                    {c.length > 28 ? `${c.slice(0, 26)}…` : c}
                  </button>
                );
              })
            )}
          </div>
        </div>

        <div>
          <div className="panel-title" style={{ fontSize: 12, marginBottom: 6 }}>
            Görev (mission)
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, maxHeight: 72, overflowY: "auto" }}>
            {filterOptions.missions.length === 0 ? (
              <span style={{ opacity: 0.7, fontSize: 12 }}>—</span>
            ) : (
              filterOptions.missions.slice(0, 24).map((m) => {
                const on = filters.missions.includes(m);
                return (
                  <button
                    key={m}
                    type="button"
                    className="user-participation-btn"
                    style={{
                      fontSize: 11,
                      opacity: on ? 1 : 0.65,
                      border: on ? "1px solid #0af" : "1px solid #333",
                    }}
                    onClick={() =>
                      onFiltersChange({
                        ...filters,
                        missions: toggleInList(filters.missions, m),
                      })
                    }
                  >
                    {m.length > 24 ? `${m.slice(0, 22)}…` : m}
                  </button>
                );
              })
            )}
          </div>
        </div>

        <label className="viz-settings-check">
          <input
            type="checkbox"
            checked={filters.includeUnknownDiscos}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                includeUnknownDiscos: e.target.checked,
              })
            }
          />
          DISCOS bilinmeyenleri göster
        </label>

        <label className="viz-settings-check">
          <input
            type="checkbox"
            checked={filters.massFilterEnabled}
            onChange={(e) =>
              onFiltersChange({
                ...filters,
                massFilterEnabled: e.target.checked,
              })
            }
          />
          Kütle aralığı (kg)
        </label>
        {filters.massFilterEnabled ? (
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <input
              type="number"
              min={0}
              step={10}
              value={filters.massMinKg}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  massMinKg: Number(e.target.value),
                })
              }
              style={{ width: 88, padding: 4, fontSize: 12 }}
              aria-label="Min kütle kg"
            />
            <span style={{ fontSize: 12 }}>—</span>
            <input
              type="number"
              min={0}
              step={10}
              value={filters.massMaxKg}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  massMaxKg: Number(e.target.value),
                })
              }
              style={{ width: 88, padding: 4, fontSize: 12 }}
              aria-label="Max kütle kg"
            />
          </div>
        ) : null}

        <div>
          <div className="panel-title" style={{ fontSize: 12, marginBottom: 6 }}>
            Geri bildirim (tehdit)
          </div>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, maxHeight: 200, overflowY: "auto" }}>
            {threats.slice(0, 8).map((t) => (
              <li
                key={t.pair_id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 11,
                  padding: "6px 0",
                  borderBottom: "1px solid #222",
                }}
              >
                <span style={{ flex: 1, minWidth: 0 }}>
                  {t.hedef_uydu} ↔ {t.yaklasan_cop.slice(0, 18)}
                  {t.yaklasan_cop.length > 18 ? "…" : ""}
                </span>
                <button
                  type="button"
                  className="user-participation-btn"
                  disabled={feedbackBusyId === t.pair_id}
                  title="Uygun"
                  onClick={() => onFeedback("up", t)}
                  style={{ padding: "2px 8px" }}
                >
                  +
                </button>
                <button
                  type="button"
                  className="user-participation-btn"
                  disabled={feedbackBusyId === t.pair_id}
                  title="Şüpheli"
                  onClick={() => onFeedback("down", t)}
                  style={{ padding: "2px 8px" }}
                >
                  −
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

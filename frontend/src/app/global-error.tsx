"use client";

export default function GlobalError({
  error: _error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="tr">
      <body style={{ margin: 0, background: "#0a0c0f", color: "#9edce2" }}>
        <div
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "1rem",
            fontFamily: "system-ui, sans-serif",
            padding: "1.5rem",
          }}
        >
          <h1 style={{ fontSize: "1rem", margin: 0, color: "#00e8f3" }}>
            Uygulama başlatılamadı
          </h1>
          <p style={{ margin: 0, fontSize: "0.85rem", textAlign: "center", maxWidth: "28rem" }}>
            Kök düzeyde bir hata oluştu. Yenilemeyi deneyin.
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              padding: "0.5rem 1rem",
              border: "1px solid rgba(0, 220, 230, 0.5)",
              background: "rgba(0, 220, 230, 0.12)",
              color: "#00f3ff",
              cursor: "pointer",
              fontWeight: 700,
            }}
          >
            Tekrar dene
          </button>
        </div>
      </body>
    </html>
  );
}

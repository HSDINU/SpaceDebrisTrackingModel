"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "1rem",
        background: "#0a0c0f",
        color: "#9edce2",
        fontFamily: "system-ui, sans-serif",
        padding: "1.5rem",
      }}
    >
      <h1 style={{ fontSize: "1rem", margin: 0, color: "#00e8f3" }}>
        Sayfa yüklenirken hata oluştu
      </h1>
      <p style={{ margin: 0, fontSize: "0.85rem", textAlign: "center", maxWidth: "28rem" }}>
        Arayüz beklenmedik şekilde durdu. Alttaki düğmeyle yeniden deneyebilir veya sayfayı
        yenileyebilirsiniz.
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
  );
}

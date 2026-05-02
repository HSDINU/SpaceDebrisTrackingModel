import { existsSync, statSync } from "fs";

/** Kaynak dosyaların mtime + boyut birleşimi — içerik değişmediyse aynı kalır. */
export function buildSourceSignature(paths: string[]): string {
  return paths
    .map((p) => {
      if (!existsSync(p)) return "∅";
      try {
        const st = statSync(p);
        return `${st.mtimeMs}:${st.size}`;
      } catch {
        return "err";
      }
    })
    .join("|");
}

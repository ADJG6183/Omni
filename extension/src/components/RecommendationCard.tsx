import type { AnalysisResponse } from "../utils/apiClient"

const LABEL_COLORS: Record<string, string> = {
  BUY_NOW: "#16a34a",
  WAIT_FOR_DROP: "#2563eb",
  WATCH_CLOSELY: "#d97706",
  AVOID_THIS_DEAL: "#dc2626",
  INSUFFICIENT_DATA: "#6b7280",
}

function fmt(n: number | null | undefined): string {
  if (n == null) return "—"
  return `$${n.toFixed(2)}`
}

export function RecommendationCard({ data }: { data: AnalysisResponse }) {
  const color = LABEL_COLORS[data.recommendation] ?? "#6b7280"

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", fontSize: 14, padding: 16, width: 300 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: "#6b7280", textTransform: "uppercase", letterSpacing: 1 }}>
          Omni Verdict
        </span>
      </div>

      <div
        style={{
          background: color,
          color: "#fff",
          borderRadius: 8,
          padding: "10px 14px",
          fontWeight: 700,
          fontSize: 18,
          marginBottom: 14,
        }}>
        {data.recommendation_label}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px", marginBottom: 14 }}>
        <PriceLine label="Current" value={fmt(data.current_price)} />
        <PriceLine label="30d Average" value={fmt(data.average_price_30d)} />
        <PriceLine label="Lowest Seen" value={fmt(data.lowest_price_seen)} />
        <PriceLine label="Highest Seen" value={fmt(data.highest_price_seen)} />
      </div>

      <div style={{ fontSize: 12, color: "#374151", marginBottom: 6, fontWeight: 600 }}>Why Omni says this:</div>
      <ul style={{ margin: 0, paddingLeft: 16, color: "#4b5563", fontSize: 13 }}>
        {data.explanation.map((line, i) => (
          <li key={i} style={{ marginBottom: 4 }}>
            {line}
          </li>
        ))}
      </ul>

      <div style={{ marginTop: 12, fontSize: 11, color: "#9ca3af" }}>
        Confidence: {data.confidence} · {data.model_version}
      </div>
    </div>
  )
}

function PriceLine({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span style={{ color: "#6b7280", fontSize: 12 }}>{label}</span>
      <span style={{ fontWeight: 600, fontSize: 13 }}>{value}</span>
    </>
  )
}

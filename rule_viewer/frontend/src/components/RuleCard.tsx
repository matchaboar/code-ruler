import { useNavigate } from "react-router-dom";
import type { RuleListItem } from "../api/client";

interface RuleCardProps {
  rule: RuleListItem;
}

const cardStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "2fr 1fr 100px 100px 80px 60px",
  alignItems: "center",
  gap: "12px",
  padding: "14px 20px",
  borderBottom: "1px solid #e2e8f0",
  cursor: "pointer",
  transition: "background 0.15s",
};

const slugStyle: React.CSSProperties = {
  fontFamily: "monospace",
  fontSize: "13px",
  color: "#64748b",
};

const titleStyle: React.CSSProperties = {
  fontWeight: 600,
  fontSize: "14px",
};

const categoryColors: Record<string, string> = {
  correctness: "#3b82f6",
  security: "#ef4444",
  performance: "#f59e0b",
  style: "#8b5cf6",
  maintainability: "#10b981",
};

const severityColors: Record<string, string> = {
  error: "#ef4444",
  warning: "#f59e0b",
  info: "#3b82f6",
  hint: "#94a3b8",
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: "12px",
        fontSize: "12px",
        fontWeight: 600,
        background: `${color}18`,
        color,
        textTransform: "capitalize",
      }}
    >
      {label}
    </span>
  );
}

export function RuleCard({ rule }: RuleCardProps) {
  const navigate = useNavigate();

  return (
    <div
      style={cardStyle}
      onClick={() => navigate(`/rules/${rule.slug}`)}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.background = "#f8fafc";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background = "transparent";
      }}
    >
      <div>
        <div style={titleStyle}>{rule.title}</div>
        <div style={slugStyle}>{rule.slug}</div>
      </div>
      <div>
        <Badge
          label={rule.category}
          color={categoryColors[rule.category] ?? "#64748b"}
        />
      </div>
      <div>
        <Badge
          label={rule.severity}
          color={severityColors[rule.severity] ?? "#64748b"}
        />
      </div>
      <div style={{ fontSize: "13px", color: "#64748b" }}>
        {rule.provenance_count} source{rule.provenance_count !== 1 ? "s" : ""}
      </div>
      <div style={{ fontSize: "13px", color: rule.is_active ? "#10b981" : "#94a3b8" }}>
        {rule.is_active ? "Active" : "Inactive"}
      </div>
      <div style={{ fontSize: "13px", color: "#64748b" }}>
        {rule.has_decorator ? "Fn" : ""}
      </div>
    </div>
  );
}

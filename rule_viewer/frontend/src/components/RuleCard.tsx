import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { generateTestSprite, fetchJobStatus, type RuleListItem } from "../api/client";

interface RuleCardProps {
  rule: RuleListItem;
}

const cardStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "2fr 1fr 100px 100px 80px 60px 30px auto",
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
  const [tsStatus, setTsStatus] = useState<"idle" | "generating" | "done" | "error">("idle");

  const handleTestSprite = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (tsStatus === "generating") return;
    setTsStatus("generating");
    generateTestSprite(rule.slug)
      .then((resp) => {
        const poll = setInterval(() => {
          fetchJobStatus(resp.job_id)
            .then((job) => {
              if (job.status === "completed") {
                clearInterval(poll);
                setTsStatus("done");
              } else if (job.status === "failed") {
                clearInterval(poll);
                setTsStatus("error");
              }
            })
            .catch(() => {
              clearInterval(poll);
              setTsStatus("error");
            });
        }, 2000);
      })
      .catch(() => setTsStatus("error"));
  };

  const tsButtonLabel = tsStatus === "generating" ? "Generating..." : tsStatus === "done" ? "Done" : tsStatus === "error" ? "Failed" : "TestSprite";
  const tsButtonColor = tsStatus === "generating" ? "#f59e0b" : tsStatus === "done" ? "#22c55e" : tsStatus === "error" ? "#ef4444" : "#10b981";

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
      <div style={{ fontSize: "13px", color: rule.has_enforcer ? "#3b82f6" : "#e2e8f0" }} title={rule.has_enforcer ? "Has enforcer" : ""}>
        {rule.has_enforcer ? "E" : ""}
      </div>
      <div>
        <button
          onClick={handleTestSprite}
          disabled={tsStatus === "generating"}
          style={{
            padding: "3px 8px",
            fontSize: "11px",
            fontWeight: 600,
            background: `${tsButtonColor}18`,
            color: tsButtonColor,
            border: `1px solid ${tsButtonColor}40`,
            borderRadius: "6px",
            cursor: tsStatus === "generating" ? "wait" : "pointer",
            whiteSpace: "nowrap",
          }}
        >
          {tsButtonLabel}
        </button>
      </div>
    </div>
  );
}

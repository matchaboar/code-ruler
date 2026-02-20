import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchRule,
  fetchProvenance,
  type RuleDetail,
  type ProvenanceItem,
} from "../api/client";
import { CodeBlock } from "../components/CodeBlock";
import { ProvenanceCard } from "../components/ProvenanceCard";

const backStyle: React.CSSProperties = {
  fontSize: "14px",
  color: "#4361ee",
  marginBottom: "16px",
  display: "inline-block",
};

const headerStyle: React.CSSProperties = {
  marginBottom: "32px",
};

const titleStyle: React.CSSProperties = {
  fontSize: "28px",
  fontWeight: 700,
  marginBottom: "4px",
};

const slugStyle: React.CSSProperties = {
  fontFamily: "monospace",
  fontSize: "14px",
  color: "#64748b",
  marginBottom: "12px",
};

const badgeRowStyle: React.CSSProperties = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  alignItems: "center",
  marginBottom: "8px",
};

const sectionStyle: React.CSSProperties = {
  marginBottom: "32px",
};

const sectionTitle: React.CSSProperties = {
  fontSize: "18px",
  fontWeight: 600,
  marginBottom: "12px",
  color: "#1e293b",
};

const textBlock: React.CSSProperties = {
  fontSize: "15px",
  lineHeight: 1.7,
  color: "#334155",
  whiteSpace: "pre-wrap",
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
        padding: "3px 12px",
        borderRadius: "12px",
        fontSize: "13px",
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

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 12px",
        borderRadius: "12px",
        fontSize: "13px",
        fontWeight: 600,
        background: active ? "#dcfce7" : "#f1f5f9",
        color: active ? "#166534" : "#64748b",
      }}
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}

function CollapsibleCode({
  title,
  code,
  language = "python",
}: {
  title: string;
  code: string;
  language?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginBottom: "12px" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "10px 16px",
          cursor: "pointer",
          fontSize: "14px",
          fontWeight: 600,
          color: "#334155",
          width: "100%",
          textAlign: "left",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>{title}</span>
        <span style={{ color: "#94a3b8" }}>{open ? "Collapse" : "Expand"}</span>
      </button>
      {open && (
        <div style={{ marginTop: "8px" }}>
          <CodeBlock code={code} language={language} />
        </div>
      )}
    </div>
  );
}

export function RuleDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [rule, setRule] = useState<RuleDetail | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;

    setLoading(true);
    setError(null);

    Promise.all([fetchRule(slug), fetchProvenance(slug)])
      .then(([ruleData, provData]) => {
        setRule(ruleData);
        setProvenance(provData);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load rule");
      })
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return <div style={{ textAlign: "center", padding: "48px", color: "#94a3b8" }}>Loading...</div>;
  }

  if (error || !rule) {
    return (
      <div style={{ textAlign: "center", padding: "48px", color: "#ef4444" }}>
        {error ?? "Rule not found"}
      </div>
    );
  }

  return (
    <div>
      <Link to="/" style={backStyle}>
        &larr; Back to rules
      </Link>

      <div style={headerStyle}>
        <h1 style={titleStyle}>{rule.title}</h1>
        <div style={slugStyle}>{rule.slug}</div>
        <div style={badgeRowStyle}>
          <Badge
            label={rule.category}
            color={categoryColors[rule.category] ?? "#64748b"}
          />
          <Badge
            label={rule.severity}
            color={severityColors[rule.severity] ?? "#64748b"}
          />
          <StatusBadge active={rule.is_active} />
          <span style={{ fontSize: "13px", color: "#94a3b8" }}>
            v{rule.version}
          </span>
        </div>
      </div>

      {/* Description */}
      <div style={sectionStyle}>
        <h2 style={sectionTitle}>Description</h2>
        <div style={textBlock}>{rule.description}</div>
      </div>

      {/* Examples */}
      {(rule.positive_example || rule.negative_example) && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Examples</h2>
          {rule.positive_example && (
            <div
              style={{
                borderLeft: "4px solid #22c55e",
                borderRadius: "8px",
                paddingLeft: "0",
                marginBottom: "16px",
                overflow: "hidden",
              }}
            >
              <CodeBlock
                code={rule.positive_example}
                language="python"
                title="Good"
              />
            </div>
          )}
          {rule.negative_example && (
            <div
              style={{
                borderLeft: "4px solid #ef4444",
                borderRadius: "8px",
                paddingLeft: "0",
                overflow: "hidden",
              }}
            >
              <CodeBlock
                code={rule.negative_example}
                language="python"
                title="Bad"
              />
            </div>
          )}
        </div>
      )}

      {/* Rationale */}
      <div style={sectionStyle}>
        <h2 style={sectionTitle}>Rationale</h2>
        <div style={textBlock}>{rule.rationale}</div>
      </div>

      {/* Constraints */}
      {rule.constraints && rule.constraints.length > 0 && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Constraints</h2>
          <ul style={{ paddingLeft: "24px", color: "#334155", fontSize: "15px" }}>
            {rule.constraints.map((c, i) => (
              <li key={i} style={{ marginBottom: "4px" }}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Function type sources */}
      {(rule.decorator_source || rule.linter_source) && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Implementation</h2>
          {rule.decorator_name && (
            <p style={{ fontSize: "14px", color: "#64748b", marginBottom: "12px" }}>
              Decorator: <code style={{ fontWeight: 600 }}>{rule.decorator_name}</code>
            </p>
          )}
          {rule.decorator_source && (
            <CollapsibleCode
              title="Decorator Source"
              code={rule.decorator_source}
            />
          )}
          {rule.linter_source && (
            <CollapsibleCode
              title="Linter Source"
              code={rule.linter_source}
            />
          )}
        </div>
      )}

      {/* Provenance */}
      <div style={sectionStyle}>
        <h2 style={sectionTitle}>
          Provenance ({provenance.length} source{provenance.length !== 1 ? "s" : ""})
        </h2>
        {provenance.length === 0 ? (
          <div style={{ color: "#94a3b8", fontSize: "14px" }}>
            No provenance records found for this rule.
          </div>
        ) : (
          provenance.map((item, i) => (
            <ProvenanceCard key={i} item={item} />
          ))
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchEnforcers, fetchEnforcer, type EnforcerListItem, type EnforcerDetail } from "../api/client";
import { CodeBlock } from "../components/CodeBlock";
import { TabBar } from "../components/TabBar";

const statusColors: Record<string, string> = {
  passed: "#22c55e",
  failed: "#ef4444",
  generating: "#f59e0b",
  pending: "#94a3b8",
};

const severityColors: Record<string, string> = {
  error: "#ef4444",
  warning: "#f59e0b",
  info: "#3b82f6",
};

const categoryColors: Record<string, string> = {
  correctness: "#3b82f6",
  security: "#ef4444",
  performance: "#f59e0b",
  style: "#8b5cf6",
  maintainability: "#10b981",
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

const headerRowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "2fr 1fr 100px 100px 80px 80px",
  alignItems: "center",
  gap: "12px",
  padding: "10px 20px",
  borderBottom: "2px solid #e2e8f0",
  fontSize: "12px",
  fontWeight: 700,
  color: "#64748b",
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

const rowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "2fr 1fr 100px 100px 80px 80px",
  alignItems: "center",
  gap: "12px",
  padding: "14px 20px",
  borderBottom: "1px solid #e2e8f0",
  cursor: "pointer",
  transition: "background 0.15s",
};

function ExpandedDetail({
  detail,
  loading,
  onViewRule,
}: {
  detail: EnforcerDetail | null;
  loading: boolean;
  onViewRule: (ev: React.MouseEvent) => void;
}) {
  const [tab, setTab] = useState("source");

  if (loading) {
    return (
      <div style={{ padding: "16px 20px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
        <div style={{ color: "#94a3b8" }}>Loading detail...</div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div style={{ padding: "16px 20px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
        <div style={{ color: "#ef4444" }}>Failed to load enforcer detail.</div>
      </div>
    );
  }

  const tabs = [
    { key: "source", label: "Source" },
    { key: "diff", label: "Diff", disabled: !detail.diff },
    { key: "decorator", label: "Decorator", disabled: !detail.decorator_source },
    { key: "test", label: "Test Output", disabled: !detail.test_output },
    { key: "traces", label: "Traces", disabled: !detail.dd_traces?.length },
  ];

  return (
    <div style={{ padding: "16px 20px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
      <TabBar tabs={tabs} active={tab} onChange={setTab} />

      {tab === "source" && detail.enforcer_source && (
        <CodeBlock code={detail.enforcer_source} language="python" />
      )}

      {tab === "diff" && detail.diff && (
        <CodeBlock code={detail.diff} language="diff" />
      )}

      {tab === "decorator" && detail.decorator_source && (
        <CodeBlock code={detail.decorator_source} language="python" />
      )}

      {tab === "test" && detail.test_output && (
        <pre style={{ background: "#1e293b", color: "#e2e8f0", padding: "12px", borderRadius: "8px", fontSize: "13px", overflow: "auto", whiteSpace: "pre-wrap" }}>
          {detail.test_output}
        </pre>
      )}

      {tab === "traces" && detail.dd_traces && detail.dd_traces.length > 0 && (
        <pre style={{ background: "#1e293b", color: "#e2e8f0", padding: "12px", borderRadius: "8px", fontSize: "12px", overflow: "auto" }}>
          {JSON.stringify(detail.dd_traces, null, 2)}
        </pre>
      )}

      <button
        onClick={onViewRule}
        style={{
          marginTop: "12px",
          padding: "6px 16px",
          background: "#3b82f6",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: "pointer",
          fontSize: "13px",
        }}
      >
        View Rule Detail
      </button>
    </div>
  );
}

export function EnforcerPage() {
  const [enforcers, setEnforcers] = useState<EnforcerListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedSlug, setExpandedSlug] = useState<string | null>(null);
  const [detail, setDetail] = useState<EnforcerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchEnforcers()
      .then(setEnforcers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleRowClick = (slug: string) => {
    if (expandedSlug === slug) {
      setExpandedSlug(null);
      setDetail(null);
      return;
    }
    setExpandedSlug(slug);
    setDetailLoading(true);
    fetchEnforcer(slug)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  };

  if (loading) {
    return <div style={{ textAlign: "center", padding: "48px", color: "#94a3b8" }}>Loading...</div>;
  }

  return (
    <div>
      <h1 style={{ fontSize: "24px", fontWeight: 700, marginBottom: "24px" }}>Enforcers</h1>
      {enforcers.length === 0 ? (
        <div style={{ color: "#94a3b8", textAlign: "center", padding: "48px" }}>
          No enforcer scripts generated yet. Go to a rule detail page and click "Add Enforcer".
        </div>
      ) : (
        <div style={{ border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden" }}>
          <div style={headerRowStyle}>
            <div>Rule</div>
            <div>Category</div>
            <div>Severity</div>
            <div>Status</div>
            <div>Type</div>
            <div>Attempts</div>
          </div>
          {enforcers.map((e) => (
            <div key={e.rule_slug}>
              <div
                style={rowStyle}
                onClick={() => handleRowClick(e.rule_slug)}
                onMouseEnter={(ev) => { (ev.currentTarget as HTMLElement).style.background = "#f8fafc"; }}
                onMouseLeave={(ev) => { (ev.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>{e.rule_title}</div>
                  <div style={{ fontFamily: "monospace", fontSize: "12px", color: "#64748b" }}>{e.rule_slug}</div>
                </div>
                <div>
                  <Badge label={e.category} color={categoryColors[e.category] ?? "#64748b"} />
                </div>
                <div>
                  <Badge label={e.severity} color={severityColors[e.severity] ?? "#64748b"} />
                </div>
                <div>
                  <Badge label={e.status} color={statusColors[e.status] ?? "#94a3b8"} />
                </div>
                <div style={{ fontSize: "13px", color: "#64748b" }}>{e.check_type}</div>
                <div style={{ fontSize: "13px", color: "#64748b" }}>{e.attempt_count}</div>
              </div>
              {expandedSlug === e.rule_slug && (
                <ExpandedDetail
                  detail={detail}
                  loading={detailLoading}
                  onViewRule={(ev) => { ev.stopPropagation(); navigate(`/rules/${e.rule_slug}`); }}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

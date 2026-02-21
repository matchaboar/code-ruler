import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchTestSpriteResults,
  fetchTestSpriteDetail,
  type TestSpriteListItem,
  type TestSpriteDetail,
} from "../api/client";
import { CodeBlock } from "../components/CodeBlock";
import { DiffView } from "../components/DiffView";
import { TabBar } from "../components/TabBar";

const statusColors: Record<string, string> = {
  completed: "#22c55e",
  failed: "#ef4444",
  running: "#f59e0b",
  cloning: "#f59e0b",
  generating: "#f59e0b",
  pending: "#94a3b8",
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
  gridTemplateColumns: "2fr 2fr 100px 160px",
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
  gridTemplateColumns: "2fr 2fr 100px 160px",
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
  detail: TestSpriteDetail | null;
  loading: boolean;
  onViewRule: (ev: React.MouseEvent) => void;
}) {
  const [tab, setTab] = useState("diff");

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
        <div style={{ color: "#ef4444" }}>Failed to load detail.</div>
      </div>
    );
  }

  const tabs = [
    { key: "diff", label: "Diff", disabled: !detail.diff },
    { key: "tests", label: "Generated Tests", disabled: !detail.generated_tests },
    { key: "results", label: "Test Results", disabled: !detail.test_results },
    { key: "plan", label: "Test Plan", disabled: !detail.test_plan },
  ];

  // Default to first non-disabled tab
  const activeTab = tabs.find((t) => t.key === tab && !t.disabled) ? tab : tabs.find((t) => !t.disabled)?.key ?? "diff";

  return (
    <div style={{ padding: "16px 20px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
      {detail.error_message && (
        <div style={{ color: "#ef4444", marginBottom: "12px", fontSize: "13px" }}>
          Error: {detail.error_message}
        </div>
      )}

      <TabBar tabs={tabs} active={activeTab} onChange={setTab} />

      {activeTab === "diff" && detail.diff && (
        <DiffView diffHunk={detail.diff} />
      )}

      {activeTab === "tests" && detail.generated_tests && (
        <CodeBlock code={detail.generated_tests} language="python" />
      )}

      {activeTab === "results" && detail.test_results && (
        <pre style={{ background: "#1e293b", color: "#e2e8f0", padding: "12px", borderRadius: "8px", fontSize: "12px", overflow: "auto" }}>
          {JSON.stringify(detail.test_results, null, 2)}
        </pre>
      )}

      {activeTab === "plan" && detail.test_plan && (
        <pre style={{ background: "#1e293b", color: "#e2e8f0", padding: "12px", borderRadius: "8px", fontSize: "12px", overflow: "auto" }}>
          {JSON.stringify(detail.test_plan, null, 2)}
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

export function TestSpritePage({ repoId }: { repoId: number | null }) {
  const [results, setResults] = useState<TestSpriteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<TestSpriteDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const navigate = useNavigate();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadResults = () => {
    fetchTestSpriteResults(repoId ?? undefined)
      .then(setResults)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setLoading(true);
    loadResults();
  }, [repoId]);

  // Auto-refresh while any result is in non-terminal status
  useEffect(() => {
    const hasInProgress = results.some(
      (r) => !["completed", "failed"].includes(r.status)
    );
    if (hasInProgress) {
      intervalRef.current = setInterval(loadResults, 5000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [results]);

  const handleRowClick = (id: number) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    setDetailLoading(true);
    fetchTestSpriteDetail(id)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  };

  if (loading) {
    return <div style={{ textAlign: "center", padding: "48px", color: "#94a3b8" }}>Loading...</div>;
  }

  return (
    <div>
      <h1 style={{ fontSize: "24px", fontWeight: 700, marginBottom: "24px" }}>Tests</h1>
      {results.length === 0 ? (
        <div style={{ color: "#94a3b8", textAlign: "center", padding: "48px" }}>
          No TestSprite results yet. Go to the Rules page and click "TestSprite" on a rule card.
        </div>
      ) : (
        <div style={{ border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden" }}>
          <div style={headerRowStyle}>
            <div>Rule</div>
            <div>Repo</div>
            <div>Status</div>
            <div>Created</div>
          </div>
          {results.map((r) => (
            <div key={r.id}>
              <div
                style={rowStyle}
                onClick={() => handleRowClick(r.id)}
                onMouseEnter={(ev) => { (ev.currentTarget as HTMLElement).style.background = "#f8fafc"; }}
                onMouseLeave={(ev) => { (ev.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: "14px" }}>{r.rule_title}</div>
                  <div style={{ fontFamily: "monospace", fontSize: "12px", color: "#64748b" }}>{r.rule_slug}</div>
                </div>
                <div style={{ fontSize: "13px", color: "#64748b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {r.repo_url}
                </div>
                <div>
                  <Badge label={r.status} color={statusColors[r.status] ?? "#94a3b8"} />
                </div>
                <div style={{ fontSize: "13px", color: "#64748b" }}>
                  {new Date(r.created_at).toLocaleString()}
                </div>
              </div>
              {expandedId === r.id && (
                <ExpandedDetail
                  detail={detail}
                  loading={detailLoading}
                  onViewRule={(ev) => { ev.stopPropagation(); navigate(`/rules/${r.rule_slug}`); }}
                />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

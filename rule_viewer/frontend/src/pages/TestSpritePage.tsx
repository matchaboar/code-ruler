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

const PAGE_SIZE = 5;

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

function StatusSummary({ items }: { items: TestSpriteListItem[] }) {
  const counts: Record<string, number> = {};
  for (const item of items) {
    counts[item.status] = (counts[item.status] || 0) + 1;
  }
  return (
    <span style={{ display: "inline-flex", gap: "6px" }}>
      {Object.entries(counts).map(([status, count]) => (
        <Badge key={status} label={`${count} ${status}`} color={statusColors[status] ?? "#94a3b8"} />
      ))}
    </span>
  );
}

interface RuleGroup {
  slug: string;
  title: string;
  items: TestSpriteListItem[];
}

function groupByRule(results: TestSpriteListItem[]): RuleGroup[] {
  const map = new Map<string, RuleGroup>();
  for (const r of results) {
    if (!map.has(r.rule_slug)) {
      map.set(r.rule_slug, { slug: r.rule_slug, title: r.rule_title, items: [] });
    }
    map.get(r.rule_slug)!.items.push(r);
  }
  return Array.from(map.values());
}

const rowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "2fr 100px 160px",
  alignItems: "center",
  gap: "12px",
  padding: "12px 20px",
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

function PaginationBar({ page, totalPages, onPageChange }: { page: number; totalPages: number; onPageChange: (p: number) => void }) {
  if (totalPages <= 1) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", padding: "10px 20px", borderTop: "1px solid #e2e8f0" }}>
      <button
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        style={{
          padding: "4px 12px",
          fontSize: "13px",
          border: "1px solid #e2e8f0",
          borderRadius: "6px",
          background: page <= 1 ? "#f1f5f9" : "#fff",
          color: page <= 1 ? "#94a3b8" : "#334155",
          cursor: page <= 1 ? "default" : "pointer",
        }}
      >
        Prev
      </button>
      <span style={{ fontSize: "13px", color: "#64748b" }}>
        {page} / {totalPages}
      </span>
      <button
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        style={{
          padding: "4px 12px",
          fontSize: "13px",
          border: "1px solid #e2e8f0",
          borderRadius: "6px",
          background: page >= totalPages ? "#f1f5f9" : "#fff",
          color: page >= totalPages ? "#94a3b8" : "#334155",
          cursor: page >= totalPages ? "default" : "pointer",
        }}
      >
        Next
      </button>
    </div>
  );
}

function RuleAccordion({
  group,
  isOpen,
  onToggle,
  expandedId,
  detail,
  detailLoading,
  onRowClick,
  navigate,
}: {
  group: RuleGroup;
  isOpen: boolean;
  onToggle: () => void;
  expandedId: number | null;
  detail: TestSpriteDetail | null;
  detailLoading: boolean;
  onRowClick: (id: number) => void;
  navigate: ReturnType<typeof useNavigate>;
}) {
  const [page, setPage] = useState(1);
  const totalPages = Math.ceil(group.items.length / PAGE_SIZE);
  const pageItems = group.items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Reset page when accordion closes/opens
  useEffect(() => {
    if (!isOpen) setPage(1);
  }, [isOpen]);

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: "10px", overflow: "hidden" }}>
      {/* Accordion header */}
      <div
        onClick={onToggle}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 20px",
          background: isOpen ? "#f1f5f9" : "#fff",
          cursor: "pointer",
          transition: "background 0.15s",
          userSelect: "none",
        }}
        onMouseEnter={(ev) => { (ev.currentTarget as HTMLElement).style.background = "#f1f5f9"; }}
        onMouseLeave={(ev) => { if (!isOpen) (ev.currentTarget as HTMLElement).style.background = "#fff"; }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
          <span style={{
            display: "inline-block",
            transition: "transform 0.2s",
            transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
            fontSize: "12px",
            color: "#64748b",
          }}>
            &#9654;
          </span>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 600, fontSize: "14px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {group.title}
            </div>
            <div style={{ fontFamily: "monospace", fontSize: "11px", color: "#94a3b8" }}>
              {group.slug}
            </div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexShrink: 0 }}>
          <StatusSummary items={group.items} />
          <span style={{ fontSize: "12px", color: "#94a3b8" }}>
            {group.items.length} run{group.items.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Expanded content */}
      {isOpen && (
        <>
          <div style={{
            display: "grid",
            gridTemplateColumns: "2fr 100px 160px",
            alignItems: "center",
            gap: "12px",
            padding: "8px 20px",
            borderTop: "1px solid #e2e8f0",
            borderBottom: "1px solid #e2e8f0",
            fontSize: "11px",
            fontWeight: 700,
            color: "#94a3b8",
            textTransform: "uppercase",
            letterSpacing: "0.5px",
            background: "#fafbfc",
          }}>
            <div>Repo</div>
            <div>Status</div>
            <div>Created</div>
          </div>
          {pageItems.map((r) => (
            <div key={r.id}>
              <div
                style={rowStyle}
                onClick={() => onRowClick(r.id)}
                onMouseEnter={(ev) => { (ev.currentTarget as HTMLElement).style.background = "#f8fafc"; }}
                onMouseLeave={(ev) => { (ev.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <div style={{ fontSize: "13px", color: "#334155", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
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
          <PaginationBar page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}

export function TestSpritePage({ repoId }: { repoId: number | null }) {
  const [results, setResults] = useState<TestSpriteListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openSlug, setOpenSlug] = useState<string | null>(null);
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

  const groups = groupByRule(results);

  return (
    <div>
      <h1 style={{ fontSize: "24px", fontWeight: 700, marginBottom: "24px" }}>Tests</h1>
      {results.length === 0 ? (
        <div style={{ color: "#94a3b8", textAlign: "center", padding: "48px" }}>
          No TestSprite results yet. Go to the Rules page and click "TestSprite" on a rule card.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {groups.map((group) => (
            <RuleAccordion
              key={group.slug}
              group={group}
              isOpen={openSlug === group.slug}
              onToggle={() => {
                setOpenSlug(openSlug === group.slug ? null : group.slug);
                setExpandedId(null);
                setDetail(null);
              }}
              expandedId={expandedId}
              detail={detail}
              detailLoading={detailLoading}
              onRowClick={handleRowClick}
              navigate={navigate}
            />
          ))}
        </div>
      )}
    </div>
  );
}

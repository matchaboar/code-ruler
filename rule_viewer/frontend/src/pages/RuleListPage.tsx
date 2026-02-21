import { useEffect, useState, useCallback } from "react";
import {
  fetchRules,
  fetchStats,
  type RuleListItem,
  type RuleListParams,
  type Stats,
} from "../api/client";
import { RuleCard } from "../components/RuleCard";
import { RuleFilters } from "../components/RuleFilters";

const headingStyle: React.CSSProperties = {
  fontSize: "28px",
  fontWeight: 700,
  marginBottom: "4px",
};

const subStyle: React.CSSProperties = {
  fontSize: "14px",
  color: "#64748b",
  marginBottom: "24px",
};

const tableHeaderStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "2fr 1fr 100px 100px 80px 60px 30px auto",
  gap: "12px",
  padding: "10px 20px",
  fontSize: "12px",
  fontWeight: 600,
  color: "#64748b",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  borderBottom: "2px solid #e2e8f0",
};

const tableContainerStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: "10px",
  border: "1px solid #e2e8f0",
  overflow: "hidden",
};

const emptyStyle: React.CSSProperties = {
  textAlign: "center",
  padding: "48px 24px",
  color: "#94a3b8",
  fontSize: "15px",
};

export function RuleListPage({ repoId }: { repoId: number | null }) {
  const [rules, setRules] = useState<RuleListItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [filters, setFilters] = useState<Omit<RuleListParams, "repoId">>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadRules = useCallback(async (params: Omit<RuleListParams, "repoId">, rid: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRules({ ...params, repoId: rid });
      setRules(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (repoId === null) return;
    fetchStats(repoId)
      .then(setStats)
      .catch(() => {});
  }, [repoId]);

  useEffect(() => {
    if (repoId === null) {
      setRules([]);
      setLoading(false);
      return;
    }
    loadRules(filters, repoId);
  }, [filters, repoId, loadRules]);

  const categories = stats ? Object.keys(stats.rules_by_category).sort() : [];
  const severities = stats ? Object.keys(stats.rules_by_severity).sort() : [];

  if (repoId === null) {
    return (
      <div>
        <h1 style={headingStyle}>Rules</h1>
        <p style={subStyle}>Select a repository from the header to view rules.</p>
      </div>
    );
  }

  return (
    <div>
      <h1 style={headingStyle}>Rules</h1>
      <p style={subStyle}>
        {stats
          ? `${stats.total_rules} rules extracted from ${stats.total_prs_processed} pull requests`
          : "Loading statistics..."}
      </p>

      <RuleFilters
        filters={filters}
        categories={categories}
        severities={severities}
        onFilterChange={setFilters}
      />

      {error && (
        <div style={{ color: "#ef4444", padding: "16px", textAlign: "center" }}>
          {error}
        </div>
      )}

      <div style={tableContainerStyle}>
        <div style={tableHeaderStyle}>
          <span>Rule</span>
          <span>Category</span>
          <span>Severity</span>
          <span>Sources</span>
          <span>Status</span>
          <span>Type</span>
          <span></span>
          <span>Tests</span>
        </div>
        {loading ? (
          <div style={emptyStyle}>Loading rules...</div>
        ) : rules.length === 0 ? (
          <div style={emptyStyle}>No rules match the current filters.</div>
        ) : (
          rules.map((rule) => <RuleCard key={rule.slug} rule={rule} />)
        )}
      </div>
    </div>
  );
}

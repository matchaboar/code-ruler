import type { RuleListParams } from "../api/client";

interface RuleFiltersProps {
  filters: RuleListParams;
  categories: string[];
  severities: string[];
  onFilterChange: (filters: RuleListParams) => void;
}

const barStyle: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "12px",
  alignItems: "center",
  padding: "16px 20px",
  background: "#fff",
  borderRadius: "10px",
  border: "1px solid #e2e8f0",
  marginBottom: "16px",
};

const selectStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: "6px",
  border: "1px solid #cbd5e1",
  fontSize: "14px",
  background: "#fff",
  color: "#334155",
  minWidth: "140px",
};

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: "6px",
  border: "1px solid #cbd5e1",
  fontSize: "14px",
  flex: "1 1 200px",
  minWidth: "200px",
};

const toggleStyle = (active: boolean): React.CSSProperties => ({
  padding: "8px 16px",
  borderRadius: "6px",
  border: `1px solid ${active ? "#4361ee" : "#cbd5e1"}`,
  background: active ? "#4361ee" : "#fff",
  color: active ? "#fff" : "#334155",
  fontSize: "13px",
  fontWeight: 600,
  cursor: "pointer",
  transition: "all 0.15s",
});

export function RuleFilters({
  filters,
  categories,
  severities,
  onFilterChange,
}: RuleFiltersProps) {
  const activeValue =
    filters.is_active === undefined ? "all" : filters.is_active ? "active" : "inactive";

  return (
    <div style={barStyle}>
      <select
        style={selectStyle}
        value={filters.category ?? ""}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            category: e.target.value || undefined,
          })
        }
      >
        <option value="">All Categories</option>
        {categories.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <select
        style={selectStyle}
        value={filters.severity ?? ""}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            severity: e.target.value || undefined,
          })
        }
      >
        <option value="">All Severities</option>
        {severities.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      <input
        type="text"
        placeholder="Search rules..."
        style={inputStyle}
        value={filters.search ?? ""}
        onChange={(e) =>
          onFilterChange({
            ...filters,
            search: e.target.value || undefined,
          })
        }
      />

      <button
        style={toggleStyle(activeValue === "all")}
        onClick={() => onFilterChange({ ...filters, is_active: undefined })}
      >
        All
      </button>
      <button
        style={toggleStyle(activeValue === "active")}
        onClick={() => onFilterChange({ ...filters, is_active: true })}
      >
        Active
      </button>
      <button
        style={toggleStyle(activeValue === "inactive")}
        onClick={() => onFilterChange({ ...filters, is_active: false })}
      >
        Inactive
      </button>
    </div>
  );
}

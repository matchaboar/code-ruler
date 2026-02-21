interface Tab {
  key: string;
  label: string;
  disabled?: boolean;
}

interface TabBarProps {
  tabs: Tab[];
  active: string;
  onChange: (key: string) => void;
}

const tabStyle: React.CSSProperties = {
  padding: "8px 16px",
  border: "none",
  background: "none",
  fontSize: "13px",
  fontWeight: 600,
  cursor: "pointer",
  borderBottom: "2px solid transparent",
  color: "#64748b",
  transition: "color 0.15s, border-color 0.15s",
};

const activeTabStyle: React.CSSProperties = {
  ...tabStyle,
  color: "#3b82f6",
  borderBottomColor: "#3b82f6",
};

const disabledTabStyle: React.CSSProperties = {
  ...tabStyle,
  color: "#cbd5e1",
  cursor: "default",
};

export function TabBar({ tabs, active, onChange }: TabBarProps) {
  return (
    <div
      style={{
        display: "flex",
        gap: "4px",
        borderBottom: "1px solid #e2e8f0",
        marginBottom: "16px",
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          style={tab.disabled ? disabledTabStyle : tab.key === active ? activeTabStyle : tabStyle}
          onClick={() => !tab.disabled && onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

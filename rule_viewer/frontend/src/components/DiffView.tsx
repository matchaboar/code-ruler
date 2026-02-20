interface DiffViewProps {
  diffHunk: string;
  filePath?: string;
}

const containerStyle: React.CSSProperties = {
  borderRadius: "8px",
  overflow: "hidden",
  border: "1px solid #e2e8f0",
  marginBottom: "16px",
  fontFamily: "'Fira Code', 'Cascadia Code', monospace",
  fontSize: "13px",
  lineHeight: 1.6,
};

const headerStyle: React.CSSProperties = {
  background: "#f1f5f9",
  padding: "8px 16px",
  fontSize: "12px",
  color: "#475569",
  borderBottom: "1px solid #e2e8f0",
  fontWeight: 600,
};

function lineStyle(type: "add" | "remove" | "context" | "header"): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: "0 16px",
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
  };
  switch (type) {
    case "add":
      return { ...base, background: "#dcfce7", color: "#166534" };
    case "remove":
      return { ...base, background: "#fef2f2", color: "#991b1b" };
    case "header":
      return { ...base, background: "#eff6ff", color: "#1e40af", fontStyle: "italic" };
    default:
      return { ...base, background: "#fff", color: "#334155" };
  }
}

function classifyLine(line: string): "add" | "remove" | "context" | "header" {
  if (line.startsWith("@@")) return "header";
  if (line.startsWith("+")) return "add";
  if (line.startsWith("-")) return "remove";
  return "context";
}

export function DiffView({ diffHunk, filePath }: DiffViewProps) {
  const lines = diffHunk.split("\n");

  return (
    <div style={containerStyle}>
      {filePath && <div style={headerStyle}>{filePath}</div>}
      <div>
        {lines.map((line, i) => {
          const type = classifyLine(line);
          return (
            <div key={i} style={lineStyle(type)}>
              {line || "\u00a0"}
            </div>
          );
        })}
      </div>
    </div>
  );
}

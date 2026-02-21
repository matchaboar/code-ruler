import { useState, useMemo } from "react";

interface DiffViewProps {
  diffHunk: string;
  filePath?: string;
}

/* ── Types ──────────────────────────────────────────────── */

interface ParsedFile {
  path: string;
  hunks: ParsedHunk[];
  isNew: boolean;
  isDeleted: boolean;
}

interface ParsedHunk {
  header: string;
  lines: ParsedLine[];
}

interface ParsedLine {
  type: "add" | "remove" | "context" | "header";
  content: string;
  oldNum: number | null;
  newNum: number | null;
}

/* ── Parser ─────────────────────────────────────────────── */

function extractFilePath(line: string): string {
  // "diff --git a/foo/bar.py b/foo/bar.py" → "foo/bar.py"
  const m = line.match(/^diff --git a\/(.+?) b\/(.+)/);
  if (m) return m[2];
  // "+++ b/foo.py" → "foo.py"
  const p = line.match(/^\+\+\+ b\/(.+)/);
  if (p) return p[1];
  return line;
}

function parseDiff(raw: string, singleFilePath?: string): ParsedFile[] {
  const lines = raw.split("\n");
  const files: ParsedFile[] = [];
  let current: ParsedFile | null = null;
  let currentHunk: ParsedHunk | null = null;
  let oldLine = 0;
  let newLine = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // New file boundary
    if (line.startsWith("diff --git ")) {
      current = { path: extractFilePath(line), hunks: [], isNew: false, isDeleted: false };
      files.push(current);
      currentHunk = null;
      continue;
    }

    // File metadata lines
    if (line.startsWith("index ") || line.startsWith("old mode") || line.startsWith("new mode")) continue;
    if (line.startsWith("new file")) { if (current) current.isNew = true; continue; }
    if (line.startsWith("deleted file")) { if (current) current.isDeleted = true; continue; }

    if (line.startsWith("--- ")) {
      // If we don't have a current file yet (single-hunk diff), create one
      if (!current) {
        current = { path: singleFilePath ?? "", hunks: [], isNew: false, isDeleted: false };
        files.push(current);
      }
      if (line === "--- /dev/null" && current) current.isNew = true;
      continue;
    }
    if (line.startsWith("+++ ")) {
      if (current && !current.path) {
        current.path = extractFilePath(line);
      }
      if (line === "+++ /dev/null" && current) current.isDeleted = true;
      continue;
    }

    // Hunk header
    const hunkMatch = line.match(/^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@(.*)/);
    if (hunkMatch) {
      if (!current) {
        current = { path: singleFilePath ?? "", hunks: [], isNew: false, isDeleted: false };
        files.push(current);
      }
      oldLine = parseInt(hunkMatch[1], 10);
      newLine = parseInt(hunkMatch[2], 10);
      const funcContext = hunkMatch[3]?.trim() ?? "";
      currentHunk = { header: funcContext ? `@@ ${funcContext}` : line, lines: [] };
      current.hunks.push(currentHunk);
      continue;
    }

    // Diff lines
    if (!currentHunk) {
      // Lines before first hunk with no file context — treat as single file
      if (!current && line.trim()) {
        current = { path: singleFilePath ?? "", hunks: [], isNew: false, isDeleted: false };
        files.push(current);
        currentHunk = { header: "", lines: [] };
        current.hunks.push(currentHunk);
      } else {
        continue;
      }
    }

    if (line.startsWith("+")) {
      currentHunk.lines.push({ type: "add", content: line.slice(1), oldNum: null, newNum: newLine++ });
    } else if (line.startsWith("-")) {
      currentHunk.lines.push({ type: "remove", content: line.slice(1), oldNum: oldLine++, newNum: null });
    } else if (line.startsWith("\\")) {
      // "\ No newline at end of file"
      continue;
    } else {
      // Context line (may or may not have leading space)
      const content = line.startsWith(" ") ? line.slice(1) : line;
      if (line === "" && i === lines.length - 1) continue; // skip trailing empty
      currentHunk.lines.push({ type: "context", content, oldNum: oldLine++, newNum: newLine++ });
    }
  }

  // Edge case: raw hunk with no diff header at all
  if (files.length === 0 && raw.trim()) {
    const fallback: ParsedFile = { path: singleFilePath ?? "", hunks: [], isNew: false, isDeleted: false };
    const hunk: ParsedHunk = { header: "", lines: [] };
    for (const line of lines) {
      if (line.startsWith("@@")) {
        const m = line.match(/^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/);
        if (m) { oldLine = parseInt(m[1], 10); newLine = parseInt(m[2], 10); }
        if (hunk.lines.length === 0) { hunk.header = line; continue; }
      }
      if (line.startsWith("+")) {
        hunk.lines.push({ type: "add", content: line.slice(1), oldNum: null, newNum: newLine++ });
      } else if (line.startsWith("-")) {
        hunk.lines.push({ type: "remove", content: line.slice(1), oldNum: oldLine++, newNum: null });
      } else {
        const content = line.startsWith(" ") ? line.slice(1) : line;
        hunk.lines.push({ type: "context", content, oldNum: oldLine++, newNum: newLine++ });
      }
    }
    if (hunk.lines.length > 0) {
      fallback.hunks.push(hunk);
      files.push(fallback);
    }
  }

  return files;
}

/* ── Styles ─────────────────────────────────────────────── */

const colors = {
  add: { bg: "#e6ffec", gutter: "#ccffd8", text: "#1a7f37", symbol: "#1a7f37" },
  remove: { bg: "#ffebe9", gutter: "#ffd7d5", text: "#cf222e", symbol: "#cf222e" },
  context: { bg: "#ffffff", gutter: "#f6f8fa", text: "#1f2328", symbol: "#636c76" },
  header: { bg: "#ddf4ff", gutter: "#ddf4ff", text: "#0969da", symbol: "#0969da" },
  border: "#d1d9e0",
  fileBg: "#f6f8fa",
  fileActiveBg: "#ffffff",
  fileHover: "#eef1f5",
  lineNumText: "#636c76",
  hunkSep: "#eef1f5",
};

const monoFont = "'Fira Code', 'Cascadia Code', 'JetBrains Mono', 'SF Mono', Consolas, monospace";

/* ── File list sidebar ──────────────────────────────────── */

function FileIcon({ isNew, isDeleted }: { isNew: boolean; isDeleted: boolean }) {
  const color = isNew ? colors.add.symbol : isDeleted ? colors.remove.symbol : "#636c76";
  const label = isNew ? "A" : isDeleted ? "D" : "M";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 18,
        height: 18,
        borderRadius: 3,
        fontSize: 10,
        fontWeight: 700,
        color: "#fff",
        background: color,
        flexShrink: 0,
      }}
    >
      {label}
    </span>
  );
}

function fileName(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function dirName(path: string): string {
  const parts = path.split("/");
  if (parts.length <= 1) return "";
  return parts.slice(0, -1).join("/") + "/";
}

function FileList({
  files,
  selectedIndex,
  onSelect,
}: {
  files: ParsedFile[];
  selectedIndex: number;
  onSelect: (i: number) => void;
}) {
  return (
    <div
      style={{
        width: 260,
        minWidth: 200,
        borderRight: `1px solid ${colors.border}`,
        background: colors.fileBg,
        overflowY: "auto",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          padding: "10px 14px",
          fontSize: 12,
          fontWeight: 700,
          color: "#636c76",
          textTransform: "uppercase",
          letterSpacing: "0.04em",
          borderBottom: `1px solid ${colors.border}`,
        }}
      >
        Files ({files.length})
      </div>
      {files.map((f, i) => (
        <div
          key={i}
          onClick={() => onSelect(i)}
          onMouseEnter={(e) => {
            if (i !== selectedIndex) e.currentTarget.style.background = colors.fileHover;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = i === selectedIndex ? colors.fileActiveBg : "transparent";
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 14px",
            cursor: "pointer",
            background: i === selectedIndex ? colors.fileActiveBg : "transparent",
            borderLeft: i === selectedIndex ? "3px solid #0969da" : "3px solid transparent",
            borderBottom: `1px solid ${colors.border}20`,
            transition: "background 0.1s",
          }}
        >
          <FileIcon isNew={f.isNew} isDeleted={f.isDeleted} />
          <div style={{ overflow: "hidden", minWidth: 0 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: i === selectedIndex ? 600 : 400,
                color: "#1f2328",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {fileName(f.path)}
            </div>
            {dirName(f.path) && (
              <div
                style={{
                  fontSize: 11,
                  color: "#636c76",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {dirName(f.path)}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Diff content pane ──────────────────────────────────── */

function DiffLine({ line }: { line: ParsedLine }) {
  const c = colors[line.type];
  const symbol = line.type === "add" ? "+" : line.type === "remove" ? "−" : " ";

  return (
    <div
      style={{
        display: "flex",
        minHeight: 22,
        lineHeight: "22px",
        fontSize: 13,
        fontFamily: monoFont,
      }}
    >
      {/* Old line number */}
      <span
        style={{
          width: 50,
          minWidth: 50,
          textAlign: "right",
          padding: "0 8px 0 0",
          color: colors.lineNumText,
          background: c.gutter,
          userSelect: "none",
          fontSize: 12,
          borderRight: `1px solid ${colors.border}30`,
        }}
      >
        {line.oldNum ?? ""}
      </span>
      {/* New line number */}
      <span
        style={{
          width: 50,
          minWidth: 50,
          textAlign: "right",
          padding: "0 8px 0 0",
          color: colors.lineNumText,
          background: c.gutter,
          userSelect: "none",
          fontSize: 12,
          borderRight: `1px solid ${colors.border}30`,
        }}
      >
        {line.newNum ?? ""}
      </span>
      {/* Symbol gutter */}
      <span
        style={{
          width: 24,
          minWidth: 24,
          textAlign: "center",
          color: c.symbol,
          background: c.gutter,
          fontWeight: 700,
          userSelect: "none",
        }}
      >
        {symbol}
      </span>
      {/* Content */}
      <span
        style={{
          flex: 1,
          padding: "0 12px",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
          background: c.bg,
          color: c.text,
        }}
      >
        {line.content || "\u00a0"}
      </span>
    </div>
  );
}

function HunkHeader({ text }: { text: string }) {
  return (
    <div
      style={{
        display: "flex",
        minHeight: 28,
        lineHeight: "28px",
        fontSize: 12,
        fontFamily: monoFont,
        background: colors.header.bg,
        color: colors.header.text,
        fontStyle: "italic",
        borderTop: `1px solid ${colors.border}40`,
        borderBottom: `1px solid ${colors.border}40`,
      }}
    >
      <span style={{ width: 50, minWidth: 50, background: colors.header.gutter }} />
      <span style={{ width: 50, minWidth: 50, background: colors.header.gutter }} />
      <span style={{ width: 24, minWidth: 24, background: colors.header.gutter }} />
      <span style={{ flex: 1, padding: "0 12px", fontWeight: 500 }}>
        {text}
      </span>
    </div>
  );
}

function FileHeader({ file }: { file: ParsedFile }) {
  const label = file.isNew ? "NEW" : file.isDeleted ? "DELETED" : "MODIFIED";
  const labelColor = file.isNew ? colors.add.symbol : file.isDeleted ? colors.remove.symbol : "#636c76";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 16px",
        background: colors.fileBg,
        borderBottom: `1px solid ${colors.border}`,
        fontSize: 13,
        fontFamily: monoFont,
        fontWeight: 600,
        color: "#1f2328",
      }}
    >
      <FileIcon isNew={file.isNew} isDeleted={file.isDeleted} />
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {file.path || "unknown"}
      </span>
      <span
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: labelColor,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {label}
      </span>
    </div>
  );
}

function DiffContent({ file }: { file: ParsedFile }) {
  return (
    <div style={{ flex: 1, overflowX: "auto", overflowY: "auto" }}>
      <FileHeader file={file} />
      {file.hunks.map((hunk, hi) => (
        <div key={hi}>
          {hunk.header && <HunkHeader text={hunk.header} />}
          {hunk.lines.map((line, li) => (
            <DiffLine key={`${hi}-${li}`} line={line} />
          ))}
        </div>
      ))}
      {file.hunks.length === 0 && (
        <div style={{ padding: 20, color: "#636c76", fontSize: 13, textAlign: "center" }}>
          No changes
        </div>
      )}
    </div>
  );
}

/* ── Main component ─────────────────────────────────────── */

export function DiffView({ diffHunk, filePath }: DiffViewProps) {
  const files = useMemo(() => parseDiff(diffHunk, filePath), [diffHunk, filePath]);
  const [selectedFile, setSelectedFile] = useState(0);
  const multiFile = files.length > 1;
  const activeFile = files[selectedFile] ?? files[0];

  if (!activeFile) {
    return (
      <div
        style={{
          border: `1px solid ${colors.border}`,
          borderRadius: 8,
          padding: 20,
          color: "#636c76",
          fontSize: 13,
          textAlign: "center",
          marginBottom: 16,
        }}
      >
        No diff content
      </div>
    );
  }

  return (
    <div
      style={{
        borderRadius: 8,
        overflow: "hidden",
        border: `1px solid ${colors.border}`,
        marginBottom: 16,
        display: "flex",
        maxHeight: multiFile ? 600 : undefined,
        background: "#fff",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {multiFile && (
        <FileList files={files} selectedIndex={selectedFile} onSelect={setSelectedFile} />
      )}
      <DiffContent file={activeFile} />
    </div>
  );
}

import type { ProvenanceItem } from "../api/client";
import { DiffView } from "./DiffView";

interface ProvenanceCardProps {
  item: ProvenanceItem;
}

const cardStyle: React.CSSProperties = {
  border: "1px solid #e2e8f0",
  borderRadius: "10px",
  padding: "20px",
  marginBottom: "16px",
  background: "#fff",
};

const prLinkStyle: React.CSSProperties = {
  fontSize: "16px",
  fontWeight: 600,
  color: "#4361ee",
};

const metaStyle: React.CSSProperties = {
  fontSize: "13px",
  color: "#64748b",
  marginTop: "4px",
};

const commentStyle: React.CSSProperties = {
  background: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "8px",
  padding: "12px 16px",
  margin: "12px 0",
  fontSize: "14px",
  whiteSpace: "pre-wrap",
  lineHeight: 1.6,
};

const notesStyle: React.CSSProperties = {
  fontSize: "13px",
  color: "#64748b",
  fontStyle: "italic",
  marginTop: "8px",
};

export function ProvenanceCard({ item }: ProvenanceCardProps) {
  return (
    <div style={cardStyle}>
      <a
        href={item.pr_url}
        target="_blank"
        rel="noopener noreferrer"
        style={prLinkStyle}
      >
        {item.repo_full_name} #{item.pr_number}
      </a>
      <div style={metaStyle}>
        {item.pr_title}
        {item.comment_author && <> &middot; reviewed by <strong>{item.comment_author}</strong></>}
      </div>

      {item.comment_body && (
        <div style={commentStyle}>{item.comment_body}</div>
      )}

      {item.diff_hunk && (
        <DiffView diffHunk={item.diff_hunk} filePath={item.file_path} />
      )}

      {item.extraction_notes && (
        <div style={notesStyle}>Notes: {item.extraction_notes}</div>
      )}
    </div>
  );
}

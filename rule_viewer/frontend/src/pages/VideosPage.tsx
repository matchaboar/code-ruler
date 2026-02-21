import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchVideos,
  fetchVideoStatus,
  type VideoListItem,
} from "../api/client";

const statusColors: Record<string, string> = {
  Success: "#22c55e",
  Fail: "#ef4444",
  Processing: "#f59e0b",
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
      }}
    >
      {label}
    </span>
  );
}

function Spinner({ size = 16 }: { size?: number }) {
  return (
    <>
      <span
        style={{
          display: "inline-block",
          width: size,
          height: size,
          border: "2px solid #e2e8f0",
          borderTop: "2px solid currentColor",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
          verticalAlign: "middle",
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

const headerRowStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "2fr 100px 160px 80px",
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
  gridTemplateColumns: "2fr 100px 160px 80px",
  alignItems: "center",
  gap: "12px",
  padding: "14px 20px",
  borderBottom: "1px solid #e2e8f0",
  transition: "background 0.15s",
};

export function VideosPage() {
  const [videos, setVideos] = useState<VideoListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [downloadUrls, setDownloadUrls] = useState<Record<string, string>>({});
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadVideos = () => {
    fetchVideos()
      .then(setVideos)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    setLoading(true);
    loadVideos();
  }, []);

  // Auto-refresh while any video is still processing
  useEffect(() => {
    const hasProcessing = videos.some((v) => v.status === "Processing");
    if (hasProcessing) {
      intervalRef.current = setInterval(loadVideos, 5000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [videos]);

  const handleRowClick = (v: VideoListItem) => {
    if (expandedId === v.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(v.id);
    // If completed but we don't have a fresh download_url, fetch it
    if (v.status === "Success" && !downloadUrls[v.task_id] && !v.download_url) {
      fetchVideoStatus(v.task_id)
        .then((status) => {
          if (status.download_url) {
            setDownloadUrls((prev) => ({ ...prev, [v.task_id]: status.download_url! }));
          }
        })
        .catch(() => {});
    }
  };

  if (loading) {
    return <div style={{ textAlign: "center", padding: "48px", color: "#94a3b8" }}>Loading...</div>;
  }

  return (
    <div>
      <h1 style={{ fontSize: "24px", fontWeight: 700, marginBottom: "24px" }}>Videos</h1>
      {videos.length === 0 ? (
        <div style={{ color: "#94a3b8", textAlign: "center", padding: "48px" }}>
          No videos yet. Go to a rule detail page and click "Generate Video" to create one.
        </div>
      ) : (
        <div style={{ border: "1px solid #e2e8f0", borderRadius: "12px", overflow: "hidden" }}>
          <div style={headerRowStyle}>
            <div>Rule</div>
            <div>Status</div>
            <div>Created</div>
            <div></div>
          </div>
          {videos.map((v) => {
            const videoUrl = v.download_url || downloadUrls[v.task_id];
            return (
              <div key={v.id}>
                <div
                  style={{ ...rowStyle, cursor: v.status === "Success" ? "pointer" : "default" }}
                  onClick={() => handleRowClick(v)}
                  onMouseEnter={(ev) => { (ev.currentTarget as HTMLElement).style.background = "#f8fafc"; }}
                  onMouseLeave={(ev) => { (ev.currentTarget as HTMLElement).style.background = "transparent"; }}
                >
                  <div>
                    <Link
                      to={`/rules/${v.rule_slug}`}
                      style={{ fontWeight: 600, fontSize: "14px", color: "#1e293b", textDecoration: "none" }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {v.rule_title}
                    </Link>
                    <div style={{ fontFamily: "monospace", fontSize: "12px", color: "#64748b" }}>
                      {v.rule_slug}
                    </div>
                  </div>
                  <div>
                    <Badge label={v.status} color={statusColors[v.status] ?? "#94a3b8"} />
                    {v.status === "Processing" && (
                      <span style={{ marginLeft: "6px" }}><Spinner size={12} /></span>
                    )}
                  </div>
                  <div style={{ fontSize: "13px", color: "#64748b" }}>
                    {new Date(v.created_at).toLocaleString()}
                  </div>
                  <div>
                    {v.status === "Success" && (
                      <span style={{ fontSize: "12px", color: "#3b82f6", cursor: "pointer" }}>
                        {expandedId === v.id ? "Hide" : "Preview"}
                      </span>
                    )}
                  </div>
                </div>
                {expandedId === v.id && v.status === "Success" && videoUrl && (
                  <div style={{ padding: "16px 20px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                    <video
                      controls
                      style={{
                        width: "100%",
                        maxWidth: "720px",
                        borderRadius: "8px",
                        background: "#000",
                      }}
                      src={videoUrl}
                    />
                  </div>
                )}
                {expandedId === v.id && v.status === "Fail" && (
                  <div style={{ padding: "16px 20px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                    <div style={{ color: "#ef4444", fontSize: "13px" }}>
                      Error: {v.error || "Unknown error"}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

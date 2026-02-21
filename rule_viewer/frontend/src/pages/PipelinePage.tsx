import { useEffect, useState, useRef, useCallback } from "react";
import {
  startExtractPRs,
  startExtractRules,
  startQuickRun,
  fetchJobStatus,
  fetchJobs,
  fetchRepoStats,
  type JobStatus,
  type JobEvent,
  type RepoStats,
} from "../api/client";

// ---- Shared styles ----

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

const cardStyle: React.CSSProperties = {
  background: "#fff",
  borderRadius: "10px",
  border: "1px solid #e2e8f0",
  padding: "24px",
  marginBottom: "24px",
};

const cardTitleStyle: React.CSSProperties = {
  fontSize: "18px",
  fontWeight: 600,
  marginBottom: "16px",
};

const labelStyle: React.CSSProperties = {
  fontSize: "13px",
  fontWeight: 500,
  color: "#475569",
  marginBottom: "4px",
};

const inputStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderRadius: "6px",
  border: "1px solid #cbd5e1",
  fontSize: "14px",
  outline: "none",
};

const buttonStyle = (
  disabled: boolean,
  variant: "primary" | "secondary" | "success" = "primary"
): React.CSSProperties => {
  const colors = {
    primary: disabled ? "#94a3b8" : "#3b82f6",
    secondary: disabled ? "#94a3b8" : "#6366f1",
    success: disabled ? "#94a3b8" : "#10b981",
  };
  return {
    padding: "8px 20px",
    borderRadius: "6px",
    border: "none",
    background: colors[variant],
    color: "#fff",
    fontSize: "14px",
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
  };
};

const statusBadge = (status: string): React.CSSProperties => ({
  display: "inline-block",
  padding: "2px 10px",
  borderRadius: "9999px",
  fontSize: "12px",
  fontWeight: 600,
  background:
    status === "completed"
      ? "rgba(34,197,94,0.15)"
      : status === "failed"
        ? "rgba(239,68,68,0.15)"
        : "rgba(59,130,246,0.15)",
  color:
    status === "completed"
      ? "#16a34a"
      : status === "failed"
        ? "#dc2626"
        : "#2563eb",
});

const kindLabel = (kind: string): string => {
  switch (kind) {
    case "extract-prs":
      return "PR Extraction";
    case "extract-rules":
      return "Rule Extraction";
    case "quick-run":
      return "Quick Run";
    default:
      return kind;
  }
};

const kindBadge = (kind: string): React.CSSProperties => ({
  display: "inline-block",
  padding: "2px 8px",
  borderRadius: "4px",
  fontSize: "11px",
  fontWeight: 600,
  letterSpacing: "0.03em",
  background:
    kind === "quick-run"
      ? "rgba(16,185,129,0.12)"
      : kind === "extract-prs"
        ? "rgba(59,130,246,0.12)"
        : "rgba(99,102,241,0.12)",
  color:
    kind === "quick-run"
      ? "#059669"
      : kind === "extract-prs"
        ? "#2563eb"
        : "#4f46e5",
});

// ---- Tooltip helper ----

function Tooltip({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  const [show, setShow] = useState(false);
  return (
    <span
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          style={{
            position: "absolute",
            bottom: "100%",
            left: "50%",
            transform: "translateX(-50%)",
            marginBottom: "6px",
            padding: "6px 10px",
            borderRadius: "6px",
            background: "#1e293b",
            color: "#e2e8f0",
            fontSize: "12px",
            whiteSpace: "nowrap",
            zIndex: 100,
            pointerEvents: "none",
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}

// ---- Hook: poll a single job ----

function useJobPoller(jobId: string | null): JobStatus | null {
  const [job, setJob] = useState<JobStatus | null>(null);
  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }

    const poll = () => {
      fetchJobStatus(jobId)
        .then((j) => {
          setJob(j);
          if (j.status !== "running" && intervalRef.current !== null) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        })
        .catch(() => {});
    };

    poll();
    intervalRef.current = window.setInterval(poll, 2000);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId]);

  return job;
}

// ---- PR Event Card ----

function PREventCard({ event }: { event: JobEvent }) {
  const { pr_number, pr_title, author } = event.data;
  const isSkipped = event.type === "pr_skipped";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        padding: "10px 14px",
        borderRadius: "8px",
        border: "1px solid #e2e8f0",
        background: isSkipped ? "#f8fafc" : "#fff",
        marginBottom: "6px",
      }}
    >
      <span
        style={{
          width: "8px",
          height: "8px",
          borderRadius: "50%",
          background: isSkipped ? "#94a3b8" : "#22c55e",
          flexShrink: 0,
        }}
      />
      <span style={{ fontWeight: 600, fontSize: "13px", color: "#1e293b" }}>
        #{pr_number}
      </span>
      <span
        style={{
          fontSize: "13px",
          color: "#475569",
          flex: 1,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {pr_title}
      </span>
      <span style={{ fontSize: "12px", color: "#94a3b8" }}>{author}</span>
      <span
        style={{
          fontSize: "11px",
          fontWeight: 500,
          color: isSkipped ? "#94a3b8" : "#16a34a",
        }}
      >
        {isSkipped ? "cached" : "extracted"}
      </span>
    </div>
  );
}

// ---- DD Trace Section (collapsible) ----

function DDTraceSection({ traces }: { traces: any[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!traces || traces.length === 0) return null;

  const allOk = traces.every((t: any) => t.ok);
  const failCount = traces.filter((t: any) => !t.ok).length;

  return (
    <div style={{ marginTop: "6px", marginLeft: "18px" }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: "none",
          border: "none",
          color: "#64748b",
          fontSize: "11px",
          cursor: "pointer",
          padding: "2px 0",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        <span style={{ fontSize: "10px" }}>{expanded ? "\u25BC" : "\u25B6"}</span>
        <span
          style={{
            display: "inline-block",
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            background: allOk ? "#a855f7" : "#ef4444",
            flexShrink: 0,
          }}
        />
        DD Traces ({traces.length} call{traces.length !== 1 ? "s" : ""}
        {failCount > 0 ? `, ${failCount} failed` : ", all sent"})
      </button>
      {expanded && (
        <div
          style={{
            marginTop: "4px",
            padding: "8px 10px",
            borderRadius: "6px",
            background: "#faf5ff",
            border: "1px solid #e9d5ff",
            fontSize: "11px",
            fontFamily: "monospace",
          }}
        >
          {traces.map((t: any, i: number) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "2px 0",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  background: t.ok ? "#22c55e" : "#ef4444",
                  flexShrink: 0,
                }}
              />
              <span style={{ color: "#6b7280" }}>LLM call {i + 1}</span>
              {t.trace_id ? (
                <span style={{ color: "#7c3aed" }}>trace_id: {t.trace_id}</span>
              ) : (
                <span style={{ color: "#94a3b8" }}>no trace_id</span>
              )}
              {!t.ok && (
                <span style={{ color: "#dc2626" }}>
                  FAILED{t.error ? `: ${t.error}` : ""}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- Review Event Card ----

function ReviewEventCard({ event }: { event: JobEvent }) {
  const { index, total, pr_number, file_path, candidates, error, dd_traces } =
    event.data;
  const isError = event.type === "review_error";
  const isProcessing = event.type === "review_start";

  return (
    <div
      style={{
        padding: "12px 14px",
        borderRadius: "8px",
        border: `1px solid ${isError ? "#fecaca" : "#e2e8f0"}`,
        background: isError ? "#fef2f2" : isProcessing ? "#eff6ff" : "#fff",
        marginBottom: "6px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          marginBottom: candidates?.length || dd_traces?.length ? "8px" : 0,
        }}
      >
        {isProcessing && (
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: "#3b82f6",
              flexShrink: 0,
              animation: "pulse 1.5s infinite",
            }}
          />
        )}
        {!isProcessing && (
          <span
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: isError ? "#ef4444" : "#22c55e",
              flexShrink: 0,
            }}
          />
        )}
        <span style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 500 }}>
          {index}/{total}
        </span>
        <span style={{ fontWeight: 600, fontSize: "13px", color: "#1e293b" }}>
          PR #{pr_number}
        </span>
        <span
          style={{
            fontSize: "12px",
            color: "#64748b",
            fontFamily: "monospace",
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {file_path}
        </span>
        {isProcessing && (
          <span style={{ fontSize: "11px", color: "#3b82f6", fontWeight: 500 }}>
            processing...
          </span>
        )}
      </div>
      {isError && (
        <div style={{ fontSize: "12px", color: "#dc2626", marginTop: "4px" }}>
          Error: {error}
        </div>
      )}
      {candidates?.length > 0 && (
        <div style={{ marginLeft: "18px" }}>
          {candidates.map((c: any, i: number) => (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "12px",
                padding: "3px 0",
              }}
            >
              <span
                style={{
                  padding: "1px 6px",
                  borderRadius: "3px",
                  fontSize: "10px",
                  fontWeight: 600,
                  background:
                    c.action === "discard"
                      ? "rgba(148,163,184,0.2)"
                      : c.action === "merge"
                        ? "rgba(245,158,11,0.15)"
                        : "rgba(34,197,94,0.15)",
                  color:
                    c.action === "discard"
                      ? "#64748b"
                      : c.action === "merge"
                        ? "#d97706"
                        : "#16a34a",
                }}
              >
                {c.action}
              </span>
              <span style={{ color: "#475569", fontWeight: 500 }}>
                {c.slug}
              </span>
              <span style={{ color: "#94a3b8" }}>{c.title}</span>
            </div>
          ))}
        </div>
      )}
      <DDTraceSection traces={dd_traces} />
    </div>
  );
}

// ---- Log viewer (fallback for raw logs) ----

function LogViewer({ job }: { job: JobStatus }) {
  const logEndRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (expanded) {
      logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [job.logs.length, expanded]);

  if (job.logs.length === 0) return null;

  return (
    <div style={{ marginTop: "12px" }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: "none",
          border: "none",
          color: "#64748b",
          fontSize: "12px",
          cursor: "pointer",
          padding: "4px 0",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        <span style={{ fontSize: "10px" }}>{expanded ? "▼" : "▶"}</span>
        Raw logs ({job.logs.length} lines)
      </button>
      {expanded && (
        <div
          style={{
            background: "#0f172a",
            color: "#e2e8f0",
            borderRadius: "6px",
            padding: "12px 16px",
            fontFamily: "monospace",
            fontSize: "12px",
            lineHeight: 1.6,
            maxHeight: "200px",
            overflowY: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            marginTop: "4px",
          }}
        >
          {job.logs.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
          <div ref={logEndRef} />
        </div>
      )}
    </div>
  );
}

// ---- Pipeline Detail View ----

function PipelineDetail({
  jobId,
  onBack,
}: {
  jobId: string;
  onBack: () => void;
}) {
  const job = useJobPoller(jobId);

  if (!job) {
    return <p style={{ color: "#64748b" }}>Loading job...</p>;
  }

  const prEvents = job.events.filter(
    (e) => e.type === "pr_extracted" || e.type === "pr_skipped"
  );
  const reviewEvents = job.events.filter(
    (e) =>
      e.type === "review_start" ||
      e.type === "review_done" ||
      e.type === "review_error"
  );

  // Merge review_start and review_done for the same index
  const reviewMap = new Map<number, JobEvent>();
  for (const e of reviewEvents) {
    const idx = e.data.index;
    const existing = reviewMap.get(idx);
    // Prefer done/error over start
    if (
      !existing ||
      e.type === "review_done" ||
      e.type === "review_error"
    ) {
      reviewMap.set(idx, e);
    }
  }
  const mergedReviews = Array.from(reviewMap.values()).sort(
    (a, b) => (a.data.index ?? 0) - (b.data.index ?? 0)
  );

  return (
    <div>
      <button
        onClick={onBack}
        style={{
          background: "none",
          border: "none",
          color: "#3b82f6",
          fontSize: "14px",
          cursor: "pointer",
          padding: "0",
          marginBottom: "16px",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        ← Back to pipelines
      </button>

      <div style={cardStyle}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
            marginBottom: "16px",
          }}
        >
          <span style={kindBadge(job.kind)}>{kindLabel(job.kind)}</span>
          <span style={statusBadge(job.status)}>{job.status}</span>
          {job.status === "running" && (
            <span style={{ fontSize: "12px", color: "#64748b" }}>
              Polling every 2s...
            </span>
          )}
          <span
            style={{
              marginLeft: "auto",
              fontSize: "12px",
              color: "#94a3b8",
              fontFamily: "monospace",
            }}
          >
            {job.job_id}
          </span>
        </div>

        {job.repo_url && (
          <div style={{ fontSize: "13px", color: "#475569", marginBottom: "12px" }}>
            Repository: <strong>{job.repo_url}</strong>
          </div>
        )}

        <div
          style={{
            display: "flex",
            gap: "8px",
            fontSize: "12px",
            color: "#64748b",
            marginBottom: "16px",
          }}
        >
          <span>
            Started: {new Date(job.started_at).toLocaleString()}
          </span>
          {job.finished_at && (
            <span>
              · Finished: {new Date(job.finished_at).toLocaleString()}
            </span>
          )}
        </div>

        {job.error && (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: "8px",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#dc2626",
              fontSize: "13px",
              fontWeight: 500,
              marginBottom: "16px",
            }}
          >
            Error: {job.error}
          </div>
        )}

        {/* PR Events Section */}
        {prEvents.length > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <div
              style={{
                fontSize: "14px",
                fontWeight: 600,
                color: "#1e293b",
                marginBottom: "10px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              Pull Requests
              <span
                style={{
                  fontSize: "12px",
                  color: "#94a3b8",
                  fontWeight: 400,
                }}
              >
                {prEvents.filter((e) => e.type === "pr_extracted").length}{" "}
                extracted,{" "}
                {prEvents.filter((e) => e.type === "pr_skipped").length} cached
              </span>
            </div>
            {prEvents.map((e, i) => (
              <PREventCard key={i} event={e} />
            ))}
          </div>
        )}

        {/* Review Events Section */}
        {mergedReviews.length > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <div
              style={{
                fontSize: "14px",
                fontWeight: 600,
                color: "#1e293b",
                marginBottom: "10px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              Rule Reviews
              <span
                style={{
                  fontSize: "12px",
                  color: "#94a3b8",
                  fontWeight: 400,
                }}
              >
                {mergedReviews.filter((e) => e.type === "review_done").length} /{" "}
                {mergedReviews.length} completed
              </span>
            </div>
            {mergedReviews.map((e, i) => (
              <ReviewEventCard key={i} event={e} />
            ))}
          </div>
        )}

        <LogViewer job={job} />
      </div>
    </div>
  );
}

// ---- New Pipeline Form ----

function NewPipelineForm({
  onCreated,
  onCancel,
}: {
  onCreated: (jobId: string) => void;
  onCancel: () => void;
}) {
  const [mode, setMode] = useState<"quick" | "prs" | "rules">("quick");
  const [repoUrl, setRepoUrl] = useState("");
  const [limit, setLimit] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    setStarting(true);
    try {
      let resp;
      if (mode === "quick") {
        resp = await startQuickRun(repoUrl.trim());
      } else if (mode === "prs") {
        resp = await startExtractPRs(
          repoUrl.trim(),
          limit ? parseInt(limit, 10) : undefined
        );
      } else {
        resp = await startExtractRules(
          limit ? parseInt(limit, 10) : undefined,
          dryRun
        );
      }
      onCreated(resp.job_id);
    } catch (e) {
      alert(`Failed to start: ${e}`);
    } finally {
      setStarting(false);
    }
  };

  const canStart =
    mode === "rules" ? !starting : !starting && repoUrl.trim().length > 0;

  return (
    <div style={cardStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "20px",
        }}
      >
        <div style={cardTitleStyle}>New Pipeline</div>
        <button
          onClick={onCancel}
          style={{
            background: "none",
            border: "none",
            color: "#94a3b8",
            fontSize: "18px",
            cursor: "pointer",
            padding: "4px",
          }}
        >
          ✕
        </button>
      </div>

      {/* Mode selector */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "20px",
        }}
      >
        {(
          [
            ["quick", "Quick Run"],
            ["prs", "Extract PRs"],
            ["rules", "Extract Rules"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setMode(key)}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: `1px solid ${mode === key ? "#3b82f6" : "#e2e8f0"}`,
              background: mode === key ? "rgba(59,130,246,0.08)" : "#fff",
              color: mode === key ? "#2563eb" : "#64748b",
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Quick Run description */}
      {mode === "quick" && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: "8px",
            padding: "10px 14px",
            borderRadius: "8px",
            background: "rgba(16,185,129,0.06)",
            border: "1px solid rgba(16,185,129,0.15)",
            marginBottom: "16px",
            fontSize: "13px",
            color: "#475569",
          }}
        >
          <Tooltip text="Extracts up to 10 PRs from the repo, then runs rule extraction on all unprocessed review comments. Skips already-cached PRs.">
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "16px",
                height: "16px",
                borderRadius: "50%",
                background: "#10b981",
                color: "#fff",
                fontSize: "11px",
                fontWeight: 700,
                flexShrink: 0,
                cursor: "help",
              }}
            >
              ?
            </span>
          </Tooltip>
          <span>
            Pulls up to 10 merged PRs and extracts coding rules from their
            review comments. Already-cached PRs are skipped.
          </span>
        </div>
      )}

      {/* Repo URL (for quick and prs modes) */}
      {(mode === "quick" || mode === "prs") && (
        <div style={{ marginBottom: "16px" }}>
          <div style={labelStyle}>Repository URL</div>
          <input
            style={{ ...inputStyle, width: "100%" }}
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
          />
        </div>
      )}

      {/* Limit (for prs and rules modes) */}
      {mode !== "quick" && (
        <div
          style={{
            display: "flex",
            gap: "12px",
            alignItems: "flex-end",
            marginBottom: "16px",
            flexWrap: "wrap",
          }}
        >
          <div style={{ width: "100px" }}>
            <div style={labelStyle}>Limit</div>
            <input
              style={{ ...inputStyle, width: "100%" }}
              type="number"
              placeholder="All"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
          </div>
          {mode === "rules" && (
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "14px",
                color: "#475569",
                cursor: "pointer",
                paddingBottom: "8px",
              }}
            >
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
              />
              Dry run
            </label>
          )}
        </div>
      )}

      <div style={{ display: "flex", gap: "10px" }}>
        <button
          style={buttonStyle(
            !canStart,
            mode === "quick" ? "success" : "primary"
          )}
          onClick={handleStart}
          disabled={!canStart}
        >
          {starting
            ? "Starting..."
            : mode === "quick"
              ? "Quick Run"
              : mode === "prs"
                ? "Start PR Extraction"
                : "Start Rule Extraction"}
        </button>
      </div>
    </div>
  );
}

// ---- Repo Stats Section ----

function RepoStatsSection({
  onJobCreated,
}: {
  onJobCreated?: (jobId: string) => void;
}) {
  const [stats, setStats] = useState<RepoStats[]>([]);
  const [resuming, setResuming] = useState<string | null>(null);

  useEffect(() => {
    fetchRepoStats().then(setStats).catch(() => {});
    const id = window.setInterval(() => {
      fetchRepoStats().then(setStats).catch(() => {});
    }, 10000);
    return () => clearInterval(id);
  }, []);

  const handleResume = async (repoFullName: string, limit?: number) => {
    setResuming(repoFullName);
    try {
      const resp = await startExtractRules(limit, false, repoFullName);
      onJobCreated?.(resp.job_id);
    } catch (e) {
      alert(`Failed to start: ${e}`);
    } finally {
      setResuming(null);
    }
  };

  if (stats.length === 0) return null;

  return (
    <div style={cardStyle}>
      <div style={cardTitleStyle}>Repositories</div>
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {stats.map((r) => (
          <div
            key={r.full_name}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
              padding: "10px 14px",
              borderRadius: "8px",
              border: "1px solid #e2e8f0",
              fontSize: "13px",
            }}
          >
            <span style={{ fontWeight: 600, color: "#1e293b", minWidth: "180px" }}>
              {r.full_name}
            </span>
            <span style={{ color: "#64748b" }}>
              {r.total_prs} PR{r.total_prs !== 1 ? "s" : ""}
            </span>
            <span style={{ color: "#16a34a" }}>
              {r.processed_comments} processed
            </span>
            <span style={{ color: "#d97706" }}>
              {r.unprocessed_comments} unprocessed
            </span>
            {r.unprocessed_comments > 0 && r.processed_comments + r.unprocessed_comments > 0 && (
              <div
                style={{
                  flex: 1,
                  height: "6px",
                  borderRadius: "3px",
                  background: "#f1f5f9",
                  overflow: "hidden",
                  minWidth: "80px",
                }}
              >
                <div
                  style={{
                    width: `${(r.processed_comments / (r.processed_comments + r.unprocessed_comments)) * 100}%`,
                    height: "100%",
                    background: "#22c55e",
                    borderRadius: "3px",
                    transition: "width 0.3s",
                  }}
                />
              </div>
            )}
            {r.unprocessed_comments > 0 && (
              <div style={{ display: "flex", gap: "6px", flexShrink: 0 }}>
                <button
                  onClick={() => handleResume(r.full_name)}
                  disabled={resuming !== null}
                  style={{
                    padding: "4px 12px",
                    borderRadius: "6px",
                    border: "none",
                    background: resuming === r.full_name ? "#94a3b8" : "#6366f1",
                    color: "#fff",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: resuming !== null ? "not-allowed" : "pointer",
                    whiteSpace: "nowrap",
                  }}
                >
                  {resuming === r.full_name ? "Starting..." : "Resume All"}
                </button>
                <button
                  onClick={() => handleResume(r.full_name, 10)}
                  disabled={resuming !== null}
                  title="Quick run: only process 10 PRs"
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    border: "1px solid #6366f1",
                    background: resuming === r.full_name ? "#94a3b8" : "#eef2ff",
                    color: resuming === r.full_name ? "#fff" : "#6366f1",
                    fontSize: "12px",
                    fontWeight: 600,
                    cursor: resuming !== null ? "not-allowed" : "pointer",
                    whiteSpace: "nowrap",
                  }}
                >
                  Quick [10]
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Pipeline List (Job Cards) ----

function PipelineList({
  jobs,
  onSelect,
}: {
  jobs: JobStatus[];
  onSelect: (jobId: string) => void;
}) {
  if (jobs.length === 0) {
    return (
      <div
        style={{
          textAlign: "center",
          padding: "40px 0",
          color: "#94a3b8",
          fontSize: "14px",
        }}
      >
        No pipelines yet. Create one to get started.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {jobs.map((j) => {
        const prCount = j.events.filter(
          (e) => e.type === "pr_extracted" || e.type === "pr_skipped"
        ).length;
        const reviewCount = j.events.filter(
          (e) => e.type === "review_done" || e.type === "review_error"
        ).length;
        const reviewTotal =
          j.events.find((e) => e.type === "review_start" || e.type === "review_done")
            ?.data.total ?? 0;

        return (
          <div
            key={j.job_id}
            onClick={() => onSelect(j.job_id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "14px",
              padding: "14px 18px",
              borderRadius: "10px",
              border: `1px solid ${j.status === "running" ? "#bfdbfe" : "#e2e8f0"}`,
              background: j.status === "running" ? "#eff6ff" : "#fff",
              cursor: "pointer",
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.borderColor = "#93c5fd";
              (e.currentTarget as HTMLElement).style.boxShadow =
                "0 1px 4px rgba(59,130,246,0.1)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.borderColor =
                j.status === "running" ? "#bfdbfe" : "#e2e8f0";
              (e.currentTarget as HTMLElement).style.boxShadow = "none";
            }}
          >
            <span style={kindBadge(j.kind)}>{kindLabel(j.kind)}</span>
            <span style={statusBadge(j.status)}>{j.status}</span>

            {j.repo_url && (
              <span
                style={{
                  fontSize: "13px",
                  color: "#475569",
                  fontWeight: 500,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  maxWidth: "250px",
                }}
              >
                {j.repo_url.replace("https://github.com/", "")}
              </span>
            )}

            <span style={{ flex: 1 }} />

            {prCount > 0 && (
              <span style={{ fontSize: "12px", color: "#64748b" }}>
                {prCount} PR{prCount !== 1 ? "s" : ""}
              </span>
            )}
            {reviewTotal > 0 && (
              <span style={{ fontSize: "12px", color: "#64748b" }}>
                {reviewCount}/{reviewTotal} reviews
              </span>
            )}

            <span
              style={{
                fontSize: "12px",
                color: "#94a3b8",
              }}
            >
              {new Date(j.started_at).toLocaleString()}
            </span>

            <span style={{ color: "#94a3b8", fontSize: "14px" }}>→</span>
          </div>
        );
      })}
    </div>
  );
}

// ---- Main Page ----

export function PipelinePage() {
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<
    { type: "list" } | { type: "detail"; jobId: string } | { type: "new" }
  >({ type: "list" });

  const load = useCallback(() => {
    fetchJobs()
      .then(setJobs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const id = window.setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  if (view.type === "detail") {
    return (
      <div>
        <h1 style={headingStyle}>Pipeline</h1>
        <p style={subStyle}>
          Run extraction steps to pull PR data and derive coding rules.
        </p>
        <PipelineDetail
          jobId={view.jobId}
          onBack={() => setView({ type: "list" })}
        />
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "4px",
        }}
      >
        <h1 style={{ ...headingStyle, marginBottom: 0 }}>Pipeline</h1>
        {view.type === "list" && (
          <button
            style={buttonStyle(false, "primary")}
            onClick={() => setView({ type: "new" })}
          >
            + New Pipeline
          </button>
        )}
      </div>
      <p style={subStyle}>
        Run extraction steps to pull PR data and derive coding rules.
      </p>

      {view.type === "new" && (
        <NewPipelineForm
          onCreated={(jobId) => {
            load();
            setView({ type: "detail", jobId });
          }}
          onCancel={() => setView({ type: "list" })}
        />
      )}

      <RepoStatsSection
        onJobCreated={(jobId) => {
          load();
          setView({ type: "detail", jobId });
        }}
      />

      <div style={cardStyle}>
        <div style={cardTitleStyle}>
          Pipelines
          {jobs.filter((j) => j.status === "running").length > 0 && (
            <span
              style={{
                marginLeft: "8px",
                fontSize: "12px",
                color: "#2563eb",
                fontWeight: 400,
              }}
            >
              {jobs.filter((j) => j.status === "running").length} running
            </span>
          )}
        </div>
        {loading ? (
          <p style={{ color: "#64748b" }}>Loading...</p>
        ) : (
          <PipelineList
            jobs={jobs}
            onSelect={(jobId) => setView({ type: "detail", jobId })}
          />
        )}
      </div>
    </div>
  );
}

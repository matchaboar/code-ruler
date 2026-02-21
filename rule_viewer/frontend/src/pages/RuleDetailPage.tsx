import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchRule,
  fetchProvenance,
  fetchEnforcer,
  fetchJobStatus,
  generateEnforcer,
  generateVideo,
  fetchVideoStatus,
  generateTestSprite,
  fetchRuleTestSpriteResults,
  type RuleDetail,
  type ProvenanceItem,
  type EnforcerDetail,
  type VideoResponse,
  type TestSpriteListItem,
} from "../api/client";
import { CodeBlock } from "../components/CodeBlock";
import { ProvenanceCard } from "../components/ProvenanceCard";
import { TabBar } from "../components/TabBar";

const backStyle: React.CSSProperties = {
  fontSize: "14px",
  color: "#4361ee",
  marginBottom: "16px",
  display: "inline-block",
};

const headerStyle: React.CSSProperties = {
  marginBottom: "32px",
};

const titleStyle: React.CSSProperties = {
  fontSize: "28px",
  fontWeight: 700,
  marginBottom: "4px",
};

const slugStyle: React.CSSProperties = {
  fontFamily: "monospace",
  fontSize: "14px",
  color: "#64748b",
  marginBottom: "12px",
};

const badgeRowStyle: React.CSSProperties = {
  display: "flex",
  gap: "8px",
  flexWrap: "wrap",
  alignItems: "center",
  marginBottom: "8px",
};

const sectionStyle: React.CSSProperties = {
  marginBottom: "32px",
};

const sectionTitle: React.CSSProperties = {
  fontSize: "18px",
  fontWeight: 600,
  marginBottom: "12px",
  color: "#1e293b",
};

const textBlock: React.CSSProperties = {
  fontSize: "15px",
  lineHeight: 1.7,
  color: "#334155",
  whiteSpace: "pre-wrap",
};

const categoryColors: Record<string, string> = {
  correctness: "#3b82f6",
  security: "#ef4444",
  performance: "#f59e0b",
  style: "#8b5cf6",
  maintainability: "#10b981",
};

const severityColors: Record<string, string> = {
  error: "#ef4444",
  warning: "#f59e0b",
  info: "#3b82f6",
  hint: "#94a3b8",
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 12px",
        borderRadius: "12px",
        fontSize: "13px",
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

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 12px",
        borderRadius: "12px",
        fontSize: "13px",
        fontWeight: 600,
        background: active ? "#dcfce7" : "#f1f5f9",
        color: active ? "#166534" : "#64748b",
      }}
    >
      {active ? "Active" : "Inactive"}
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

const actionButtonStyle = (
  color: string,
  disabled: boolean,
): React.CSSProperties => ({
  display: "inline-flex",
  alignItems: "center",
  gap: "6px",
  padding: "8px 18px",
  background: disabled ? "#94a3b8" : color,
  color: "#fff",
  border: "none",
  borderRadius: "8px",
  cursor: disabled ? "not-allowed" : "pointer",
  fontSize: "13px",
  fontWeight: 600,
  opacity: disabled ? 0.7 : 1,
  transition: "opacity 0.15s",
});

function CollapsibleCode({
  title,
  code,
  language = "python",
}: {
  title: string;
  code: string;
  language?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ marginBottom: "12px" }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          background: "none",
          border: "1px solid #e2e8f0",
          borderRadius: "8px",
          padding: "10px 16px",
          cursor: "pointer",
          fontSize: "14px",
          fontWeight: 600,
          color: "#334155",
          width: "100%",
          textAlign: "left",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>{title}</span>
        <span style={{ color: "#94a3b8" }}>{open ? "Collapse" : "Expand"}</span>
      </button>
      {open && (
        <div style={{ marginTop: "8px" }}>
          <CodeBlock code={code} language={language} />
        </div>
      )}
    </div>
  );
}

export function RuleDetailPage({ repoId }: { repoId: number | null }) {
  const { slug } = useParams<{ slug: string }>();
  const [rule, setRule] = useState<RuleDetail | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enforcer, setEnforcer] = useState<EnforcerDetail | null>(null);

  const [enforcerTab, setEnforcerTab] = useState("source");

  // Enforcer generation state
  const [generating, setGenerating] = useState(false);

  // Video generation state
  const [videoGenerating, setVideoGenerating] = useState(false);
  const [videoResult, setVideoResult] = useState<VideoResponse | null>(null);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [videoElapsed, setVideoElapsed] = useState(0);
  const videoStartRef = useRef<number | null>(null);

  // TestSprite generation state
  const [tsGenerating, setTsGenerating] = useState(false);
  const [tsResults, setTsResults] = useState<TestSpriteListItem[]>([]);
  const [tsError, setTsError] = useState<string | null>(null);

  useEffect(() => {
    if (!videoGenerating) return;
    const tick = setInterval(() => {
      if (videoStartRef.current) {
        setVideoElapsed(Math.floor((Date.now() - videoStartRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(tick);
  }, [videoGenerating]);

  useEffect(() => {
    if (!slug) return;

    setLoading(true);
    setError(null);

    Promise.all([fetchRule(slug, repoId ?? undefined), fetchProvenance(slug)])
      .then(([ruleData, provData]) => {
        setRule(ruleData);
        setProvenance(provData);
        fetchEnforcer(slug).then(setEnforcer).catch(() => setEnforcer(null));
        fetchRuleTestSpriteResults(slug).then(setTsResults).catch(() => setTsResults([]));
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load rule");
      })
      .finally(() => setLoading(false));
  }, [slug, repoId]);

  const handleGenerateEnforcer = () => {
    if (!slug) return;
    setGenerating(true);
    generateEnforcer(slug)
      .then((res) => {
        const pollId = setInterval(() => {
          fetchJobStatus(res.job_id)
            .then((job) => {
              if (job.status !== "running") {
                clearInterval(pollId);
                setGenerating(false);
                fetchEnforcer(slug).then(setEnforcer).catch(() => {});
              }
            })
            .catch(() => {
              clearInterval(pollId);
              setGenerating(false);
            });
        }, 2000);
      })
      .catch(() => setGenerating(false));
  };

  const handleGenerateVideo = () => {
    if (!slug) return;
    setVideoGenerating(true);
    setVideoError(null);
    setVideoResult(null);
    setVideoElapsed(0);
    videoStartRef.current = Date.now();
    generateVideo(slug)
      .then((res) => {
        const pollId = setInterval(() => {
          fetchVideoStatus(res.task_id)
            .then((status) => {
              if (status.status === "Success") {
                clearInterval(pollId);
                setVideoResult(status);
                setVideoGenerating(false);
              } else if (status.status === "Fail") {
                clearInterval(pollId);
                setVideoError(status.error || "Video generation failed");
                setVideoGenerating(false);
              }
            })
            .catch(() => {
              clearInterval(pollId);
              setVideoError("Failed to check video status");
              setVideoGenerating(false);
            });
        }, 5000);
      })
      .catch((err) => {
        setVideoError(err instanceof Error ? err.message : "Failed to submit");
        setVideoGenerating(false);
      });
  };

  const handleGenerateTestSprite = () => {
    if (!slug) return;
    setTsGenerating(true);
    setTsError(null);
    generateTestSprite(slug)
      .then((res) => {
        const pollId = setInterval(() => {
          fetchJobStatus(res.job_id)
            .then((job) => {
              if (job.status === "completed") {
                clearInterval(pollId);
                setTsGenerating(false);
                fetchRuleTestSpriteResults(slug).then(setTsResults).catch(() => {});
              } else if (job.status === "failed") {
                clearInterval(pollId);
                setTsGenerating(false);
                setTsError("TestSprite generation failed");
              }
            })
            .catch(() => {
              clearInterval(pollId);
              setTsGenerating(false);
              setTsError("Failed to check job status");
            });
        }, 2000);
      })
      .catch((err) => {
        setTsError(err instanceof Error ? err.message : "Failed to start");
        setTsGenerating(false);
      });
  };

  if (loading) {
    return <div style={{ textAlign: "center", padding: "48px", color: "#94a3b8" }}>Loading...</div>;
  }

  if (error || !rule) {
    return (
      <div style={{ textAlign: "center", padding: "48px", color: "#ef4444" }}>
        {error ?? "Rule not found"}
      </div>
    );
  }

  const canEnforcer = !!rule.negative_example;
  const canVideo = !!(rule.positive_example || rule.negative_example);

  return (
    <div>
      <Link to="/" style={backStyle}>
        &larr; Back to rules
      </Link>

      <div style={headerStyle}>
        <h1 style={titleStyle}>{rule.title}</h1>
        <div style={slugStyle}>{rule.slug}</div>
        <div style={badgeRowStyle}>
          <Badge
            label={rule.category}
            color={categoryColors[rule.category] ?? "#64748b"}
          />
          <Badge
            label={rule.severity}
            color={severityColors[rule.severity] ?? "#64748b"}
          />
          <StatusBadge active={rule.is_active} />
          <span style={{ fontSize: "13px", color: "#94a3b8" }}>
            v{rule.version}
          </span>
        </div>
      </div>

      {/* Action bar */}
      <div
        style={{
          display: "flex",
          gap: "10px",
          flexWrap: "wrap",
          alignItems: "center",
          marginBottom: "32px",
          padding: "16px 20px",
          background: "#f8fafc",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
        }}
      >
        <button
          onClick={handleGenerateEnforcer}
          disabled={generating || !canEnforcer}
          title={canEnforcer ? undefined : "Needs a negative example"}
          style={actionButtonStyle("#3b82f6", generating || !canEnforcer)}
        >
          {generating ? <><Spinner /> Generating Enforcer...</> : enforcer ? "Regenerate Enforcer" : "Generate Enforcer"}
        </button>

        <button
          onClick={handleGenerateVideo}
          disabled={videoGenerating || !canVideo}
          title={canVideo ? undefined : "Needs code examples"}
          style={actionButtonStyle("#8b5cf6", videoGenerating || !canVideo)}
        >
          {videoGenerating ? (
            <>
              <Spinner /> Generating Video... {Math.floor(videoElapsed / 60)}:{String(videoElapsed % 60).padStart(2, "0")}
            </>
          ) : videoResult?.status === "Success" ? "Regenerate Video" : "Generate Video"}
        </button>

        <button
          onClick={handleGenerateTestSprite}
          disabled={tsGenerating}
          style={actionButtonStyle("#10b981", tsGenerating)}
        >
          {tsGenerating ? <><Spinner /> Generating Tests...</> : tsResults.length > 0 ? "Regenerate Tests" : "Generate Tests"}
        </button>

        {videoError && (
          <span style={{ fontSize: "13px", color: "#ef4444" }}>{videoError}</span>
        )}
        {tsError && (
          <span style={{ fontSize: "13px", color: "#ef4444" }}>{tsError}</span>
        )}
      </div>

      {/* Video result (show inline when ready) */}
      {videoResult?.status === "Success" && videoResult.download_url && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Video</h2>
          <video
            controls
            style={{
              width: "100%",
              maxWidth: "720px",
              borderRadius: "8px",
              background: "#000",
            }}
            src={videoResult.download_url}
          />
          <div style={{ marginTop: "8px", display: "flex", gap: "8px", alignItems: "center" }}>
            <Badge label="Ready" color="#22c55e" />
            {videoElapsed > 0 && (
              <span style={{ fontSize: "13px", color: "#64748b" }}>
                Generated in {Math.floor(videoElapsed / 60)}:{String(videoElapsed % 60).padStart(2, "0")}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Description */}
      <div style={sectionStyle}>
        <h2 style={sectionTitle}>Description</h2>
        <div style={textBlock}>{rule.description}</div>
      </div>

      {/* Examples */}
      {(rule.positive_example || rule.negative_example) && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Examples</h2>
          {rule.positive_example && (
            <div
              style={{
                borderLeft: "4px solid #22c55e",
                borderRadius: "8px",
                paddingLeft: "0",
                marginBottom: "16px",
                overflow: "hidden",
              }}
            >
              <CodeBlock
                code={rule.positive_example}
                language="python"
                title="Good"
              />
            </div>
          )}
          {rule.negative_example && (
            <div
              style={{
                borderLeft: "4px solid #ef4444",
                borderRadius: "8px",
                paddingLeft: "0",
                overflow: "hidden",
              }}
            >
              <CodeBlock
                code={rule.negative_example}
                language="python"
                title="Bad"
              />
            </div>
          )}
        </div>
      )}

      {/* Rationale */}
      <div style={sectionStyle}>
        <h2 style={sectionTitle}>Rationale</h2>
        <div style={textBlock}>{rule.rationale}</div>
      </div>

      {/* Constraints */}
      {rule.constraints && rule.constraints.length > 0 && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Constraints</h2>
          <ul style={{ paddingLeft: "24px", color: "#334155", fontSize: "15px" }}>
            {rule.constraints.map((c, i) => (
              <li key={i} style={{ marginBottom: "4px" }}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Function type sources */}
      {(rule.decorator_source || rule.linter_source) && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Implementation</h2>
          {rule.decorator_name && (
            <p style={{ fontSize: "14px", color: "#64748b", marginBottom: "12px" }}>
              Decorator: <code style={{ fontWeight: 600 }}>{rule.decorator_name}</code>
            </p>
          )}
          {rule.decorator_source && (
            <CollapsibleCode
              title="Decorator Source"
              code={rule.decorator_source}
            />
          )}
          {rule.linter_source && (
            <CollapsibleCode
              title="Linter Source"
              code={rule.linter_source}
            />
          )}
        </div>
      )}

      {/* Enforcer */}
      {enforcer && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Enforcer</h2>
          <div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "12px" }}>
              <Badge
                label={enforcer.status}
                color={enforcer.status === "passed" ? "#22c55e" : enforcer.status === "failed" ? "#ef4444" : "#f59e0b"}
              />
              <span style={{ fontSize: "13px", color: "#64748b" }}>
                {enforcer.check_type} check | {enforcer.attempt_count} attempt(s)
              </span>
            </div>
            <TabBar
              tabs={[
                { key: "source", label: "Source" },
                { key: "diff", label: "Diff", disabled: !enforcer.diff },
                { key: "decorator", label: "Decorator", disabled: !enforcer.decorator_source },
                { key: "test", label: "Test Output", disabled: !enforcer.test_output },
              ]}
              active={enforcerTab}
              onChange={setEnforcerTab}
            />

            {enforcerTab === "source" && enforcer.enforcer_source && (
              <CodeBlock code={enforcer.enforcer_source} language="python" />
            )}

            {enforcerTab === "diff" && enforcer.diff && (
              <CodeBlock code={enforcer.diff} language="diff" />
            )}

            {enforcerTab === "decorator" && enforcer.decorator_source && (
              <CodeBlock code={enforcer.decorator_source} language="python" />
            )}

            {enforcerTab === "test" && enforcer.test_output && (
              <pre style={{ background: "#1e293b", color: "#e2e8f0", padding: "12px", borderRadius: "8px", fontSize: "13px", overflow: "auto", whiteSpace: "pre-wrap" }}>
                {enforcer.test_output}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* TestSprite results */}
      {tsResults.length > 0 && (
        <div style={sectionStyle}>
          <h2 style={sectionTitle}>Test Results ({tsResults.length})</h2>
          {tsResults.map((r) => (
            <div
              key={r.id}
              style={{
                display: "flex",
                gap: "12px",
                alignItems: "center",
                padding: "10px 16px",
                background: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                marginBottom: "8px",
                fontSize: "13px",
              }}
            >
              <Badge
                label={r.status}
                color={r.status === "passed" ? "#22c55e" : r.status === "failed" ? "#ef4444" : "#f59e0b"}
              />
              <span style={{ color: "#64748b" }}>{new Date(r.created_at).toLocaleString()}</span>
              <Link
                to={`/tests`}
                style={{ color: "#3b82f6", textDecoration: "none", marginLeft: "auto" }}
              >
                View details
              </Link>
            </div>
          ))}
        </div>
      )}

      {/* Provenance */}
      <div style={sectionStyle}>
        <h2 style={sectionTitle}>
          Provenance ({provenance.length} source{provenance.length !== 1 ? "s" : ""})
        </h2>
        {provenance.length === 0 ? (
          <div style={{ color: "#94a3b8", fontSize: "14px" }}>
            No provenance records found for this rule.
          </div>
        ) : (
          provenance.map((item, i) => (
            <ProvenanceCard key={i} item={item} />
          ))
        )}
      </div>
    </div>
  );
}

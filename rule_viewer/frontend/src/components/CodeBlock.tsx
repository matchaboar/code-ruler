import { Highlight, themes } from "prism-react-renderer";

interface CodeBlockProps {
  code: string;
  language?: string;
  title?: string;
}

const wrapperStyle: React.CSSProperties = {
  borderRadius: "8px",
  overflow: "hidden",
  marginBottom: "16px",
};

const titleBarStyle: React.CSSProperties = {
  background: "#1e293b",
  color: "#94a3b8",
  padding: "8px 16px",
  fontSize: "12px",
  fontWeight: 600,
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

export function CodeBlock({ code, language = "python", title }: CodeBlockProps) {
  return (
    <div style={wrapperStyle}>
      {title && <div style={titleBarStyle}>{title}</div>}
      <Highlight theme={themes.nightOwl} code={code.trim()} language={language}>
        {({ style, tokens, getLineProps, getTokenProps }) => (
          <pre
            style={{
              ...style,
              padding: "16px",
              margin: 0,
              fontSize: "13px",
              lineHeight: 1.6,
              overflowX: "auto",
            }}
          >
            {tokens.map((line, i) => (
              <div key={i} {...getLineProps({ line })}>
                <span
                  style={{
                    display: "inline-block",
                    width: "2em",
                    textAlign: "right",
                    marginRight: "1em",
                    color: "#475569",
                    userSelect: "none",
                  }}
                >
                  {i + 1}
                </span>
                {line.map((token, key) => (
                  <span key={key} {...getTokenProps({ token })} />
                ))}
              </div>
            ))}
          </pre>
        )}
      </Highlight>
    </div>
  );
}

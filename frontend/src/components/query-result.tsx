"use client";
import * as Tabs from "@radix-ui/react-tabs";
import { useState } from "react";
import { Table2, Code2, Activity, Copy, Download, Check } from "lucide-react";
import { QueryResult as Result } from "@/lib/api";
function cell(value: unknown): string {
  return value === null || value === undefined
    ? "NULL"
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
}
export function QueryResult({ result }: { result: Result }) {
  const [page, setPage] = useState(0);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  function download() {
    const csv = [
      result.columns,
      ...result.rows.map((row) =>
        result.columns.map((column) => cell(row[column])),
      ),
    ]
      .map((row) =>
        row
          .map(
            (value) =>
              '"' +
              String(value)
                .replace(/^[=+@\-\t\r]/, "'$&")
                .replaceAll('"', '""') +
              '"',
          )
          .join(","),
      )
      .join("\r\n");
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8;" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "rowan-results.csv";
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="result">
      <div className="answer-heading">
        <span className="mini-mark">r.</span>Rowan
      </div>
      {result.summary && <p className="summary">{result.summary}</p>}
      <Tabs.Root defaultValue="data">
        <div className="result-toolbar">
          <Tabs.List aria-label="Query details">
            <Tabs.Trigger value="data">
              <Table2 size={15} />
              Results
            </Tabs.Trigger>
            <Tabs.Trigger value="sql">
              <Code2 size={15} />
              SQL
            </Tabs.Trigger>
            <Tabs.Trigger value="metrics">
              <Activity size={15} />
              Details
            </Tabs.Trigger>
          </Tabs.List>
          <button
            className="icon-button"
            aria-label="Download results as CSV"
            onClick={download}
          >
            <Download size={16} />
          </button>
        </div>
        <Tabs.Content value="data">
          <div className="table-scroll">
            {result.rows.length ? (
              <table>
                <thead>
                  <tr>
                    {result.columns.map((column) => (
                      <th key={column}>{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows
                    .slice(page * 20, (page + 1) * 20)
                    .map((row, index) => (
                      <tr key={index}>
                        {result.columns.map((column) => (
                          <td
                            key={column}
                            className={row[column] == null ? "null-cell" : ""}
                          >
                            {cell(row[column])}
                          </td>
                        ))}
                      </tr>
                    ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-results">
                No matching rows. Try broadening your filters.
              </div>
            )}
          </div>
          <div className="result-footer">
            <span>
              {result.row_count.toLocaleString()} rows ·{" "}
              {result.execution_time_ms.toLocaleString()} ms
              {result.truncated ? " · Row limit reached" : ""}
            </span>
            {result.rows.length > 20 && (
              <div>
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </button>
                <span>
                  {page + 1} / {Math.ceil(result.rows.length / 20)}
                </span>
                <button
                  disabled={(page + 1) * 20 >= result.rows.length}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </Tabs.Content>
        <Tabs.Content value="sql">
          <div className="sql-actions">
            <span>Executed SQL</span>
            <button
              className="text-button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(result.sql_query);
                  setCopied(true);
                  setCopyError(false);
                  setTimeout(() => setCopied(false), 2000);
                } catch {
                  setCopyError(true);
                }
              }}
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}{" "}
              {copied ? "Copied" : "Copy SQL"}
            </button>
          </div>
          {copyError && (
            <p role="alert">Copy unavailable. Select and copy the SQL below.</p>
          )}
          <pre className="sql">
            <code>{result.sql_query}</code>
          </pre>
        </Tabs.Content>
        <Tabs.Content value="metrics">
          <dl className="metrics">
            {[
              ["Execution time", `${result.execution_time_ms} ms`],
              ["Rows returned", result.row_count],
              ["Total tokens", result.token_usage.total_tokens],
              ["Input tokens", result.token_usage.input_tokens],
              ["Output tokens", result.token_usage.output_tokens],
              ["Cached input", result.token_usage.cached_input_tokens],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

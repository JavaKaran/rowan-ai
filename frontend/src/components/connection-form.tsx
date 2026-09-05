"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Database, ArrowRight, LoaderCircle, ShieldCheck } from "lucide-react";
import { request } from "@/lib/api";
import type {
  Connection,
  Context,
  DatabaseConnectionResult,
} from "@/types";
export function ConnectionForm({
  context,
  onConnected,
}: {
  context: Context;
  onConnected: (name: string, type: string) => void;
}) {
  const [type, setType] = useState<Connection["database_type"]>("postgresql");
  const mutation = useMutation({
    mutationFn: (data: Connection) =>
      request<DatabaseConnectionResult>("connection/", context, data),
    onSuccess: (data) => {
      if (data.success) onConnected(data.database_name, data.database_type);
    },
  });
  return (
    <div className="connection-panel">
      <div className="large-icon">
        <Database size={26} />
      </div>
      <h1>Meet your database.</h1>
      <p>Connect a database to start a conversation with your data.</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          const data = new FormData(event.currentTarget);
          mutation.mutate({
            database_type: type,
            host: String(data.get("host")).trim(),
            port: Number(data.get("port")),
            database_name: String(data.get("database_name")).trim(),
            username: String(data.get("username")).trim(),
            password: String(data.get("password")),
            ssl_mode: type === "postgresql" ? String(data.get("ssl_mode")) : "",
          });
        }}
      >
        <fieldset disabled={mutation.isPending}>
          <legend className="field-label">Database type</legend>
          <div className="database-types">
            {(["postgresql", "mysql"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={value === type}
                className={value === type ? "selected" : ""}
                onClick={() => {
                  setType(value);
                  mutation.reset();
                }}
              >
                <Database size={18} />
                {value === "postgresql" ? "PostgreSQL" : "MySQL"}
              </button>
            ))}
          </div>
          <div className="form-grid">
            <label className="wide">
              Host
              <input
                name="host"
                required
                placeholder="db.example.com"
                autoComplete="off"
              />
            </label>
            <label>
              Port
              <input
                key={type}
                name="port"
                type="number"
                required
                min={1}
                max={65535}
                defaultValue={type === "postgresql" ? 5432 : 3306}
              />
            </label>
            <label>
              Database name
              <input
                name="database_name"
                required
                placeholder="analytics"
                autoComplete="off"
              />
            </label>
            <label>
              Username
              <input
                name="username"
                required
                placeholder="readonly_user"
                autoComplete="off"
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                required
                placeholder="Enter database password"
                autoComplete="off"
              />
            </label>
            {type === "postgresql" && (
              <label className="wide">
                SSL mode
                <select
                  name="ssl_mode"
                  key={`${type}-ssl`}
                  defaultValue="require"
                >
                  {(type === "postgresql"
                    ? [
                        "require",
                        "verify-full",
                        "verify-ca",
                        "prefer",
                        "disable",
                      ]
                    : ["require", "disable"]
                  ).map((mode) => (
                    <option key={mode} value={mode}>
                      {mode}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          {(mutation.error || mutation.data?.success === false) && (
            <div className="error" role="alert">
              {mutation.error?.message || mutation.data?.message}
            </div>
          )}
          <button className="button full" type="submit">
            {mutation.isPending ? (
              <>
                <LoaderCircle className="spin" size={17} />
                Connecting…
              </>
            ) : (
              <>
                Connect database
                <ArrowRight size={17} />
              </>
            )}
          </button>
        </fieldset>
      </form>
      <div className="connection-note">
        <ShieldCheck size={16} />
        <span>
          Use a read-only database user. Credentials are sent to the backend and
          never saved in your browser.
        </span>
      </div>
    </div>
  );
}

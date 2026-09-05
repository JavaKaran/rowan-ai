/**
 * Database connection types.
 * Mirrors `backend/app/schemas/database_connection.py`
 * (`DatabaseConnectionCreate` / `DatabaseConnectionResponse`)
 * backed by the `database_connections` table.
 */
export type Connection = {
  database_type: "postgresql" | "mysql";
  host: string;
  port: number;
  database_name: string;
  username: string;
  password: string;
  ssl_mode: string;
};

export type DatabaseConnectionResult = {
  success: boolean;
  message: string;
  database_type: string;
  database_name: string;
};

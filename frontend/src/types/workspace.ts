/**
 * Workspace types.
 * Mirrors `backend/app/schemas/workspace.py` (`WorkspaceResponse`)
 * backed by the `workspaces` table.
 */
export type Workspace = {
  workspace_key: string;
  name?: string | null;
};

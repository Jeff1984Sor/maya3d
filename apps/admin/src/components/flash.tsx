import { Alert } from "./ui";

/** Mostra ?ok= / ?erro= vindos dos redirects das server actions. */
export function Flash({ ok, erro }: { ok?: string; erro?: string }) {
  if (erro) return <Alert tone="error">{erro}</Alert>;
  if (ok) return <Alert tone="ok">{ok}</Alert>;
  return null;
}

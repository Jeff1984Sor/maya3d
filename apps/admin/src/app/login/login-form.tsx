"use client";

import { useActionState } from "react";
import { Alert, Button, Label, inputClass } from "@/components/ui";
import { login } from "./actions";

export function LoginForm({ next }: { next: string }) {
  const [state, action, pending] = useActionState(login, {});
  return (
    <form action={action} className="space-y-4">
      {state.error && <Alert tone="error">{state.error}</Alert>}
      <input type="hidden" name="next" value={next} />
      <Label label="Senha">
        <input name="password" type="password" required autoFocus autoComplete="current-password" className={inputClass} />
      </Label>
      <Button type="submit" disabled={pending} className="w-full">
        {pending ? "Entrando…" : "Entrar"}
      </Button>
    </form>
  );
}

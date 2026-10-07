"use client";

import { useState, useTransition } from "react";
import { issueRobotToken, revokeRobotToken } from "@/actions/integrations";
import { Badge, Button, Card } from "@/components/ui";

/** Token temporário para o robô de importação. Aparece uma vez só: copie na hora. */
export function RobotToken({ active, expiresAt }: { active: boolean; expiresAt: string | null }) {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [pending, start] = useTransition();

  return (
    <Card title="🤖 Robô (automações)">
      <p className="mb-3 text-sm text-muted">
        Token temporário para o robô que sobe o acervo do seu computador. Vale 7 dias, aparece uma vez só e pode ser revogado a
        qualquer momento. Tudo o que o robô faz fica na Auditoria.
      </p>
      <div className="mb-3 flex items-center gap-2 text-sm">
        <Badge tone={active ? "ok" : "muted"}>{active ? "ativo" : "sem token"}</Badge>
        {active && expiresAt && <span className="text-xs text-muted">vale até {new Date(expiresAt).toLocaleString("pt-BR")}</span>}
      </div>
      {token && (
        <div className="mb-3 space-y-2 rounded-xl border border-secondary bg-secondary/5 p-3">
          <p className="text-xs font-medium">Copie agora (não aparece de novo):</p>
          <code className="block break-all rounded bg-bg p-2 text-xs">{token}</code>
          <Button
            variant="secondary"
            onClick={async () => {
              await navigator.clipboard.writeText(token);
              setCopied(true);
            }}
          >
            {copied ? "Copiado ✓" : "Copiar token"}
          </Button>
        </div>
      )}
      {error && <p className="mb-3 text-sm text-primary">{error}</p>}
      <div className="flex gap-2">
        <Button
          disabled={pending}
          onClick={() =>
            start(async () => {
              const res = await issueRobotToken();
              if ("error" in res) setError(res.error);
              else {
                setToken(res.token);
                setError(null);
              }
            })
          }
        >
          {active ? "Gerar novo token" : "Gerar token"}
        </Button>
        {active && (
          <Button variant="danger" disabled={pending} onClick={() => start(async () => void (await revokeRobotToken()))}>
            Revogar
          </Button>
        )}
      </div>
    </Card>
  );
}

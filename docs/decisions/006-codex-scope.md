# 006 — Subscription-backed Codex with server-enforced tools

Use the official pinned Python Codex SDK and its matching runtime, managed ChatGPT sign-in, and an isolated profile. The application uses the account's shared Codex allowance. It supplies no API key, buys no credits and changes no billing settings. Existing account credit/reload settings can apply after included usage. [Codex authentication](https://learn.chatgpt.com/docs/auth), [account credits](https://help.openai.com/en/articles/12642688-using-credits-for-flexible-usage-in-chatgpt-personal-plans).

The runtime has a read-only sandbox, approval policy `never`, disabled shell/web/unrelated capabilities, and exactly one scoped MCP server. Keep the tool-dispatch host enabled because the installed runtime uses it for MCP calls. Read-only annotations and per-tool automatic approval allow only the listed evidence operations; the inventory is verified before a turn.

Six claim tools or three ontology-review tools call a narrow local HTTP API. The server derives case, country, projection and role from a short-lived token. Inputs cannot select new scope; excerpt IDs must have been issued to the run. Revocation and a 20-call budget apply server-side. The protocol probe exercises actual STDIO serialization and rejects scope-changing arguments, cross-country evidence and writes.

Persist explicit progress, IDs, model, usage, validated results and bounded errors—not hidden reasoning or credentials. A completed turn must pass schema and evidence-context checks. One repair is permitted inside the 180-second total budget. A new source/snapshot starts a fresh thread and leaves the old brief intact. Read-only ontology suggestions cannot approve or activate anything.

The model may still misinterpret evidence. Deterministic citation membership is not entailment, so live verification includes source-by-source inspection and retains limitations. Original facts, generated suggestions and explicit simulated human decisions remain separate.

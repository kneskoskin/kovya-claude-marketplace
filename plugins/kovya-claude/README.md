# Kovya for Claude Code: Windows preview 0.1.0-preview.10.8

Local review candidate for the proposed kneskoskin/kovya-claude-marketplace repository. Catalog: kovya-claude-marketplace. Plugin: kovya-claude. Runtime/minimum: 1.0.13. Windows x64 only.

This package targets Claude Code CLI and local Claude Code sessions in Desktop. Desktop loading, actual hook approval, MCP initialization, sign-in, saving and recall remain unverified. This is not a Cowork or web-chat integration. The marketplace has not been published or installed by this assembly.

After independent review and publication, add the marketplace and install its plugin in a local Claude Code session. The commands are:

```text
/plugin marketplace add kneskoskin/kovya-claude-marketplace
/plugin install kovya-claude@kovya-claude-marketplace
```

For this comparison, use a new empty local project and select Install for you, in this repo only (local scope) in the plugin detail panel. A project folder alone does not prevent a user-wide install. The first trial checks the connected server and advertised tool list without invoking the tools. Connect, automatic memory hooks and servicing require their own trial decision.

These steps target Claude Code CLI and local Claude Code sessions in Desktop on Windows x64. They are not instructions for a remote cloud session, Cowork, or web chat. Installation and hook approval can activate the memory effects described below and require the applicable authorization. This assembly did not run these commands.

After that authorized installation and host refresh, ask the kovya-setup skill to Connect Kovya. The skill uses this plugin's pinned Node, wrapper and claude_code host. Connect opens the default browser for email and emailed code; keep credentials, codes and approval addresses out of chat. Follow the skill's diagnosis and single-consent repair rules; do not blindly repeat an uncertain operation.

When enabled and approved by the host, SessionStart recalls memory, UserPromptSubmit uses the current prompt to recall relevant memory, and Stop reads the host-selected transcript and attempts to save the latest user/assistant exchange. These hooks can read and write Kovya account data and local diagnostic/runtime state. Hook approval or installation must not be represented as a harmless metadata-only operation.

The adapter preserves the host's KOVYA_HOME override and otherwise selects the user's normal .kovya home. It neither isolates accounts by plugin name nor migrates existing state. Use of a shared existing home may affect the same account/runtime as other Kovya hosts. No home was accessed during assembly.

The unchanged included Node, role-specific native executables and addon bytes are reused from Claude marketplace commit 8f1a19275f11f67808df0436e38ddd8b2b7260b0 without compilation. The approved JavaScript changes and their new dependencies are folded into both frontend and runtime payload, with a freshly generated 1.0.13 descriptor and requirement. The Claude host metadata is derived from the canonical Claude adapter. The earlier 10.6 package notes recorded an installed-host MCP startup refusal; this file-only assembly does not establish its resolution. Do not describe this candidate as operationally accepted.

Claude's plugin-root variable selects bundled commands. No Codex MCP cwd field, Codex plugin manifest or Codex SessionEnd hook is registered. The three command hooks use Claude exec form: the bundled .exe path and separate argument vectors, without a shell. Actual hook launch and results require their own authorized host check. The manifest references the bundled Kovya mark; visible icon rendering is unverified.

This local 10.8 candidate adds verified human-turn capture with response-level narrated tool support, truthful callback receipt/refusal pages, and D2 query admission up to 256 while query generation remains 24. Expanded server writing remains off and requires its separate server rollout; this package does not deploy a server or reindex old records. A callback receipt is not proof of saving or recall. Independent assembly review, publication, installation, native runtime admission and the authorized live save/recall trial remain pending. Readiness #3396 and R2 changes are excluded.

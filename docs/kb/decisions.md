# Package decisions and constraints

These package choices are recorded in the current manifests and README.

| Decision or constraint | Evidence | Reason / limit |
|---|---|---|
| Offer one Claude plugin from the marketplace catalog. | [Marketplace manifest](../../.claude-plugin/marketplace.json) | The `kovya-claude` entry points to `plugins/kovya-claude` and identifies the Windows x64 preview. |
| Support local Claude Code CLI and Desktop sessions on Windows x64. | [Marketplace manifest](../../.claude-plugin/marketplace.json), [plugin README](../../plugins/kovya-claude/README.md) | Cowork and web chat are outside this package's target. The plugin README lists host behaviors that remain unverified. |
| Connect through Claude MCP and lifecycle hooks. | [Hook config](../../plugins/kovya-claude/hooks/hooks.json), [MCP config](../../plugins/kovya-claude/.mcp.json) | When installed and approved, hooks can recall memory and attempt to save a turn. They can access prompts, selected transcripts, account data and local runtime state. |
| Check the included runtime and helper before local runtime admission. | [Runtime requirement](../../plugins/kovya-claude/connector/plugin/runtime-requirement.json), [runtime descriptor](../../plugins/kovya-claude/runtime/descriptor.json) | The package carries its Node runtime and native Windows helper with integrity bindings. |
| Use the configured Kovya home without plugin-specific namespacing. | [Plugin layout](../../plugins/kovya-claude/connector/plugin/layout.mjs) | A shared `.kovya` home can share account and runtime state across hosts. |
| Treat this repository as a review candidate. | [Root README](../../README.md), [plugin README](../../plugins/kovya-claude/README.md) | Publication, installation and observed host behavior are separate release steps. |
# Local 10.8 file-only assembly

Use the complete served Claude 10.6 tree, not the M1 readiness worktree or the different 10.7 local candidate. Fold only the accepted sixteen source members, regenerate the 1.0.13 runtime descriptor and matching frontend requirement, and preserve unchanged role-specific binary and generated-binding bytes. Keep launch metadata and the existing KB checker/hook intact. Allocation, local assembly and disconnected checks do not imply publication, installation, native admission or live verification. Independent release review and the separate server rollout remain required.


# Claude plugin package

`plugins/kovya-claude` is the shipped plugin and runtime boundary. Its Claude manifest points to the skills, icon and `.mcp.json`. The MCP server launches the bundled Windows native broker helper. `hooks.json` registers `SessionStart`, `UserPromptSubmit` and `Stop` command hooks that invoke the helper with the matching host event.

The hook worker dispatches events through the memory client. Session start requests recall for the new session. Prompt submission uses the current prompt to request relevant recall. Stop reads the host-selected transcript and attempts to capture the latest exchange. Failed or unconfirmed operations are reported as unavailable or unconfirmed, so a hook invocation alone does not establish a successful save or recall.

Setup is exposed through the bundled `kovya` command. The package includes a pinned Node runtime, connector modules and a native Windows helper. The command selects a supported host and setup operation, checks the packaged runtime and delegates through the native helper. Runtime admission verifies the helper and payload before publishing or upgrading local runtime files. Repair and sign-in use separate consent and protected-input flows. Installing the plugin does not sign in the user.

The package preserves the `KOVYA_HOME` override and otherwise uses the normal `.kovya` home. Hosts using the same home may share an account and runtime state. The package does not namespace state by plugin name or migrate an existing home. The bundled runtime payload contains copies of connector modules, alongside the pinned Node runtime and native helper.

## Scope and limits

- The declared target is Windows x64 with Claude Code CLI and local Claude Code in Desktop.
- Cowork and web chat are outside the supported host scope.
- Desktop loading, host approval, MCP initialization, browser sign-in, saving and recall remain unverified by repository packaging.
- Hooks can read prompts or selected transcripts and can access Kovya account and local runtime state. Installation and hook approval enable those effects.

Key source boundaries: [`plugin.json`](../../../plugins/kovya-claude/.claude-plugin/plugin.json), [MCP server config](../../../plugins/kovya-claude/.mcp.json), [hook declarations](../../../plugins/kovya-claude/hooks/hooks.json), [event dispatch](../../../plugins/kovya-claude/connector/plugin/dispatch.mjs), [worker](../../../plugins/kovya-claude/connector/plugin/worker.mjs), [package command](../../../plugins/kovya-claude/bin/kovya.mjs), [runtime requirement](../../../plugins/kovya-claude/connector/plugin/runtime-requirement.mjs), [runtime admission](../../../plugins/kovya-claude/connector/plugin/native-admission.mjs) and [plugin usage notes](../../../plugins/kovya-claude/README.md).

[Owning files](../_generated/filemap.md#component-plugins) · [Layout selection](../_generated/codemap.md#symbol-4e298863775a47777259) · [Host event dispatch](../_generated/codemap.md#symbol-5363368a835f0d114c4f) · [Native admission](../_generated/codemap.md#symbol-fad117a85d4418c8bbf1)

<!-- kb-reviewed: 6c4a1490d7879831dba7813110b1b3e87e9c447738ed0642f3d17672fa50caf2 -->

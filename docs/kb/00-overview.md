# Kovya Claude Code marketplace

This repository packages one Windows x64 Kovya plugin for Claude Code. The marketplace catalog in [`.claude-plugin/marketplace.json`](../../.claude-plugin/marketplace.json) points to the [plugin package](../../plugins/kovya-claude/README.md), which defines its Claude manifest, MCP server, hooks, skills and bundled runtime.

The plugin connects local Claude Code CLI and Claude Code sessions in Desktop to Kovya memory. Its hooks can recall context at session start and before prompts, then attempt to save a turn at stop. These operations use the configured Kovya account and local runtime state, so installation and hook approval enable access to that data.

## Start here

- [Marketplace entry and package selection](components/claude-plugin.md)
- [Plugin runtime, hooks and setup behavior](components/plugins.md)
- [Package structure and runtime model](concepts/package-and-runtime.md)
- [Recorded package decisions and limits](decisions.md)
- [Maintaining these explanations](maintenance.md)

The package includes a pinned runtime and Windows native helper. The [plugin README](../../plugins/kovya-claude/README.md) describes its host scope, memory effects and the parts that still need host verification. This repository is a review candidate. Publication and installation are separate steps.

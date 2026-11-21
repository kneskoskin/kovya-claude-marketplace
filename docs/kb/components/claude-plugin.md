# Marketplace catalog

The root `.claude-plugin/marketplace.json` defines the catalog and its single plugin entry, `kovya-claude`, sourced from `./plugins/kovya-claude`. The entry supplies the package version and identifies its Windows x64 target.

Claude uses this catalog to locate the plugin, then reads the plugin's own `.claude-plugin/plugin.json` for its skills, icon and MCP configuration. The [plugin package](plugins.md) explains its runtime and hook behavior.

The root README identifies this repository as a local review candidate and keeps publication separate from installation. The [plugin README](../../../plugins/kovya-claude/README.md) describes the intended CLI and Desktop host scope, memory effects, and unverified host behavior, including loading, approval, MCP startup, sign-in, saving and recall.

[Owning files](../_generated/filemap.md#component-claude-plugin) · [Catalog index](../_generated/codemap.md#file-5352ee4067f17e7948e1) · [Catalog source](../../../.claude-plugin/marketplace.json) · [Root package notes](../../../README.md)

<!-- kb-reviewed: c68360ce272b5357935005a0fe12f2babda12fdfe74d4df8d65cfd8fa79ab2ab -->

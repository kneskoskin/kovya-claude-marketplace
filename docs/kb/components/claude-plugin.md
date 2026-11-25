# Marketplace catalog

The root `.claude-plugin/marketplace.json` defines the catalog and its single plugin entry, `kovya-claude`, sourced from `./plugins/kovya-claude`. The entry supplies the package version and identifies its Windows x64 target.

This local assembly allocates preview 0.1.0-preview.10.8 and runtime/minimum 1.0.13. The catalog, plugin manifest and private package metadata agree. Its baseline is the complete public Claude marketplace commit 8f1a19275f11f67808df0436e38ddd8b2b7260b0. Allocation in local files does not publish a version or update the public marketplace; installation and live verification remain pending.

Claude uses this catalog to locate the plugin, then reads the plugin's own `.claude-plugin/plugin.json` for its skills, icon and MCP configuration. The [plugin package](plugins.md) explains its runtime and hook behavior.

The root README identifies this repository as a local review candidate and keeps publication separate from installation. The [plugin README](../../../plugins/kovya-claude/README.md) describes the intended CLI and Desktop host scope, memory effects, and unverified host behavior, including loading, approval, MCP startup, sign-in, saving and recall.

[Owning files](../_generated/filemap.md#component-claude-plugin) · [Catalog index](../_generated/codemap.md#file-5352ee4067f17e7948e1) · [Catalog source](../../../.claude-plugin/marketplace.json) · [Root package notes](../../../README.md)

<!-- kb-reviewed: f499dc47302e040b44b544bc12aac97ee3853a4f137c23d5709fb51aae192ace -->

# Package and runtime boundaries

The marketplace catalog selects a plugin directory and version. The plugin manifest declares Claude-specific assets and runtime configuration. The catalog is the discovery entry point. The package supplies the code that runs in the host.

The plugin package includes connector modules, a pinned Node runtime and a native Windows helper. Before setup, the package checks that the required runtime and helper match the selected release. Runtime admission then publishes or upgrades the local runtime.

The source connector modules also appear in the runtime payload. The installed runtime uses those packaged copies.

Descriptor identity is SHA-256 of the exact compact JSON object with ordered keys version, files and entrypoints. Files are sorted by path and contain hashes of actual payload bytes; entrypoint keys are node, broker, native and client. The release loader verifies that digest and each listed file. Reusing unchanged native bytes does not reuse the old runtime identity: the new JavaScript and version produce a new descriptor and matching requirement. File checks establish package consistency, not native runtime admission or a successful live memory operation.

The plugin uses the user's normal `.kovya` home unless `KOVYA_HOME` is set. Other Kovya hosts configured to the same location may use the same account and runtime state. Installing the plugin does not create a separate account or home.

Related explanations: [plugin package](../components/plugins.md), [marketplace catalog](../components/claude-plugin.md), and [recorded package decisions](../decisions.md).

# Maintaining the package knowledge base

Start with [the overview](00-overview.md), then read the component page affected by a source change. The checked-in `check_kb.py` regenerates the filemap and codemap, reports source changes that need explanation review, validates local documentation links and checks ownership. Python 3.10 or newer and Git are required. Map generation works offline.

## Update and review

From the repository root:

1. Run `py -3 docs/kb/check_kb.py --refresh` to regenerate both maps.
2. Update the affected explanation, concepts or decisions from the current source and caller behavior. If the existing explanation remains accurate, read it and acknowledge that component with `py -3 docs/kb/check_kb.py --review COMPONENT`. Multiple component IDs may be supplied after `--review`.
3. Run `py -3 docs/kb/check_kb.py` for a working-tree check. Before a proposed change is accepted, run `py -3 docs/kb/check_kb.py --staged` against the exact index. This includes partially staged files.

Review records that the author compared the explanation with current behavior. The checker cannot determine whether the prose is semantically true. Draft pages, stale generated maps, missing source and unreviewed source changes fail. Do not acknowledge a component without inspecting its page and owning source.

## Inventory and maps

`_inventory.json` records source ownership, source-language coverage and initialization evidence. Add a component only when a distinct source boundary needs its own explanation. A new source path must have one clear owner. Update the inventory and component page together. Do not exclude an authored file to make review pass.

The filemap and codemap summarize repository files and supported source declarations. They provide navigation for text and binary package contents. Regenerate them with the checker and do not edit generated files by hand.

The `docs/kb/.gitattributes` rule preserves generated file bytes across Windows checkouts.

## Local hook

The included `docs/kb/pre-commit` runs the staged check when Git uses `docs/kb` as its hook directory. A clone may use this hook through its local Git configuration. The hook does not stage files or commit changes. Keep any project-specific hook behavior in the existing hook setup and verify the exact staged content before accepting a change.

## Links

Use relative Markdown links to files and headings in this repository. Link from a component explanation to an owning generated-map symbol when one is available. Use the file anchor for other inputs. Maps do not fetch remote links, and source links must stay within the repository.

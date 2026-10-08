# Repository guidance

The portable skill is `skills/animate-architecture/`. It is the canonical source; local installations are snapshots installed by `scripts/install.py`.

- Keep the skill focused on replayable terminal-style architecture diagrams. Do not hardcode the Agent example's names, thresholds or number of steps into the general player.
- Keep the generated HTML self-contained and offline. Preserve SVG node-border ports, continuous paths, stable markers and particles following those paths.
- After template or schema changes, rebuild the HTML in `examples/agent-tree/` and `examples/order-flow/` and run `python3 -m unittest discover -s tests`.
- Validate changed visual behavior in a real browser. For route, layout or timeline changes use the browser verifier on affected examples, inspect actual screenshots, then update committed previews and reports.
- Use `dist/` for temporary build and verification output. Copy only intended example deliverables into `examples/`.
- Update local skills only after source validation; do not modify installed copies as the primary development path.
- Repository visibility is public. Do not change repository visibility or deploy the examples to a hosted site as part of routine updates.
- Preserve the MIT license in the repository, portable skill and generated HTML. Keep the two LICENSE copies and the template's full license comment consistent; record third-party material and its original terms in ATTRIBUTIONS.md when introduced.

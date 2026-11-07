# ha-openframe

Home Assistant integration for [openframe](https://github.com/tycho991/openframe) picture frames.

In planning: the changes under `openspec/changes/` describe the integration, the dashboard card
and photo management. Installation and usage follow with the first release.

## Development

```bash
mise trust && mise install
```

[mise](https://mise.jdx.dev) pins Node, OpenSpec, Python and uv (`.mise.toml`). After Renovate
raises the OpenSpec version, run `mise run openspec-sync` on its branch and commit the
regenerated skills; the `openspec-drift` check fails until then.

Changes follow OpenSpec: `/opsx:propose`, `openspec validate <change>`, `/opsx:apply`,
`/opsx:archive`.

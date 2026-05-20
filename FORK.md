# piTelex (TX35 fork)

This is a fork of upstream [fablab-wue/piTelex](https://github.com/fablab-wue/piTelex)
that adds a single device module, `tx35bridge`, for use with the
[tx35exchd](https://github.com/YOUR-USERNAME/tx35exchd) exchange daemon.

## What this fork adds

The `txDevTx35Bridge` device exposes a localhost TCP socket pair (ports
2343 outbound / 2344 inbound by default) that lets an external exchange
daemon route i-Telex calls to/from a real teleprinter without having to
re-implement the i-Telex protocol. `tx35exchd` uses this to drive a Sagem
TX35 attached to a Raspberry Pi's GPIO via an H-bridge interface.

See `doc/txDevTx35Bridge.md` for protocol and configuration details.

## Files changed vs upstream

- `telex.py` — single `elif` branch added to `init()` to load `tx35bridge`
  when configured.
- `txDevTx35Bridge.py` — new device module (added).

Everything else is untouched. Pulling from upstream `master` should merge
cleanly.

## Enabling the bridge

Add to your piTelex config under `devices`:

```json
"tx35bridge": {
    "type": "tx35bridge",
    "enable": true,
    "port": 2343
}
```

Then run piTelex normally. Connect the partner daemon (`tx35exchd`) to
localhost ports 2343/2344.

## License

GPL-3.0, inherited from upstream. See `LICENSE`.

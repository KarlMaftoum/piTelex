# piTelex (TX35 fork)

This is a fork of upstream [fablab-wue/piTelex](https://github.com/fablab-wue/piTelex)
that adds a single device module, `tx35bridge`, for use with the
[tx35exchd](https://github.com/KarlMaftoum/tx35exchd) exchange daemon.

## What this fork adds

The `txDevTx35Bridge` device exposes a localhost TCP socket pair (ports
2343 outbound / 2344 inbound by default) that lets an external exchange
daemon route i-Telex calls to/from a real teleprinter without having to
re-implement the i-Telex protocol. `tx35exchd` uses this to drive a Sagem
TX35 attached to a Raspberry Pi's GPIO via an H-bridge interface.

See `doc/txDevTx35Bridge.md` for protocol and configuration details.

## Files changed vs upstream

- `txDevTx35Bridge.py` — new device module (added).
- `telex.py` — single `elif` branch added to `init()` to load `tx35bridge`
  when configured.
- `txDevITelexCommon.py` — **peer-silence release** (independent of the
  bridge, and a candidate for upstreaming): `process_connection` tracks the
  time of the last received byte and, if a connection goes totally silent
  for longer than `peer_silence_timeout` (device param, default 90s,
  0 disables), releases the line via the same path as a remote close.

  This restores what the physical current loop gave for free. On a real
  telex circuit "engaged" had to be actively maintained — a dead machine's
  line fell to Space, which after 800ms *was* the clearing signal, so a
  faulty machine could never hold a circuit open. TCP inverted that: an
  ESTABLISHED socket holds the line indefinitely with a peer that has
  vanished. Observed twice in the field: a port scanner's half-open
  connection wedged the server into `occ`-rejecting every caller for 29
  hours, and a correspondent whose NAT silently dropped established
  sessions left zombies that blocked his own redials. Compliant i-Telex
  peers send Acknowledge traffic every second while connected, so total
  silence for 90s reliably means the peer is gone.

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

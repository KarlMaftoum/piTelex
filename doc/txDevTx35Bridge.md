# txDevTx35Bridge

A piTelex device module that exposes an external TCP bridge for an off-board
exchange daemon. Designed for use with [tx35exchd](https://github.com/YOUR-USERNAME/tx35exchd),
which implements Australian CP660 exchange signalling for a Sagem TX35
teleprinter on Raspberry Pi GPIO.

## Why a separate daemon?

The TX35 needs current-loop level signalling (loop reversal, calling and
clearing pulses, dial pulse collection, proceed-to-send) that doesn't fit
cleanly into piTelex's TW39/V.10/ED1000 device model. Splitting it out
keeps piTelex unchanged for its intended hardware while still letting the
TX35 reach the i-Telex network through piTelex's full protocol stack.

## Architecture

```
   i-Telex peer ──TCP 2342──► piTelex ──┐
                                        │ tx35bridge device
                                        │  (this module)
                                        ▼
                              localhost 2343 (out)
                              localhost 2344 (in)
                                        ▲
                                        │
                                  tx35exchd  ──► GPIO ──► TX35
```

piTelex handles all i-Telex protocol (banner, WRU, BAUDOT_DATA packets,
ACK/heartbeat, FIN/END). The bridge passes already-decoded ASCII and
piTelex-internal escape sequences to/from the partner daemon, which is
free to do its own Baudot encoding and current-loop signalling.

## Configuration

In your piTelex config (`.json`):

```json
"devices": {
    "tx35bridge": {
        "type": "tx35bridge",
        "enable": true,
        "port": 2343
    }
}
```

`port` is the outbound socket (piTelex listens; partner daemon connects).
The inbound socket is `port + 1` (default 2344), used by the partner
daemon to notify piTelex of TX35-side events like dial-out requests.

## Bus protocol

piTelex's internal bus carries ASCII characters and `\x1b`-prefixed escape
commands. The bridge passes these through to/from the partner daemon
verbatim. The partner daemon is responsible for Baudot encode/decode on
the wire (toward the actual teleprinter).

Escape commands:

- `\x1bAT` — line acquired / connection up
- `\x1b#NUMBER` — outbound dial request from teleprinter
- `\x1bST` — stop / clear

Plain characters (0x20–0x7E) are user-visible message body.

## License

GPL-3.0, same as the rest of piTelex.

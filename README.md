# DSMR Smart Meter (Encrypted) — Home Assistant custom integration

A custom integration for **encrypted DSMR / P1 smart meters**, in particular the
**Luxembourg Smarty** meter (Creos / Sudstroum), which sends AES‑128‑GCM
encrypted (DLMS general‑global‑cipher) telegrams.

It is a fork of the built‑in Home Assistant [`dsmr`] integration that bundles a
**vendored** copy of [`dsmr_parser`] including:

- **Luxembourg Smarty (`MSn`) support** — the encrypted telegram specification
  with the fixed, public authentication key from the *Luxmetering E‑Meter P1
  Specification v1.1.3* (§3.2.5), so you only need to supply your per‑meter
  encryption key. (Based on [ndokter/dsmr_parser#178].)
- **Binary frame handling in the readers** — encrypted telegrams are binary DLMS
  frames (starting with `0xDB`), not the plain `/…!XXXX` text frames. The serial
  and network readers now assemble these frames off the wire and decrypt them.
- **Config‑flow changes** — pick an encrypted meter version and enter the key.

[`dsmr`]: https://www.home-assistant.io/integrations/dsmr
[`dsmr_parser`]: https://github.com/ndokter/dsmr_parser
[ndokter/dsmr_parser#178]: https://github.com/ndokter/dsmr_parser/pull/178
[phase-2 branch]: https://github.com/balloob/dsmr_parser/tree/feature/encrypted-meter-support

## Project status

**This is a staging/testing vehicle, not the intended long‑term home.** It exists
so the *whole chain* — encrypted‑frame decoding → binary framing in the readers →
config‑flow key entry → Home Assistant entities — can be exercised end‑to‑end on a
real meter **while the underlying changes are being upstreamed**. The plan is to
land the library and integration changes upstream and then retire this repo.

The bundled library changes are being upstreamed in two pieces:

- **Luxembourg Smarty (`MSn`) spec + fixed public auth key** → [ndokter/dsmr_parser#178]
  — **merged**, released in `dsmr-parser` v1.8.0.
- **Binary framing + key plumbing through the readers** → the [phase‑2 branch]
  (rebased onto v1.8.0; to be opened as a follow‑up PR against `dsmr_parser`).

Once both land in a released `dsmr-parser` and Home Assistant's built‑in [`dsmr`]
integration picks it up, this custom integration is no longer needed.

> **Why a separate integration in the meantime?** The built‑in `dsmr` integration
> pins a released `dsmr-parser` from PyPI that does not yet contain encrypted‑
> telegram support over the readers. Vendoring the library here avoids a dependency
> clash with that pinned version, so this integration can run alongside the built‑in
> one for testing.

### Keeping in sync with Home Assistant core

The integration code is a fork of core's built‑in [`dsmr`] integration, so it
drifts as core's `dsmr` evolves. When syncing, diff the fork base against core
`dev` and port any `dsmr` changes (e.g. config‑flow / serial‑port handling):

```bash
# in a Home Assistant core checkout
git fetch origin dev
git diff <fork-base-commit>..origin/dev -- homeassistant/components/dsmr/
```

Already ported from core:

- [home-assistant/core#171103] — `SerialPortSelector` for the serial port /
  network serial‑proxy picker.
- [core@d7f42ed] — single serial‑port‑selector config flow: one `user` step,
  network meters via `socket://host:port`, reader factory built in `__init__`
  with legacy host+port migration; drops `create_tcp_dsmr_reader` /
  `create_rfxtrx_tcp_dsmr_reader`.

Fork‑only (not from core, won't transfer upstream as‑is): the encrypted meter
support, and the **labelled** version picker (`DSMR_VERSIONS` is a
`token → label` dict; core uses a plain set / i18n strings).

[home-assistant/core#171103]: https://github.com/home-assistant/core/pull/171103
[core@d7f42ed]: https://github.com/home-assistant/core/commit/d7f42ed0c06f9bb2fd1abd32a53099edd2a42402

## Installation (HACS)

1. In HACS → *Integrations* → ⋮ → **Custom repositories**, add this repository
   URL with category **Integration**.
2. Install **DSMR Smart Meter (Encrypted)** and restart Home Assistant.
3. *Settings → Devices & Services → Add Integration* → **DSMR Smart Meter
   (Encrypted)**.

(Or copy `custom_components/dsmr_encrypted` into your Home Assistant
`config/custom_components/` directory manually.)

## Configuration

1. Choose **Serial** or **Network**.
2. Select the port/device (serial) or host + port (network).
3. Select the **DSMR version**:
   - `MSn` — **Luxembourg Smarty** (encrypted). The Luxembourg Smarty *is* a
     Sagemcom T210‑D, so pick this even if your meter is labelled "Sagemcom
     T210‑D".
   - `SAGEMCOM_T210_D_R` — Sagemcom T210‑D‑R as deployed on the **Austrian**
     grid (Energienetze Steiermark), encrypted. Not for Luxembourg.
   - or any of the standard plain versions (`5`, `5B`, `5L`, …)
4. When an encrypted version is selected, you are asked for the **decryption
   key**:
   - **Luxembourg Smarty (`MSn`)** — enter only the **encryption key** supplied
     by your grid operator (Creos). Leave the authentication key empty; the
     public authentication key is built in.
   - **Austrian Sagemcom** — enter both the **encryption key** and the
     **authentication key**.

### Getting your Luxembourg key

Request the P1 port activation and the encryption key from your grid operator
(Creos) via their customer portal. The key is a 32‑character hexadecimal string.

## Supported meters

| Version | Meter | Keys needed |
| --- | --- | --- |
| `MSn` | Luxembourg Smarty (a Sagemcom T210‑D) | encryption key only (auth key built in) |
| `SAGEMCOM_T210_D_R` | Sagemcom T210‑D‑R on the Austrian grid (Energienetze Steiermark) | encryption + authentication key |
| `2.2`/`4`/`5`/`5B`/`5L`/`5S`/`Q3D`/`5EONHU` | standard plain DSMR meters | none |

> **Luxembourg + "Sagemcom T210‑D"?** The Luxembourg Smarty is Sagemcom T210‑D
> hardware, so use **`MSn`** (single encryption key). The `SAGEMCOM_T210_D_R`
> option is the *Austrian grid* configuration (different telegram layout, needs a
> separate authentication key) — not for Luxembourg.

## Credits & license

- [`dsmr_parser`] by Nigel Dokter and contributors — MIT
  (vendored under `custom_components/dsmr_encrypted/dsmr_parser/`, license
  retained alongside the code).
- Luxembourg Smarty (`MSn`) specification support from
  [ndokter/dsmr_parser#178] by Pol Bettinger.
- Binary framing + key plumbing through the readers — [phase‑2 branch].
- The Home Assistant `dsmr` integration this is forked from.

This repository is MIT licensed (see `LICENSE`).

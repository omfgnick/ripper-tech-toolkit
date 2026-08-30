# ripper-tech-toolkit

**English** · [Português (BR)](README.pt-BR.md)

[![CI](https://github.com/omfgnick/ripper-tech-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/omfgnick/ripper-tech-toolkit/actions/workflows/ci.yml)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-informational)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-informational)](requisitos.txt)

Bench utility for Windows 10/11 repair work — diagnostics, cleanup, repair,
delivery checklist and a signable PDF report — in **Python + PySide6**,
built as a **single executable** that runs from a USB stick.

Written and used by [Nicolas Mesquita Fernandes](https://github.com/omfgnick)
(NOC / N1–N3 support) on the actual bench. Every finding it reports was
verified against real machines, not mocked up.

> It does **not** bypass Windows or Office licensing. The activation panel
> installs a key the customer already owns and triggers the official
> activation — nothing more.

## Layout

```
principal.py        entry point (absolute import, so PyInstaller sees the tree)
construir.py        builds the single-file executable
tecnico/
  nucleo/           31 modules: reads the machine, decides, reports
  ui/               10 panels + the Cyberpunk-flavoured widget layer
testes/             96 tests (unittest, no extra dependency)
docs/decisoes.md    why each non-obvious decision was made
recursos/           Rajdhani (OFL) and Lucide icons (ISC), bundled
```

## The workflow it exists for

One screen runs the whole service in a fixed order and ends in the PDF:

```
mark "before"  →  full scan  →  cleanup  →  SFC  →  mark "after"
               →  disk benchmark  →  delivery checklist  →  PDF
```

The order is code, not instructions, for two reasons that bit us in
testing. The initial state is measured **before** any change — reversed, the
report shows zero gain. And the disk benchmark runs **after** the closing
snapshot, because it writes and reads 192 MB, which moves memory usage; run
earlier, it polluted the comparison with a regression caused by the
measurement itself.

## What it measures

| Area | What it reports |
| --- | --- |
| Hardware | SMART with reference values, battery wear, free RAM slots and upgrade room |
| Disk speed | Sequential and 4 KB random reads, cache bypassed |
| Memory | Four-pattern RAM test, no reboot |
| Windows | Critical events, problem devices, licensing, services, update age |
| Network | Layer-by-layer test, speed against the contracted plan, Wi-Fi channels |
| Persistence | Scheduled tasks and browser extensions — where adware hides |

Every finding says what it **means** and what to **check**. Event ID 11 does
not just read "disk controller error"; it tells you to swap the SATA cable
and port before condemning the drive, because that is the cheapest and most
common cause.

## Three decisions worth knowing

**The before/after comparison has a dead band.** A machine is never idle —
Windows writes logs and cache on its own between the two measurements.
Without the dead band the report would announce "40 MB freed" that nobody
freed. A report that sometimes says "no change" beats one that invents a
result.

**Disk measurement bypasses the cache.** Reading a freshly written file
through the normal API measures RAM, not the disk: Windows serves it from
cache and reports 3 GB/s even on an old spinning drive. With
`FILE_FLAG_NO_BUFFERING` the number is real — and it is what turns "my
computer is slow" into "your drive does 0.6 MB/s on random reads; an SSD
does fifty times that".

**Every Windows query goes through CIM, never console text.** The output of
`ipconfig` and `pnputil` is localised, and any regex over it breaks on an
English install. Learned the hard way.

## Deleting files

Cleanup works from a **whitelist**, and `_dentro_da_lista_branca` re-checks
every path immediately before the `unlink`. Documents, Desktop and Downloads
are never in it.

That guard is the most tested code in the project. The suite covers the
cases that would fool a string comparison — `C:\Windows\Temp2` starts with
`C:\Windows\Temp` and must be refused, and so must a path that climbs out
with `..`.

## Install

Download `Ripper.exe` from the CI artifacts, or build it:

```bash
pip install -r requisitos.txt
python construir.py
```

Creating a folder named `dados` next to the executable switches it to
**portable mode**: history, service records and logs live there instead of
`%LOCALAPPDATA%`, so they travel with the USB stick rather than being left
on customer machines.

## Command line

The executable is built windowed and has no console of its own;
`AttachConsole(-1)` borrows the caller's, so output shows up in the cmd or
PowerShell window you ran it from.

```bash
Ripper.exe --marcar-antes                          # snapshot before the service
Ripper.exe --roteiro --com-limpeza                 # full run, cleanup included
Ripper.exe --relatorio --comparar --saida D:\job\  # scan and PDF
Ripper.exe --autoteste                             # exercise the elevated paths
Ripper.exe --verificar                             # check the packaged resources
```

Exit code **1** when a high-severity finding appears, so a batch file can
stop and call the technician.

## Data and privacy

Everything stays local. History is keyed to the motherboard serial, with a
fallback chain — a hand-built desktop usually reports `To Be Filled By
O.E.M.` in its BIOS, and without the fallback every such machine would share
one history file, mixing unrelated customers.

Service records, checklists and session logs live under
`%LOCALAPPDATA%\Ripper\` (or `dados/` in portable mode) and are excluded
from this repository by `.gitignore`.

## Requirements

- Windows 10 or 11
- Python 3.12+ and the packages in `requisitos.txt` — only to build from source
- Administrator rights for driver export, saved Wi-Fi keys, SMART counters
  and restore points. The app detects the lack and offers to relaunch elevated
  instead of failing mid-operation.

## Development

```bash
python -m unittest discover -s testes
```

96 tests. Beyond the pure rules, one test builds the whole interface, opens
all ten panels and calls **every public method that takes no required
argument** — the exclusion list is by name, so a new method is covered by
default. It exists because three crashes reached real use and none of them
showed up at compile time; the third was caught by that test on its first
run, before shipping.

Two of those tests are skipped on CI: they issue real CIM and PowerShell
queries, which cost seconds here and over fifteen minutes on a cold runner.
They still run locally, which is where they catch the error — before the
commit.

## Design decisions

The reasoning behind the non-obvious choices — why the routine is ordered
the way it is, why services that are "stopped" are usually fine, why the
light theme needs two yellows — is in [docs/decisoes.md](docs/decisoes.md).

## Credits

**Rajdhani** by Indian Type Foundry, SIL OFL 1.1 — the typeface used in the
Cyberpunk 2077 interface, bundled because customer machines will not have it.
**Lucide** icons, ISC — monochrome SVG, recoloured at runtime to signal state.

## License

GPL-3.0. See [LICENSE](LICENSE).

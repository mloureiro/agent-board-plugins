# agent-board-plugins

A marketplace of feed integrations for [agent-board](https://github.com/mloureiro/agent-board). An integration is a program the board runs on a timer to turn items from an outside system into tasks.

## Install

```sh
board plugins install https://github.com/mloureiro/agent-board-plugins
```

The install clones this repository into the board's data directory and pins the commit it checked out. Updates never arrive on their own: the pin moves only when you run

```sh
board plugins update mloureiro
```

Integrations are then referred to as `mloureiro:<integration>`.

## Layout

```
.agent-board/marketplace.json   the manifest the board reads
feeds/<integration>/            one directory per integration, with its program
tests/                          unit tests, including a check of the manifest
```

Every entry under `feeds` in the manifest names a `program`: a relative path to a regular, executable file tracked in this repository (not a symlink).

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The programs use the Python standard library only. CI runs the tests on Python 3.9 and the latest 3.x.

## Changes

`main` is protected: every change lands through a pull request, squash-merged.

## Licence

MIT, see [LICENSE](LICENSE).

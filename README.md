# agmd-cli

A scaffolded Python CLI tool with a Unix-friendly installer script.

## Prerequisites

- `python3` available on your system

## Install

From the project root:

```bash
chmod +x install.sh
./install.sh
```

By default, the installer:

- creates a virtual environment at `~/.local/share/agmd-cli/venv`
- installs this package into that virtual environment
- symlinks the executable to `~/.local/bin/agmd`

You can customize install locations:

```bash
AGMD_APP_DIR="$HOME/.local/share/my-agmd" \
AGMD_BIN_DIR="$HOME/.local/bin" \
./install.sh
```

## Usage

```bash
agmd --help
agmd init  # creates agmd.yml
agmd init --map ".=owner/repo" --map "src=owner/repo/tree/main/src"
agmd add owner/repo --path src
agmd sync
```

`agmd init` also ensures `.gitignore` ignores `AGENTS.md` and `**/.agmd/`,
then renames any existing `AGENTS.md` files in the project to
`AGENTS.local.md`.
If `agmd.yml` already exists, it is left unchanged.

`agmd.yml` uses a list format:

```yaml
- path: "."
  mds:
    - name: "owner/repo"
      module: false
- path: "src"
  mds:
    - name: "owner/repo/tree/main/src"
      module: true
```

## Development

Create and activate a local virtual environment, then install in editable mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
agmd init --map ".=owner/repo"
```

# Porter

> *A porter carries your luggage between places, packs it up for the journey, and makes sure it arrives intact. This tool does the same — for server config files.*

**Porter** is a dual-pane terminal file manager built for homelabs and sysadmins. It works natively over SSH/SFTP between any two hosts, treats archives as virtual filesystems you can browse and build into, and integrates tightly with [labinator](https://github.com/Jerry-Lees/HomeLab) for provisioning deployment archives onto Proxmox LXC containers and VMs.

Born from the same frustration that created Midnight Commander thirty years ago: moving files between servers is tedious, dangerous when done wrong, and deserves better tooling.

---

## Table of Contents

- [About Porter](#about-porter)
- [What Is Actually Built](#what-is-actually-built)
- [Setup Guide](#setup-guide)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Archive Virtual Filesystem](#archive-virtual-filesystem)
- [SSH Connection Manager](#ssh-connection-manager)
- [Snapshot and Deployment Package Builder](#snapshot-and-deployment-package-builder)
- [Labinator Integration](#labinator-integration)
- [Troubleshooting](#troubleshooting)
- [Standing on Good Shoulders](#standing-on-good-shoulders)

---

## About Porter

In the age of steam trains and ocean liners, a porter was the person at the station or dock who took your bags, loaded them onto the right conveyance, and made sure they arrived where they were supposed to go — packed correctly, nothing lost. That's exactly what this tool does for your server config files.

Porter picks up your configs from a live server, packs them into a deployment archive with permissions and ownership intact, and delivers them ready for extraction onto a freshly provisioned container or VM. It works equally well as a general-purpose SSH file manager: browse remote filesystems, copy files between hosts, edit configs in place over SFTP, and manage your homelab infrastructure without ever leaving the terminal.

Two panes. Any combination of local filesystem, remote SSH host, or archive. Everything in one view.

---

## What Is Actually Built

This section documents what is implemented and working today. Features listed elsewhere in the README that are not listed here are planned but not yet built.

### Core file manager
- Dual-pane browser — Tab switches active pane
- Full file listing: name, permissions, owner, size, modified date
- Single-click navigation, keyboard navigation, Backspace to go up
- Hidden file toggle (`Ctrl+H`)
- Quick-jump to any path with `:` (opens a path input bar)
- Pane history navigation (`Alt+Left`)
- Pane refresh (`Ctrl+R`)

### File operations (all with confirmation dialog)
- **F3** View — opens a file viewer
- **F4** Edit — opens `$EDITOR`, saves in place
- **F5** Copy — to the other pane
- **F6** Move — to the other pane
- **F7** MkDir — create a new directory
- **F8** Delete — files or directories (recursive with warning)
- **^N** New Archive — create an empty `.tar.gz`, `.zip`, etc. in the current pane
- **Space** — toggle-select a file and advance the cursor; all subsequent F5/F6/F8 operations apply to the full selection
- **^Q** Quit

### Context menu
- **Backtick** `` ` `` or **right-click** opens a context menu
- Menu adapts per item type: file, directory, or archive
- Right-clicking empty directory background shows: New Archive, Take Snapshot, System Snapshot (from /), Build Archive from Diff

### SSH / SFTP filesystem
- `Ctrl+O` opens the connection dialog
- Reads `~/.ssh/config` automatically — HostName, User, Port, IdentityFile, ProxyJump all respected
- **Saved connections** — check "Save this connection" when entering manually; saved to `~/.config/porter/hosts.yaml` and shown in the connection dialog on every future open
- All file operations work over SFTP: view, edit, copy, move, delete
- Cross-filesystem transfers fully routed:
  - Local ↔ Local
  - Local ↔ SFTP
  - Local ↔ Archive
  - SFTP ↔ SFTP (same server: server-side `cp`/`mv`; different servers: via temp)
  - SFTP ↔ Archive
  - Archive ↔ Archive

### Archive virtual filesystem
- `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.tar`, `.zip` open as browsable virtual filesystems
- Inside an archive: navigate directories, view files, edit files (repack on save), copy in, copy out, delete, rename, mkdir, verify integrity
- Pressing `..` at the archive root exits back to the real filesystem
- Archive ↔ Archive transfers extract to temp and repack transparently

### Snapshot and deployment package builder
- **Take Snapshot** — records every file's mtime, size, mode, uid, and gid under the current directory
- **System Snapshot (from /)** — indexes the entire filesystem from `/` in a background thread; configurable exclusion list (virtual fs, logs, caches, build artifacts); UI stays responsive during the walk
- **Build Archive from Diff** — detects NEW and MOD files (content, permissions, or ownership changes) since either type of snapshot, builds a deployment archive
- Archives are stored with **absolute paths from `/`** — extract with `sudo tar -xzf pkg.tar.gz -C /` to place files in the correct locations on the target
- Every diff archive includes a `manifest.yaml` — see [Snapshot and Deployment Package Builder](#snapshot-and-deployment-package-builder) for full details

### Installer and launcher
- `install.sh` — full installer that checks Python version, installs system packages via `apt`/`dnf`/`pacman`, creates the venv, installs all Python dependencies, and symlinks `porter` into `/usr/local/bin` (prompts for sudo if needed)
- `porter.sh` — run script that activates the venv, launches porter, and deactivates cleanly on exit; symlink-safe (uses `readlink -f` to find the real venv path)

---

## Setup Guide

### Requirements

- Python 3.11 or newer
- A terminal emulator with 256-color support (xterm-256color; most modern terminals qualify)
- SSH key authentication configured for any remote hosts you plan to connect to

### Install with the installer (recommended)

```bash
git clone https://github.com/Jerry-Lees/porter.git
cd porter
./install.sh
```

The installer will:
1. Confirm Python 3.11+ is available
2. Install system packages (`python3-venv`, `openssh-client`, `rsync`) via your distro's package manager
3. Create a `.venv` virtual environment
4. Install porter and all Python dependencies (`textual`, `paramiko`, `PyYAML`)
5. Write a `porter.sh` launcher and offer to symlink it to `/usr/local/bin/porter`

If it can't write to `/usr/local/bin` without elevated privileges, it will ask whether to retry with `sudo`. If you decline, it prints the `export PATH=...` line to add to your shell profile.

### Install manually

```bash
git clone https://github.com/Jerry-Lees/porter.git
cd porter
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run

```bash
# Via the launcher (handles venv automatically)
./porter.sh

# Or if /usr/local/bin is in PATH after running install.sh
porter

# Or directly inside the venv
python -m porter
```

### SSH Setup

Porter reads `~/.ssh/config` and uses your existing SSH keys. No extra configuration needed if your hosts are already defined there. Example:

```
Host proxmox02
    HostName 172.16.10.5
    User root
    IdentityFile ~/.ssh/id_ed25519

Host pihole
    HostName pihole.example.com
    User admin
    ProxyJump bastion
```

Connect to any configured host with `Ctrl+O`. Hosts from `~/.ssh/config` appear in the list automatically. Connections entered manually can be saved to `~/.config/porter/hosts.yaml` for future use.

---

## Keyboard Shortcuts

### Navigation

| Key | Action |
|---|---|
| Tab | Switch active pane |
| Enter / click | Open directory or activate file |
| Backspace | Go up one directory |
| `:` | Quick-jump to any path |
| Alt+Left | Navigate back in pane history |
| Ctrl+H | Toggle hidden (dot) files |
| Ctrl+R | Refresh current pane listing |

### File Operations

| Key | Action |
|---|---|
| F3 | View file |
| F4 | Edit file in `$EDITOR` |
| F5 | Copy to other pane |
| F6 | Move to other pane |
| F7 | Create directory |
| F8 | Delete selected file(s) or directory |
| Space | Toggle-select current file, advance cursor |
| ^N | Create new empty archive |
| ^Q | Quit |

### Connection

| Key | Action |
|---|---|
| Ctrl+O | Open SSH connection dialog |

### Context Menu

| Key | Action |
|---|---|
| Backtick `` ` `` | Open context menu at cursor position |
| Right-click | Open context menu at mouse position |

> **Note on modifier keys:** `Ctrl` and `Alt` are fully supported in terminal applications. The `Super` / `Windows` / `Cmd` key is captured by the OS or window manager before it reaches the terminal and is not used.

---

## Archive Virtual Filesystem

Archives (`.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.zip`) open as virtual filesystems directly in a pane. Once mounted, the experience is identical to browsing a live directory.

### What you can do inside an archive

| Operation | How |
|---|---|
| Browse directories | Navigate normally |
| View a file | F3 or context menu |
| Edit a file | F4 — extracts to temp, opens `$EDITOR`, repacks on save |
| Copy files out | F5 — copies to the other pane (local or SFTP) |
| Copy files in | F5 from the other pane — adds to the archive |
| Delete a member | F8 |
| Rename a member | Context menu → Rename |
| Create a directory | F7 |
| Verify integrity | Context menu → Verify Integrity |
| Exit the archive | Navigate to `..` at the root level |

### Create a new empty archive

Press `^N` or right-click the directory background → **New Archive…**. Type a name including the desired extension (`.tar.gz`, `.tar.bz2`, `.tar.xz`, `.zip`). The archive is created immediately in the current pane and you can start copying files into it.

### Archive format support

| Format | Browse | Modify |
|---|---|---|
| `.tar.gz` / `.tgz` | ✓ | ✓ |
| `.tar.bz2` | ✓ | ✓ |
| `.tar.xz` | ✓ | ✓ |
| `.tar` | ✓ | ✓ |
| `.zip` | ✓ | ✓ |

Modifying compressed tar archives (`.tar.gz`, `.tar.bz2`, `.tar.xz`) requires a full repack — porter handles this transparently via a temp file. Plain `.tar` and `.zip` support true append mode.

---

## SSH Connection Manager

Press `Ctrl+O` to open the connection dialog. It shows three sections:

**Known hosts (`~/.ssh/config`)** — parsed automatically. `Host`, `HostName`, `User`, `Port`, `IdentityFile`, and `ProxyJump` are all respected. Select a host and press Enter (or double-click) to connect immediately.

**Saved connections** — hosts you have previously saved from within porter. Stored in `~/.config/porter/hosts.yaml`. Same one-click connect behavior.

**Manual entry** — type `user@host` or `user@host:port`. Check **Save this connection** before clicking Connect to persist it to the saved connections list for future sessions.

---

## Snapshot and Deployment Package Builder

This feature is designed for building "finish setup" packages — archives that, when extracted onto a new system, drop config files, scripts, and other assets into their correct locations and document everything needed to reproduce the source system's state.

There are two snapshot modes depending on how much of the system you changed:

### Directory snapshot (targeted)

Use this when you know changes were confined to a specific subtree (e.g., you only touched `/etc/nginx`).

1. Navigate to the directory you want to watch in the active pane.
2. Right-click the directory background → **Take Snapshot**. Porter records the mtime, size, permissions (mode), uid, and gid of every file under that directory recursively.
3. Make your changes.
4. Right-click the background → **Build Archive from Diff**. Porter compares the current state against the snapshot and shows every file that is **NEW** or **MOD** (changed content, permissions, or ownership).
5. Name the archive. It is created in the **other pane's current directory**.

### System snapshot (whole machine)

Use this when changes happened in multiple locations across the filesystem and you don't want to miss anything.

1. Right-click the directory background → **System Snapshot (from /)**.
2. A dialog appears showing the default exclusion list. Review it, add any additional paths or directory names to skip, then click **Take Snapshot**.
3. Porter walks the entire filesystem from `/` in a **background thread** — the UI stays responsive. A notification fires when indexing is complete with the file count.
4. Make your changes anywhere on the system.
5. Right-click the background → **Build Archive from Diff** — same as the directory workflow from here.

#### Default exclusions

The following are excluded automatically to avoid capturing volatile or virtual filesystem content:

| Type | Excluded |
|---|---|
| Virtual filesystems | `/proc` `/sys` `/dev` `/run` `/var/run` |
| Ephemeral directories | `/tmp` `/var/tmp` |
| Log and cache | `/var/log` `/var/cache` |
| External mounts | `/mnt` `/media` `/snap` |
| Build artifacts (by name) | `.git` `__pycache__` `node_modules` `.venv` `.cache` |

You can add additional exclusions in the dialog before taking the snapshot. Full paths (starting with `/`) exclude that entire subtree. Plain names (no `/`) exclude any directory with that name anywhere in the tree.

### Archive structure

Files are stored with their **absolute paths from `/`**. A file at `/etc/nginx/nginx.conf` is stored in the archive as `etc/nginx/nginx.conf`. To extract correctly on the target system:

```bash
sudo tar -xzf mypackage.tar.gz -C /
```

### manifest.yaml

Every diff archive includes a `manifest.yaml` at the archive root. It contains:

| Section | Contents |
|---|---|
| `porter_manifest` | Version, creation timestamp, hostname, source base directory, file count |
| `os` | Pretty name, distro ID, version, kernel version, architecture |
| `extraction` | Exact extraction command, step-by-step notes |
| `local_users` | All non-system user accounts (uid 1000–60000) with uid, gid, home, shell |
| `systemd_services` | List of services that were active on the source system |
| `packages` | Full installed package list (name + version) via `dpkg`, `rpm`, or `pacman` |
| `files` | Per-file entry: absolute path, archive path, change status, mode (octal), owner, group, uid, gid, size, mtime, sha256 |

The manifest is the "read this first" document for whoever deploys the archive on the target system. It tells them exactly what packages to install, what users to create, what services to enable, and how to verify the extraction.

---

## Labinator Integration

Porter is the designated tool for building the `.tar.gz` deployment archives used by [labinator's](https://github.com/Jerry-Lees/HomeLab) app-profile deployment system.

### Workflow

1. Stand up a reference container and configure the application until it works correctly.
2. Open porter with the reference container on the left pane (via SFTP), a local directory on the right.
3. Take a snapshot of the reference container's working directory.
4. Use porter's file operations to collect the config files that make the app work (`/etc/pihole/`, `/opt/pihole/`, etc.) into the right pane.
5. Build Archive from Diff — or manually copy files into a new archive — to produce a deployment package.
6. Porter generates a `manifest.yaml` sidecar documenting permissions, ownership, installed packages, and active services.
7. Save the archive to `~/projects/HomeLab/labinator/app-templates/`.
8. Every future deployment via labinator: install packages → extract archive → enable services → running.

### Permissions and ownership

`tarfile` preserves mode bits (chmod), uid, and gid natively. The uid/gid caveat: numeric IDs must match on the destination system. In the labinator workflow, packages are installed before archive extraction so system users already exist with correct IDs. Custom users are documented in the manifest's `local_users` section.

---

## Troubleshooting

### "Porter venv not found" when running via symlink

Run `./install.sh` again — it regenerates `porter.sh` with a symlink-safe path resolver. If you moved the porter directory after installing, re-run the installer to update the symlink.

### The terminal looks garbled or colors are wrong

Make sure your terminal reports a color-capable terminal type:

```bash
echo $TERM
# Should be xterm-256color or similar
export TERM=xterm-256color
```

Some SSH sessions strip the TERM variable. Add it to your `~/.bashrc` or `~/.zshrc`.

### SSH connection fails with "Authentication failed"

- Confirm your SSH key is loaded: `ssh-add -l`
- Test the connection directly: `ssh user@host`
- Make sure the host is defined in `~/.ssh/config` with the correct `IdentityFile`
- Check that the key's public half is in `~/.ssh/authorized_keys` on the remote host

### SSH connection fails through a jump host

- Verify the bastion host itself is reachable: `ssh bastion`
- Confirm the `ProxyJump` directive in `~/.ssh/config` is correct
- Test the full chain manually: `ssh -J bastion target`

### "Permission denied" when browsing remote files

You are connecting as a user without read access to those paths. Connect as a user with appropriate access, or use `sudo` on the remote host to grant read permissions before connecting.

### File copy fails with a permissions error

- Check available disk space on the destination: `df -h`
- Verify the SFTP subsystem is enabled on the remote host (`Subsystem sftp /usr/lib/openssh/sftp-server` in `/etc/ssh/sshd_config`)
- Confirm you have write permission to the destination directory

### Archive opens but shows no files

- The archive may be empty — this is expected for a newly created archive
- Verify it is a valid archive: `file yourarchive.tar.gz`
- Right-click → **Verify Integrity** to test without extracting

### Porter won't start — missing dependencies

```bash
./install.sh
```

Or manually:

```bash
source .venv/bin/activate
pip install -e .
```

### F-keys don't respond

Some terminals (notably GNOME Terminal, certain SSH clients) intercept F-keys before they reach the application. Options:
- Disable terminal F-key shortcuts in your terminal's preferences
- Use the context menu (backtick `` ` `` or right-click) as an alternative for all file operations

---

## Standing on Good Shoulders

Porter would not exist without the trail blazed by **Midnight Commander** (`mc`), written by **Miguel de Icaza** in 1994 and still going strong.

`mc` defined what a terminal file manager should be: two panes, F-key operations, a bottom bar that tells you what every key does, and zero ceremony between you and your files. It set the standard that every tool in this space has measured itself against for thirty years. The F-key bar at the bottom, the dual-pane layout, the navigation model — none of that is accidental.

Porter is not a fork of `mc` and shares no code with it — it's built from scratch in Python with Textual. But the design language, the workflow, the keybindings, the general philosophy that *a file manager should stay out of your way and let you work* — all of that comes directly from what Miguel built.

Midnight Commander is released under the **GNU General Public License v3**. Porter is a spiritual successor, not a derivative work — but we acknowledge the lineage openly and with gratitude.

Thank you, Miguel.

> *Midnight Commander: https://midnight-commander.org*
> *GPL v3: https://www.gnu.org/licenses/gpl-3.0.html*

---

*Porter is part of the [Jerry-Lees homelab](https://github.com/Jerry-Lees) toolchain. It pairs with [labinator](https://github.com/Jerry-Lees/HomeLab) for automated provisioning of Proxmox LXC containers and VMs.*

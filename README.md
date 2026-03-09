# Porter

> *A porter carries your luggage between places, packs it up for the journey, and makes sure it arrives intact. This tool does the same — for server config files.*

**Porter** is a dual-pane terminal file manager built for homelabs and sysadmins. It works natively over SSH/SFTP between any two hosts, treats archives as virtual filesystems you can browse and build into, and integrates tightly with [labinator](https://github.com/Jerry-Lees/HomeLab) for provisioning deployment archives onto Proxmox LXC containers and VMs.

Born from the same frustration that created Midnight Commander thirty years ago: moving files between servers is tedious, dangerous when done wrong, and deserves better tooling.

---

## Table of Contents

- [About Porter](#about-porter)
- [Features](#features)
- [Setup Guide](#setup-guide)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Archive Virtual Filesystem](#archive-virtual-filesystem)
- [Labinator Integration](#labinator-integration)
- [Troubleshooting](#troubleshooting)
- [Standing on Good Shoulders](#standing-on-good-shoulders)

---

## About Porter

In the age of steam trains and ocean liners, a porter was the person at the station or dock who took your bags, loaded them onto the right conveyance, and made sure they arrived where they were supposed to go — packed correctly, nothing lost. That's exactly what this tool does for your server config files.

Porter picks up your configs from a live server, packs them into a deployment archive with permissions and ownership intact, and delivers them ready for extraction onto a freshly provisioned container or VM. It works equally well as a general-purpose SSH file manager: browse remote filesystems, copy files between hosts, edit configs in place over SFTP, and manage your homelab infrastructure without ever leaving the terminal.

Two panes. Any combination of local filesystem, remote SSH host, or archive. Everything in one view.

---

## Features

### Dual-Pane SSH/SFTP File Browser

| Pane type | Description |
|---|---|
| Local filesystem | The machine porter is running on |
| Remote host (SSH/SFTP) | Any host reachable via SSH key authentication |
| NFS mount | Locally-mounted NFS share — treated as local |
| Archive (.tar.gz / .zip) | Browse or build an archive as a virtual filesystem |

- Both panes are independently navigable — Tab switches the active pane
- Full file listing: name, permissions, owner, group, size, modified date
- Toggle hidden (dot) files per pane with `Ctrl+H`
- Navigate history per pane with `Alt+Left` / `Alt+Right`
- Quick-jump to any path with `:` (tab completion supported)
- Bookmark frequently used paths with `Ctrl+D`

### SSH Connection Manager

- Reads `~/.ssh/config` automatically — `Host` blocks with `IdentityFile`, `ProxyJump`, `Port`, and `User` are all respected
- ProxyJump / bastion hosts work transparently
- Non-standard ports inline: `myserver.example.com:2222`
- Open a connection with `Ctrl+O`

### File Operations

| Operation | Key | Notes |
|---|---|---|
| View file | F3 | Syntax-highlighted viewer for config files |
| Edit file | F4 | Opens `$EDITOR`, uploads on save |
| Copy to other pane | F5 | Confirmation dialog with overwrite warning |
| Move to other pane | F6 | — |
| Create directory | F7 | Also creates new archives |
| Delete | F8 | Confirmation required; recursive for directories |
| Quit | F10 | — |

### Context Menu

Right-click any file or directory for a full action menu. Keyboard users can press backtick `` ` `` to open the menu at the cursor position.

Context menu adapts based on what is highlighted — files, directories, and archives each show relevant actions. Archive files show **Open Archive**, **Verify Integrity**, and **Extract to other pane**.

### Archive Virtual Filesystem

Archives open as browsable virtual filesystems. The F-key bar updates dynamically when an archive is highlighted to signal available actions. See [Archive Virtual Filesystem](#archive-virtual-filesystem) below.

### Transfers

- Transfer progress bar with per-file and total speed, ETA, and bytes transferred
- rsync backend for large live-to-live transfers (falls back to SFTP if unavailable)
- Transfer queue panel — retry failed transfers individually or all at once
- Resume interrupted SFTP transfers on reconnect
- Optional bandwidth limiting per transfer or globally

### Permissions and Ownership

All transfers preserve chmod bits and uid/gid:

- `tarfile` preserves mode, uid, and gid natively for archive operations
- SFTP `stat` / `chmod` / `chown` for remote-to-remote transfers
- The uid/gid caveat: numeric IDs must match on the destination system. In the labinator workflow, packages are installed before archive extraction so system users already exist with correct IDs. Custom users are documented in the `labinator-manifest.yaml` sidecar.

---

## Setup Guide

### Requirements

- Python 3.11 or newer
- A terminal emulator with 256-color support (xterm-256color, most modern terminals qualify)
- SSH key authentication configured for any remote hosts you plan to connect to

### Install

Clone the repo and install into a virtual environment:

```bash
git clone https://github.com/Jerry-Lees/porter.git
cd porter
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run

```bash
# From inside the venv
porter

# Or directly
python -m porter
```

### SSH Setup

Porter reads `~/.ssh/config` and uses your existing SSH keys. No extra configuration needed if your hosts are already defined in SSH config. Example SSH config block:

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

Connect to any configured host with `Ctrl+O`.

### Config File

Porter stores its own config at `~/.config/porter/config.yaml`. It is created automatically on first run. Options include:

```yaml
labinator_path: ~/projects/HomeLab/labinator   # path to your labinator repo
show_hidden: false                              # default hidden file visibility
bandwidth_limit: 0                             # transfer cap in KB/s (0 = unlimited)
```

Bookmarks are stored separately in `~/.config/porter/bookmarks.yaml`.

---

## Keyboard Shortcuts

### Navigation

| Key | Action |
|---|---|
| Tab | Switch active pane |
| Enter | Open directory / view file |
| `:` | Open quick-jump path bar |
| Alt+Left | Navigate back in pane history |
| Alt+Right | Navigate forward in pane history |
| Ctrl+H | Toggle hidden (dot) files |
| Ctrl+R | Refresh current pane |

### File Operations

| Key | Action |
|---|---|
| F3 | View file (syntax highlighted) |
| F4 | Edit file in `$EDITOR` |
| F5 | Copy to other pane |
| F6 | Move to other pane |
| F7 | Create directory |
| F8 | Delete selected |
| F10 | Quit |

### Selection

| Key | Action |
|---|---|
| Space / Ins | Toggle select current file, move down |
| Ctrl+A | Select all |
| Ctrl+I | Invert selection |
| Shift+Arrow | Extend selection |

### Connection & Session

| Key | Action |
|---|---|
| Ctrl+O | Open connection dialog |
| Ctrl+T | New tab |
| Ctrl+W | Close current tab |
| Ctrl+D | Bookmark current path |

### Context Menu

| Key | Action |
|---|---|
| Backtick `` ` `` | Open context menu at cursor |
| Right-click | Open context menu at mouse position |

> **Note on modifier keys:** `Ctrl` and `Alt` are fully supported in terminal applications. The `Super` / `Windows` / `Cmd` key is captured by the OS or window manager before it reaches the terminal and is not used.

---

## Archive Virtual Filesystem

Archives (`.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.zip`) are treated as virtual filesystems. When the cursor highlights an archive file, the F-key bar updates to indicate available archive actions — the label changes color and text so it is impossible to miss.

Pressing the highlighted key mounts the archive in that pane. Navigation from that point is identical to a live filesystem.

### Modes

**Browse** — open an existing archive and navigate its contents. Copy files out to the other pane.

**Build** — start with an empty archive (`F7 New Archive`, prompts for name and format). Copy files in from the other pane. The archive grows as files are added. Save when done.

**Edit** — open an existing archive, add or remove files, save back. The original is preserved until you explicitly save.

### Archive Format Support

| Format | Read | Write |
|---|---|---|
| `.tar.gz` / `.tgz` | ✓ | ✓ |
| `.tar.bz2` | ✓ | ✓ |
| `.tar.xz` | ✓ | ✓ |
| `.zip` | ✓ | ✓ |

When creating a new archive, a format picker and compression level selector (Fast / Balanced / Maximum) are shown.

Archive-to-archive transfers are fully supported. Porter extracts to a temp location and repacks transparently — it just works.

### Archive Integrity Verification

Right-click an archive and choose **Verify Integrity** to test the archive without extracting. A pass/fail result is shown with details on any corrupted members.

---

## Labinator Integration

Porter is the designated tool for building the `.tar.gz` deployment archives used by [labinator's](https://github.com/Jerry-Lees/HomeLab) app-profile deployment system.

### Workflow

1. Stand up a reference container and configure the application until it works correctly.
2. Open porter with the reference container on the left pane, a new archive on the right.
3. Browse the reference container's filesystem and select the config files that make the app work (`/etc/pihole/`, `/opt/pihole/`, etc.).
4. Copy them into the archive — porter preserves full paths, permissions, and ownership.
5. Porter generates a `labinator-manifest.yaml` sidecar for any custom users/groups and pre/post-extract commands.
6. Save the archive to `~/projects/HomeLab/labinator/app-templates/pihole.tar.gz`.
7. Every future deployment via labinator: install packages → extract archive → reboot → running.

### Archive Storage Layout

```
labinator/
└── app-templates/
    ├── pihole.tar.gz
    ├── pihole-manifest.yaml
    ├── nginx-proxy-manager.tar.gz
    ├── nginx-proxy-manager-manifest.yaml
    └── vaultwarden.tar.gz
```

### Labinator Builder Mode

`F11` switches the archive pane into labinator builder mode:
- The manifest being built is shown alongside the file tree
- Files already included in the archive are highlighted in the source pane
- A summary panel shows archive name, package profile association, custom users, and post-extract commands

---

## Troubleshooting

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

You are connecting as a user without read access to those paths. Options:
- Connect as root if your SSH config allows it
- Enable sudo-aware browsing for the connection in `~/.config/porter/sessions.yaml` (`sudo: true`)

### File copy fails or stalls

- Check available disk space on the destination: `df -h`
- For remote transfers, verify the SFTP subsystem is enabled on the remote host (`Subsystem sftp /usr/lib/openssh/sftp-server` in `/etc/ssh/sshd_config`)
- Interrupted transfers can be retried from the transfer queue panel (`F12`)

### Archive opens but shows no files

- The archive may be empty, or the format may not be supported
- Verify the file is a valid archive: `file youarchive.tar.gz`
- Try verifying integrity via right-click → **Verify Integrity**

### Porter won't start — missing dependencies

```bash
source .venv/bin/activate
pip install -e .
```

If the venv does not exist yet, create it first:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### F-keys don't work in my terminal

Some terminals (notably GNOME Terminal, certain SSH clients) intercept F-keys before they reach the application. Try:
- Disabling terminal F-key shortcuts in your terminal's preferences
- Using the context menu (backtick `` ` `` or right-click) as an alternative to F-keys

---

## Standing on Good Shoulders

Porter would not exist without the trail blazed by **Midnight Commander** (`mc`), written by **Miguel de Icaza** in 1994 and still going strong.

`mc` defined what a terminal file manager should be: two panes, F-key operations, a bottom bar that tells you what every key does, and zero ceremony between you and your files. It set the standard that every tool in this space has measured itself against for thirty years. I used it constantly managing Linux servers before I ever thought about writing my own file manager, and the muscle memory is still there.

Porter is not a fork of `mc` and shares no code with it — it's built from scratch in Python with Textual. But the design language, the workflow, the keybindings, the general philosophy that *a file manager should stay out of your way and let you work* — all of that comes directly from what Miguel built. The F-key bar at the bottom, the dual-pane layout, the mc-style navigation: none of that is accidental.

Midnight Commander is released under the **GNU General Public License v3**. Porter is a spiritual successor, not a derivative work — but we acknowledge the lineage openly and with gratitude.

Thank you, Miguel.

> *Midnight Commander: https://midnight-commander.org*
> *GPL v3: https://www.gnu.org/licenses/gpl-3.0.html*

---

*Porter is part of the [Jerry-Lees homelab](https://github.com/Jerry-Lees) toolchain. It pairs with [labinator](https://github.com/Jerry-Lees/HomeLab) for automated provisioning of Proxmox LXC containers and VMs.*

# Porter — Feature Ideas

**Porter** is a dual-pane terminal file manager for homelabs and sysadmins. Named after the
person who carries your luggage between places and packs it up for you — porter does the
same for server config files. It works over SSH/SFTP between any two hosts, and can pack
selected files into a `.tar.gz` deployment archive instead of (or in addition to) a live
destination filesystem.

Porter stands on its own as a general-purpose tool, but is designed to integrate with
**labinator** — specifically for building the deployment archives that labinator extracts
onto newly provisioned LXC containers and VMs as part of app-profile deployments.

> **Inspired by Midnight Commander (`mc`) by Miguel de Icaza (1994).** If `mc` is the
> classic, porter is the homelab-native evolution: SSH-native, archive-aware, and built
> for the way sysadmins actually work today. mc is GPL v3 — we stand on good shoulders.

---

## Table of Contents

- [Dual-Pane SSH/SFTP File Browser](#dual-pane-sshsftp-file-browser)
- [Virtual Filesystem — Archives as Directories](#virtual-filesystem--archives-as-directories)
- [Context Menu (Right-Click + Keyboard)](#context-menu-right-click--keyboard)
- [File Selection and Batch Operations](#file-selection-and-batch-operations)
- [Navigation and UX](#navigation-and-ux)
- [File Operations](#file-operations)
- [Transfers](#transfers)
- [Archive Features](#archive-features)
- [Connection Manager](#connection-manager)
- [Permissions and Ownership](#permissions-and-ownership)
- [Labinator Integration](#labinator-integration)

---

## Dual-Pane SSH/SFTP File Browser

The core of porter: two side-by-side panes, each showing a filesystem. Navigate, select,
and transfer files between any combination of local and remote hosts, or archives.

### Pane types

| Pane type | Description |
|---|---|
| Local filesystem | The machine porter is running on |
| Remote host (SSH/SFTP) | Any host reachable via SSH key auth |
| NFS mount | Locally-mounted NFS share — treated as local |
| tar.gz / zip archive | Browse or build an archive as a virtual filesystem |

### Layout

```
┌──────────────────────────────────┬──────────────────────────────────┐
│ [L] root@proxmox02:/etc          │ [R] pihole.tar.gz                │
├──────────────────────────────────┼──────────────────────────────────┤
│ ..                               │ ..                               │
│ nginx/              drwxr-xr-x   │ etc/                             │
│   nginx.conf        -rw-r--r--   │   nginx/                         │
│   sites-enabled/    drwxr-xr-x   │     nginx.conf                   │
│   sites-available/  drwxr-xr-x   │ opt/                             │
│ ssh/                drwxr-xr-x   │   myapp/                         │
│   sshd_config       -rw-------   │     config.yaml                  │
│ cron.d/             drwxr-xr-x   │                                  │
├──────────────────────────────────┴──────────────────────────────────┤
│ F3 View  F4 Edit  F5 Copy  F6 Move  F7 MkDir  F8 Del  F10 Quit     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key bindings (mc-style)

| Key | Action |
|---|---|
| Tab | Switch active pane |
| Enter | Open directory / view file |
| F3 | View file contents (with syntax highlighting for config files) |
| F4 | Edit file (download to temp, open `$EDITOR`, upload on save) |
| F5 | Copy selected file(s) to other pane |
| F6 | Move selected file(s) to other pane |
| F7 | Create directory (or new archive — see below) |
| F8 | Delete selected file(s) |
| F9 | Sync panes (rsync-style preview + execute) |
| F10 | Quit |
| Space | Select/deselect file and move down |
| Ins | Select/deselect file and move down |
| Ctrl+A | Select all |
| Ctrl+H | Toggle hidden (dot) files |
| Ctrl+R | Refresh pane |
| Ctrl+T | New tab |
| Ctrl+W | Close tab |
| Ctrl+D | Bookmark current path |
| Alt+Left | Navigate back in pane history |
| Alt+Right | Navigate forward in pane history |
| `:` | Open quick jump bar with tab completion |

### Implementation notes

- Built with **Textual** (Textualize) for the TUI — modern, actively maintained, Python-native,
  full mouse support including right-click.
- SSH/SFTP via **paramiko** (already a labinator dependency — reuse it).
- Each pane is independently navigable; the active pane is highlighted.
- File listing columns: name, permissions, owner, group, size, modified date.
- Transfers show a rich progress bar with per-file and total speed, ETA, and bytes transferred.

---

## Virtual Filesystem — Archives as Directories

Archives (`.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz`, `.zip`) are treated as virtual
filesystems. When the cursor highlights an archive file, the F-key bar changes dynamically
— the relevant key changes color and label to signal a new action is available:

```
 Normal file selected:
 F3 View  F4 Edit  F5 Copy  F6 Move  F7 MkDir  F8 Del  F10 Quit

 Archive file selected (F6 changes):
 F3 View  F4 Edit  F5 Copy  F6 Open Archive  F7 MkDir  F8 Del  F10 Quit
```

The highlighted key is rendered in bold with a distinct color so it's impossible to miss.
Pressing it mounts the archive as a virtual filesystem in that pane — navigation from that
point is identical to a live filesystem.

### Archive modes

**Browse mode** — open an existing archive and navigate its contents. Copy files out to
the other pane for inspection or editing.

**Build mode** — start with an empty archive (`F7 New Archive`, prompts for name and
format), copy files into it from the other pane. The archive grows as files are added.
Save to disk when done.

**Edit mode** — open an existing archive, add or remove files, save back. The original
is preserved until you explicitly save.

### Archive → Archive transfers

Transferring between two archive panes (`tar.gz → tar.gz`) is fully supported. Porter
extracts to a temp location and re-packs transparently. Slower than live-to-live transfers
but completely invisible to the user — it just works.

### Archive format support

| Format | Read | Write | Notes |
|---|---|---|---|
| `.tar.gz` / `.tgz` | ✓ | ✓ | Primary format for labinator archives |
| `.tar.bz2` | ✓ | ✓ | Better compression, slower |
| `.tar.xz` | ✓ | ✓ | Best compression, slowest |
| `.zip` | ✓ | ✓ | Useful for Windows-bound archives |

When creating a new archive, a format picker is shown. Compression level is selectable:
Fast / Balanced / Maximum.

### Implementation notes

- Python's stdlib `tarfile` and `zipfile` modules — no extra dependencies.
- Archive pane shows file listing with full paths, permissions, owner (name if resolvable,
  uid/gid as fallback), and size — identical to a live pane.
- Archive is written atomically (temp file + rename) on save to prevent corruption.
- `F9 Verify` tests archive integrity without extracting (`tar --test` / `zip -T`).

---

## Context Menu (Right-Click + Keyboard)

A flyout context menu appears at the cursor position for the highlighted file, directory,
or current selection. Provides quick access to all available actions without remembering
F-key bindings.

### Triggers

| Trigger | Notes |
|---|---|
| **Right-click** | Opens at mouse position — works everywhere Textual runs |
| **Backtick `` ` ``** | Keyboard shortcut — opens at cursor position for keyboard-only users |

> **Note on modifier keys:** `Ctrl` and `Alt/Meta` are fully supported in terminal
> applications. The `Super` / `Windows` / `Cmd` key is **not** reliably available —
> it is captured by the OS or window manager before reaching the terminal. Porter does
> not depend on it.

### Context menu contents (adapt based on selection)

```
┌─────────────────────────┐
│ nginx.conf              │
├─────────────────────────┤
│ View                    │
│ Edit                    │
│ Copy to other pane →    │
│ Move to other pane →    │
│ Add to archive          │
│ ─────────────────────── │
│ Rename                  │
│ Delete                  │
│ ─────────────────────── │
│ Properties              │
│ Checksum                │
└─────────────────────────┘
```

For a **directory**:
```
│ Open                    │
│ Copy to other pane →    │
│ Sync to other pane →    │
│ Compare with other pane │
│ Add to archive          │
│ Calculate size          │
```

For an **archive file** (before opening):
```
│ Open Archive            │
│ Verify Integrity        │
│ Extract to other pane   │
│ View Manifest           │  ← if labinator-manifest.yaml sidecar exists
```

---

## File Selection and Batch Operations

Files can be selected individually or in groups across the current pane, then operated
on as a batch.

### Selection methods

| Method | Action |
|---|---|
| Space / Ins | Toggle select on current file, move down |
| Ctrl+A | Select all visible files |
| Ctrl+I | Invert selection |
| Pattern select | Type `*` or a glob pattern to select matching files |
| Range select | Shift+Arrow to extend selection |

Selected files are highlighted distinctly (bold, different color). A count and total size
of the selection is shown in the status bar.

### Batch operations

All F-key operations (Copy, Move, Delete, Archive, Checksum) operate on the full selection
when files are selected. A confirmation summary is shown before destructive operations:

```
Delete 7 files (142 KB) from root@proxmox02:/etc/nginx/?
  [Y]es   [N]o   [S]how list
```

---

## Navigation and UX

### Tabs

`Ctrl+T` opens a new tab, each with its own independent pair of panes and connection state.
`Ctrl+W` closes the current tab. Tab bar is shown at the top when more than one tab is open.
Work on multiple host pairs simultaneously without losing context.

### Pane history

Each pane maintains its own navigation history. `Alt+Left` goes back, `Alt+Right` goes
forward — exactly like a browser. History is per-pane and per-tab, not shared.

### Quick jump bar

Press `:` to open a path bar at the bottom of the active pane. Supports tab completion
for local and remote paths. Type a full path and press Enter to jump directly. Press Esc
to cancel.

### Bookmarks

`Ctrl+D` bookmarks the current pane's path with an optional label. Bookmarks are shown
in the connection picker on startup and accessible via a bookmark menu. Stored in
`~/.config/porter/bookmarks.yaml`.

### Hidden files

`Ctrl+H` toggles dotfiles (files starting with `.`) on or off for the current pane.
Off by default. State is remembered per session.

### Directory size

`Ctrl+Space` calculates the total size of the highlighted directory (recursive), displayed
in the file listing in place of the directory entry size. Same behavior as mc.

---

## File Operations

### In-place remote edit

`F4` on any file (local, remote, or inside an archive) downloads it to a secure temp
location, opens it in `$EDITOR` (respects the environment variable), and uploads it back
on save and exit. Works transparently for any pane type.

### Directory diff

`F9 Compare` highlights differences between the two panes' current directories:
- Files that exist in one pane but not the other (shown in yellow)
- Files that exist in both but differ in size or modification time (shown in blue)
- Identical files (no highlight)

Selecting a diff entry and pressing F5 copies the source version to the destination.
Essential for "is this archive complete?" and "is this server up to date?"

### Sync mode

`F9 Sync` makes the destination pane match the source pane (one-way). Shows a preview
of what would be added, updated, and deleted before executing. Uses rsync when both sides
support it, falls back to SFTP diff + copy otherwise.

### Batch rename

Select multiple files, press `Ctrl+R` to open the batch rename dialog. Supports:
- Simple find/replace in filename
- Regex substitution
- Sequential numbering (`server-{n}.conf`)
- Case conversion (upper/lower/title)

### Checksum verification

After a copy, porter optionally verifies MD5 or SHA256 checksums between source and
destination. Enabled per-transfer or globally in config. Essential for archive transfers
where silent corruption would be catastrophic.

---

## Transfers

### Transfer queue

All copy/move operations go into a transfer queue panel (toggled with `F12`). Operations
run immediately by default, or can be queued for batch execution. The queue panel shows:
- Each pending/active/completed transfer
- Per-file speed and ETA
- Total progress
- Retry button for failed transfers

Failed transfers can be retried individually or all at once.

### Transfer resume

If an SFTP transfer is interrupted (network drop, timeout), porter detects the partial
file on the destination and offers to resume from where it left off on reconnect.

### rsync backend

For large directory transfers between live hosts where rsync is available on both sides,
porter uses rsync over SSH instead of SFTP. Delta transfers only send changed blocks —
dramatically faster for large files with small changes. Falls back to SFTP automatically
if rsync is unavailable on either end.

### Bandwidth limiting

Optional bandwidth cap per transfer or globally, configured in
`~/.config/porter/config.yaml`. Useful on shared or metered links.

---

## Archive Features

### Manifest viewer

When a `labinator-manifest.yaml` sidecar file is present alongside an archive, `F3 View`
on the archive shows the manifest contents in a split view alongside the file listing —
custom users, groups, and pre/post-extract commands at a glance.

### Archive integrity verification

`F9 Verify` (or context menu → Verify Integrity) tests the archive without extracting:
- `tar --test` for tar formats
- `zip -T` for zip
- Prints a pass/fail result with details on any corrupted members

### Compression level picker

When creating a new archive, a format and compression level picker is shown:

```
Archive format:    [ tar.gz ]  tar.bz2  tar.xz  zip
Compression:       Fast  [ Balanced ]  Maximum
```

---

## Connection Manager

### SSH config aware

Porter reads `~/.ssh/config` automatically. Host blocks with `IdentityFile`, `ProxyJump`,
`Port`, and `User` directives are all respected. Connecting to a host defined in SSH config
just works — no re-entering credentials.

### Jump host / bastion support

ProxyJump is supported transparently. If a host in `~/.ssh/config` specifies
`ProxyJump bastion.example.com`, porter tunnels through it without any extra configuration.

### Non-standard ports

Specify ports inline in the connection prompt: `myserver.example.com:2222`.

### Saved sessions

Named connection pairs that open both panes simultaneously. Examples:
- `lab-pihole` — left: controller machine, right: pihole.lees-family.io
- `archive-builder` — left: reference-server, right: pihole.tar.gz

Saved to `~/.config/porter/sessions.yaml`. Available in the startup picker and as
command-line arguments: `./porter --session archive-builder`.

### Recent connections

The startup picker shows recently used connections alongside saved sessions and SSH config
hosts. Most recently used is listed first.

### Sudo-aware remote browsing

For root-owned files on remote hosts where you connect as a non-root user, porter can
optionally prefix remote commands with `sudo`. Enabled per-connection in session config.

---

## Permissions and Ownership

Permissions (chmod bits) and ownership (uid/gid) are displayed in the file listing and
fully preserved on all transfers:

- **Local → Local:** standard file copy with `shutil.copy2` + `os.chown`
- **Local/Remote → Archive:** `tarfile` preserves mode, uid, gid natively
- **Archive → Local/Remote:** extracted with original permissions and ownership intact
- **Remote → Remote:** permissions read via SFTP `stat`, applied via SFTP `chmod`/`chown`

**The uid/gid caveat:** numeric IDs must mean the same thing on the destination. In the
labinator workflow, packages are installed before archive extraction, so system users
already exist with the correct IDs. For custom users, the porter-generated
`labinator-manifest.yaml` sidecar documents them so labinator can create them before
extracting.

---

## Labinator Integration

Porter is the designated tool for building the `.tar.gz` deployment archives used by
labinator's app-profile deployment system. The intended workflow:

1. Stand up a reference container (manually or via a community script) and configure
   the application until it works correctly.
2. Open porter with the reference container on the left, a new archive on the right.
3. Browse the reference container's filesystem, select config files that make the app
   work (`/etc/pihole/`, `/opt/pihole/`, `/var/lib/pihole/`, etc.).
4. Copy them into the archive — porter preserves full paths, permissions, and ownership.
5. Porter generates the sidecar `labinator-manifest.yaml` for any custom users/groups
   and any pre/post-extract commands needed.
6. Save the archive to `~/projects/HomeLab/labinator/app-templates/pihole.tar.gz`.
7. Every future Pi-hole deployment via labinator: install packages → extract archive →
   reboot → running.

### Labinator mode

`F11` switches the archive pane into labinator builder mode:
- The manifest being built is shown alongside the file tree
- Files already included in the archive are highlighted in the source pane
- A summary panel shows: archive name, package profile association, custom users,
  post-extract commands

### Profile browser

Pull up labinator's `config.yaml` package profiles and associate one with the archive
being built. The association is stored in the manifest so labinator knows which packages
to install before extracting.

### Save to app-templates shortcut

Porter detects the labinator project path (configurable in `~/.config/porter/config.yaml`)
and offers `Save to labinator app-templates/` as a named destination shortcut in the
save dialog.

### App-templates storage layout

```
labinator/
└── app-templates/
    ├── pihole.tar.gz
    ├── pihole-manifest.yaml
    ├── nginx-proxy-manager.tar.gz
    ├── nginx-proxy-manager-manifest.yaml
    └── vaultwarden.tar.gz
```

---

## Implementation Stack

| Component | Library | Notes |
|---|---|---|
| TUI framework | `textual` | Full mouse support, right-click events, modern Python |
| SSH/SFTP | `paramiko` | Already a labinator dependency |
| Archive handling | `tarfile`, `zipfile` | Python stdlib — no extra dependencies |
| rsync backend | `subprocess` + system `rsync` | Fallback to SFTP if unavailable |
| Config/sessions | `PyYAML` | Already a labinator dependency |

### Dependencies to add

```
textual
paramiko   # shared with labinator
PyYAML     # shared with labinator
```

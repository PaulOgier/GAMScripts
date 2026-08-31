# GAM7 Update (`gam-update.sh`)

A safety wrapper around GAM7's official installer. It downloads and runs
[`gam-install.sh`](https://raw.githubusercontent.com/GAM-team/GAM/master/src/gam-install.sh)
in upgrade mode. The upgrade itself is entirely upstream's work. What this adds
is a version check, a rollback copy and a verification pass around it.

**GAM7 only.** GAMADV-XTD3 is a separate project with its own installer and its
own install folder. Do not point this at one.

**Windows users want a different script.** This one is bash. For Windows there is
[NoSubstitute/gamupdate](https://github.com/NoSubstitute/gamupdate), Kim Nilsson's
`updategam7.ps1`, which detects the install location and CPU architecture and picks
the matching release asset.

macOS and Linux. Bash, curl and Python 3 (the installer needs all three anyway).

## Why

Running `gam-install.sh -l` directly works, and most of the time nothing goes
wrong. When something does, these are the gaps:

* It deletes `<install dir>/lib` and extracts the new release over the top.
  There is no backup. A download that dies halfway leaves you with no working
  `gam` and nothing to go back to.
* It has no idea whether you are already on the latest version, so re-running it
  re-downloads and reinstalls regardless.
* It reports what it did, but never checks that the version now on disk is the
  one you asked for.

## What it does

1. Reads the installed version, then the latest release tag from the GitHub API.
   If they match it prints `already current, nothing to do` and exits 0, so it is
   safe in a monthly cron job or a login script.
2. Copies the entire install to `<install dir>.bak-<old version>` before touching
   anything, and refuses to run if that path already exists.
3. Runs the official installer with `-l` (upgrade only, no project/auth prompts)
   and `-p false` (leave shell rc files alone, since an existing install already
   has the alias).
4. Re-reads the version and exits 1 if it is not the release that was expected.
5. Prints `gam info domain`, so which tenant your config is pointed at is on
   screen before you run anything against it. Upgrading cannot change that
   pointer, but if you administer more than one tenant you switch between them by
   pointing `config_dir` at a different folder, and nothing in gam's own output
   reminds you which one is loaded.

Your credentials are not touched at any point. The installer only writes inside
the target folder. `gam.cfg` (`~/.gam`) and the `config_dir` it points at, which
holds `client_secrets.json`, `oauth2.txt` and `oauth2service.json`, live
elsewhere.

## Usage

```bash
# Dry run: print installed vs latest, change nothing
./gam-update.sh -n

# Upgrade
./gam-update.sh

# Non-default install location
./gam-update.sh -d /opt/gam7
```

The default is `$HOME/bin/gam7`, which is where the official installer puts GAM
unless you passed it `-d` as well. If you installed somewhere else, pass the same
directory here with `-d`.

## Rollback

```bash
rm -rf ~/bin/gam7 && mv ~/bin/gam7.bak-7.47.00 ~/bin/gam7
```

Substitute your own path and version. The backup copies accumulate, so delete
the old ones once an upgrade has proved itself.

## Exit codes

`0` = upgraded, or already on the latest version. `1` = no gam binary at the
given path, GitHub unreachable or rate-limited, the backup path is already
occupied, or the version after the upgrade was not the one expected. `2` = bad
command-line arguments.

The GitHub API allows 60 unauthenticated requests per hour per IP. If you hit
that, the script prints the reason GitHub gave and stops.

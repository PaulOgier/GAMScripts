# GAM Script Checker

> ⚠️ **This tool is in testing.** It reads a GAM script and tells you what the script would do, but it can miss things. A READ-ONLY result means the checker found nothing that changes your tenant. It is not a promise that the script is safe. If you are unsure about a script, do not run it: ask someone who knows GAM, and test on a non-production domain first.

Reads a GAM script and tells you what it would do to your Google Workspace tenant and to your computer, before you run it. It never runs the script or gam.

## What the result means

Read the **VERDICT** line first. It is the worst thing the checker found anywhere in the script.

| Verdict | Meaning | What to do |
|---|---|---|
| READ-ONLY | Every command it found only reads | Fine to run |
| CHANGES | Creates, updates, suspends, moves or shares something | Read every CHANGES line before running |
| DESTRUCTIVE | Deletes, wipes, purges, trashes or removes something, or erases files on your computer | Stop. Be sure you want every DESTRUCTIVE line |
| CANNOT TELL | Something is only decided when the script runs, or no gam command was visible | Treat it as dangerous until someone checks it |
| SUSPICIOUS | Reads GAM's credential files and can send data out, or runs hidden or downloaded code | Do not run it |

Lines marked **SECURITY** weaken account protection or widen access (turning off 2-Step Verification, forwarding mail, adding delegates or admins, sharing files). They are listed whatever their level.

Where Google documents a way to undo something, the line carries an **UNDO** note, for example "an admin can restore a deleted user for 20 days", with the help page it came from. No UNDO line means Google documents no window, not that nothing can be recovered.

## Before you start

You need two things:

1. **The whole `GAM Script Checker` folder**, not just `gamcheck.py`. The checker reads the `verbs` folder next to it and will not work without it. You can ignore the `developers` folder: it holds the tests and the tools that rebuild `verbs`. To get it, open the [GAM Script Checker releases](https://github.com/PaulOgier/GAMScripts/releases?q=gam-script-checker&expanded=true), find the newest one, download the `.zip` file under **Assets** whose name starts with `gam-script-checker`, and unzip it:
   - **Mac:** double-click the zip (Safari may already have unzipped it).
   - **Windows:** right-click the zip and choose **Extract All**. Double-clicking only shows what is inside, and the checker cannot run from there.
   - **Linux:** right-click the zip and choose **Extract Here**.
2. **Python 3.9 or newer.** Nothing else to install.

There are two ways to use it:

- **Paste mode** checks a command or a few commands you copied from somewhere (a web page, a chat, an email).
- **File mode** checks a whole script saved as a file (`.sh`, `.ps1`, `.bat`, `.cmd`, `.py` or a gam batch `.txt`).

Use file mode for any script with blank lines in it: a blank line ends a paste.

## Mac

### Open Terminal in the checker folder

1. Press **Cmd+Space**, type `Terminal`, press **Enter**.
2. Type `cd` followed by a space. Do not press Enter yet.
3. Drag the `GAM Script Checker` folder from Finder into the Terminal window. Its location appears after `cd`.
4. Press **Enter**.

If you have never used Python on this Mac, the first command below may ask to install the developer tools. Click **Install**, wait for it to finish, then run the command again.

### Paste mode

1. Type `python3 gamcheck.py` and press **Enter**.
2. Paste the command with **Cmd+V**.
3. Press **Enter twice**. The report appears.

### File mode

1. Type `python3 gamcheck.py` followed by a space. Do not press Enter yet.
2. Drag the script file from Finder into the Terminal window.
3. Press **Enter**. The report appears.

## Windows

### Get Python

Open the Start menu, type `cmd`, open **Command Prompt**, type `py --version` and press **Enter**. If it prints `Python 3.9` or higher, you are ready. If not, install Python from [python.org/downloads](https://www.python.org/downloads/) and run the check again.

### Open Command Prompt in the checker folder

1. Open the `GAM Script Checker` folder in File Explorer.
2. Click the address bar at the top of the window, so the folder path turns blue.
3. Type `cmd` and press **Enter**. A Command Prompt window opens in that folder.

### Paste mode

1. Type `py gamcheck.py` and press **Enter**.
2. Paste the command with **Ctrl+V** (or right-click in the window). If Windows warns that the text has several lines, choose to paste anyway.
3. Press **Enter twice**. The report appears.

### File mode

1. Type `py gamcheck.py` followed by a space. Do not press Enter yet.
2. Drag the script file from File Explorer into the Command Prompt window.
3. Press **Enter**. The report appears.

If `py` is not recognised, use `python` instead of `py` in the commands above.

## Linux

### Open a terminal in the checker folder

1. Open the `GAM Script Checker` folder in your file manager.
2. Right-click an empty part of the window and choose **Open in Terminal**. If your file manager has no such option, open a terminal, type `cd` and a space, drag the folder into the window and press **Enter**.

Check Python with `python3 --version`. Most distributions already have 3.9 or newer.

### Paste mode

1. Type `python3 gamcheck.py` and press **Enter**.
2. Paste the command with **Ctrl+Shift+V** (plain Ctrl+V does not paste in most Linux terminals).
3. Press **Enter twice**. The report appears.

### File mode

1. Type `python3 gamcheck.py` followed by a space. Do not press Enter yet.
2. Drag the script file into the terminal window, or type its name if it is in the same folder.
3. Press **Enter**. The report appears.

## Try it first

These commands are only for practising with the checker. **Do not run them in gam**: the last one deletes a user.

```
gam print users
gam update user bob@example.com suspended on
gam delete user bob@example.com
```

Paste all three in paste mode. The checker should say DESTRUCTIVE: one read, one change, one delete, with a 20-day UNDO note on the delete.

For file mode, check `developers/fixtures/offboard.sh` from inside the checker folder. It should also say DESTRUCTIVE (1 changes, 3 destructive).

## Handy options

Add these after the file name:

```
python3 gamcheck.py cleanup.ps1 --quiet     # hide the read-only lines in a long script
python3 gamcheck.py script.py --json        # machine-readable output for other tools
```

In paste mode the checker also tidies what you pasted, and tells you when it does: it removes a copied prompt (`$ gam ...`, `> gam ...`), straightens curly quotes picked up from a web page or chat (gam will not accept them), and guesses PowerShell or batch from the text.

## What it can and cannot tell you

- **It reads text. It does not run anything.** Commands put together while the script runs (a verb held in a variable, a command typed at a prompt, a list built in a loop) come out as **CANNOT TELL**, never as READ-ONLY.
- **It reports what the script can do, not what one run will do.** GAM's own safety words are understood: a Gmail, calendar-event or device command without `doit`, or a group, licence or Drive-transfer command with `preview`, is reported as a dry run. A script's own `--dry-run` switch is not: if the code path exists, it is reported.
- **Checking for damage to your computer uses a list of known commands** (`rm -rf`, `Remove-Item -Recurse`, `format`, `diskpart` and so on). A determined author can get past a list. This catches careless or AI-generated scripts. It is not a sandbox against a malicious one.
- **A gam command handed to another program as text** (`bash -c "gam ..."`, `ssh host "gam ..."`, `Start-Process -ArgumentList "..."`, `"$(gam ...)"`) is reported as **CANNOT TELL** with the text shown. Check the inner command on its own. Wrappers that pass gam through directly (`sudo -u x gam`, `timeout 300 gam`, `python3 gam.py`, `$GAM`) are followed.
- **Obfuscated code is flagged, not decoded.**
- **Row counts need the file.** "Deletes every user in leavers.csv (212 rows)" only appears when the CSV is next to the script or in the current folder.
- **Placeholders read as CANNOT TELL.** A command copied from documentation with `<GOOGLE SHEET ID>` or `<UserTypeEntity>` still in it cannot be judged.
- **It says what a script would do, not whether it works.** A command GAM7 would reject can still get a verdict when its verb is valid.
- **Python that calls Google's APIs directly** (`googleapiclient`) without gam is not analysed.
- **The command tables go out of date.** They are built from GAM's own source (GAM7 7.48.07, GAMADV-XTD3 7.06.04, legacy GAM 6.58). A command they do not know is CANNOT TELL. A new safety switch added to a command GAM already had is not picked up automatically.

A command written for GAMADV-XTD3 or legacy GAM that GAM7 no longer accepts is named as such, because it will stop with an error on GAM7.

## What it reads

| File | How gam is found |
|---|---|
| `.sh`, no extension | `gam ...`, `$GAM ...` when `GAM=` holds its path, aliases, functions passing `"$@"` to gam |
| `.ps1` | `gam ...`, `& $gam ...`, `Set-Alias`, functions passing `@args` |
| `.bat`, `.cmd` | `gam ...`, `%GAM% ...` |
| `.py` | `subprocess` and `os.system` calls, wrapper functions such as `def gam(*args)`, gam command strings and argument lists kept as data |
| `.txt` | GAM batch files (`gam batch`, `gam tbatch`), including `execute` lines |

`gam csv`, `gam loop`, `gam batch` and `gam tbatch` are followed into the command they repeat or the file they run.

## Exit codes

For use in other scripts: the exit code is the verdict.

| Exit | Verdict |
|---|---|
| 0 | READ-ONLY |
| 1 | CHANGES |
| 2 | CANNOT TELL |
| 3 | DESTRUCTIVE |
| 4 | SUSPICIOUS |

## Maintaining it

Everything except `gamcheck.py` and `verbs/` lives in `developers/`. Run these from the `GAM Script Checker` folder:

```
python3 developers/test_gamcheck.py                        # fixtures, GAM gates, trigger-word attacks, verb coverage
python3 developers/real-world/score.py gamcheck.py         # hand-labelled real commands; fails on any under-warning (corpora are not shipped: build one with fetch_group_corpus.py and label it)
python3 developers/real-world/blind-adversarial-2026-09-13/blind_run.py gamcheck.py   # 178 hostile commands with expected levels from GAM source
git clone --depth 1 https://github.com/GAM-team/GAM.git
python3 developers/build_verb_table.py GAM/src/gam > verbs/gam7.json   # after a GAM release
git clone --depth 1 https://github.com/GAM-team/GAM.wiki.git
python3 developers/build_verb_table.py --wiki GAM.wiki verbs/gam7.json > verbs/wiki.json
python3 developers/test_gamcheck.py                        # fails if a new verb has no danger level
```

A new verb with no danger level fails the test instead of defaulting to read-only. Give it a level in `VERB_LEVEL` in `gamcheck.py`.

`developers/ttypaste.py` pastes lines into the checker through a real terminal, the way a person would, for testing paste mode on other machines.

Fixtures use example.com addresses only. Real scripts for local testing go in `developers/local-samples/`, which is never shipped.

## Licence

Apache License 2.0, copyright (c) 2026 Paul Ogier, Outsource House. Keep the attribution block at the top of `gamcheck.py` if you redistribute it. Provided as is, without warranty.

GAM training from Taming.Tech: [GAM7 course](https://taming.tech/GAMCourse), [Google Workspace Admin course](https://www.taming.tech/GoogleWorkspaceAdmin), [Google Workspace End-User course](https://www.taming.tech/TheCompleteWorkspaceCourse).

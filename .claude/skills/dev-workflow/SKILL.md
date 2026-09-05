---
name: "dev-workflow"
description: "The development workflow for this repository – GitFlow branching (main/dev/feature/release/hotfix), commit and PR protocol, clean code patterns, and verification discipline. Use this skill whenever work touches a git repository: before committing, pushing, branching, or opening a PR; when refactoring or cleaning up code; when adding a file, layer, module, or data source to an existing project; when debugging a bug whose root cause isn't yet confirmed; or when reverting. Also trigger on phrases like \"commit this\", \"let's push\", \"clean this up\", \"make a branch\", \"cut a release\", \"why is this still broken\", or when writing code that will live in a repo. Governs the rules that the maintainer approves every commit and verifies visual output personally. Consult before any git operation."
---

# Dev Workflow

The engineering workflow for this repository: GitFlow branching, clean commits, and code that stays simple as it
grows.

The goal behind all of it is that a repo should be understandable six months from now by someone
who wasn't there, including the future maintainer. Most of these rules exist because a shortcut that
saved five minutes cost hours later.

---

## TWO RULES THAT OVERRIDE EVERYTHING

### 1. Ask before committing

Never run `git commit` without the maintainer's explicit go-ahead on that specific commit. Not
"they said yes to committing earlier in the session" – each commit needs its own confirmation.

When work is ready, stop and present it: which files changed, what each change does, and a
proposed commit message. Then wait.

This exists because a commit is a claim that something works. Committing before the maintainer
has confirmed it works turns the git history into a record of guesses, and unwinding those is far
more expensive than pausing to ask. The same applies to `push`, `merge`, and anything that
touches a remote or a shared branch.

Staging (`git add`), writing the message, and showing a diff are all fine unprompted – those are
reversible and they make the decision easier.

### 2. The maintainer verifies anything visual

Rendered output – map styling, layout, color, spacing, "does this look right" – is the
maintainer's call, made with their own eyes. Never report a visual problem as fixed based on your own inspection.

The honest formulation is "the change is in, reload and take a look," not "confirmed fixed."

If asked to verify something visually, that is an invitation to *show the evidence*: capture the
screenshot, state exactly where you looked (location, zoom, what's toggled), and let him judge.
Evidence, not verdict. If you genuinely can't see the thing – the tab won't render, the
screenshot is stale – say so plainly instead of inferring from code that it must be fine.

Non-visual claims are different. "All 12 geometries validate as `holes: 0`" is a fact you can
verify and state. Know which kind of claim you're making.

---

## GITFLOW

Two permanent branches, three kinds of temporary ones.

| Branch | Lives | Purpose |
|---|---|---|
| `main` | forever | Production. Only ever receives merges from `release/*` or `hotfix/*`. Every commit is a tagged, deployed version. |
| `dev` | forever | Integration. Where finished features accumulate between releases. |
| `feature/*` | short | New work. Branches off `dev`, merges back to `dev`. |
| `release/*` | short | Release prep. Branches off `dev`, merges to **both** `main` and `dev`. |
| `hotfix/*` | short | Urgent production fix. Branches off `main`, merges to **both** `main` and `dev`. |

```
main    ──●──────────────────────●────────────●──►  tagged releases
           \                    /            /
            \        release/1.0            /
             \          /                hotfix/1.0.1
dev  ──●──────●────────●──────●────────────●──────►  integration
        \    /          \    /
      feature/a       feature/b
```

**Everyday loop (features):**

1. Branch off `dev`: `git switch dev && git pull && git switch -c feature/org-directory-page`
2. Commit in small logical units as you go.
3. Push the branch, open a PR **into `dev`**.
4. Merge once reviewed and verified. Delete the branch.

**Cutting a release:**

1. `release/1.2.0` off `dev`. Only stabilization commits go here – version bumps, changelog,
   bug fixes found in testing. No new features.
2. PR into `main`, merge, tag: `git tag -a v1.2.0 -m "..."`.
3. **Merge back into `dev` too.** Skipping this is the classic GitFlow mistake – the fixes made
   during release prep get lost, then reappear as bugs after the next release.

**Hotfixes:**

Branch off `main`, fix, PR into `main`, tag, then merge into `dev` as well. Same reason.

**Branch naming:** `feature/`, `release/`, `hotfix/` prefix, then a short description of what it
touches: `feature/wordpress-iframe-embed`, `hotfix/broken-pmtiles-path`. Releases use the version:
`release/1.2.0`.

**Branch scope:** one branch answers one question or fixes one thing. If a branch starts
collecting unrelated changes, that's a signal to split it. A PR that's hard to describe in a
sentence is usually two PRs.

**Why this shape:** `main` staying deployable-and-tagged means there's always a known-good version
to roll back to, and `dev` absorbing integration risk means half-finished work never blocks a
production fix. The cost is discipline about the double-merges – release and hotfix branches must
land in both places.

---

## PULL REQUESTS

A PR is where the reasoning lives. The commit history says what changed; the PR says why it was
worth changing and what was considered.

**Include:**
- What problem this solves, in a sentence
- What approach was taken, and any alternative that was rejected and why
- How it was verified – and explicitly, what still needs the maintainer's eyes
- Anything intentionally left undone, with a note or follow-up issue

Debugging false starts belong here, not in commit messages. "Tried X first, it turned out to be
unrelated" is useful context in a PR and noise in `main`'s history.

**Target the right branch.** Features → `dev`. Releases and hotfixes → `main` (then a second
merge into `dev`). Getting this wrong is easy and annoying to unwind.

---

## COMMITS

**One logical change per commit.** A commit that fixes a bug *and* renames variables *and*
updates docs can't be reverted cleanly, and its message can't be accurate.

**Message format:**

```
Short imperative summary, under ~72 chars

Why this change exists and what problem it solves. The diff already shows
what changed – the message explains what the diff can't: the reasoning, the
constraint, the thing that was tried first and didn't work.

Include specifics that would be expensive to rediscover: root cause, why an
obvious alternative was rejected, what was verified and how.
```

**Example:**

```
Remove duplicate basin/HUC-8 context layers

Both shapes were drawn twice - once by their own dedicated context layer,
once by org-fill/org-outline (they're real org boundaries in
boundaries.geojson). The overlapping outlines, one of them line-offset,
rendered as dotted fragments along every shared edge.

Deleted the four redundant layers. Popup metadata now reads from the
reference files directly rather than from rendered features.
```

**Do record a confirmed root cause** – the next person to see similar symptoms will search for it.
**Don't narrate the hunt.** "Third attempt at fixing X" is PR material.

**Never commit** commented-out code, debug logging, temporary filters, `console.log`, or files
that only exist to be excluded. Clean the workspace first.

---

## KEEPING CODE CLEAN

The forces that turn a clean codebase into spaghetti are all individually reasonable. These
counter them.

### Delete, don't disable

When something is no longer needed, remove it. Don't comment it out, don't leave it behind a
flag, don't add a filter that excludes it while it still loads.

Disabled code still has to be read, still confuses search, and still gets partially updated by
someone who doesn't know it's dead. Git remembers it – that's what git is for. If it matters why
it was removed, put that in the commit message or a one-line comment where it used to be.

The tell that this rule is being violated: a filter, flag, or exclusion whose only purpose is to
neutralize something that's still present.

### One source of truth

Every fact, shape, or piece of configuration lives in exactly one place. When the same thing
exists twice, the copies drift – and worse, both get rendered/used/read and produce artifacts
nobody can explain.

Before adding a file, layer, source, or constant, check whether it already exists somewhere. When
two things must share data, one reads from the other – don't copy.

This applies especially to derived files. If `B` is generated from `A`, then `A` is the source of
truth, `B` is regenerated whenever `A` changes, and nobody hand-edits `B`. If it's not obvious
which is which, say so in a comment or README. When a derived file stops earning its keep, delete
it rather than maintaining a second copy of the same data.

### Comments explain why

Code shows what it does. Comments should carry what the code can't: the constraint, the
non-obvious reason, the thing that seems wrong but isn't.

Stale comments are worse than none. When a comment narrates history that no longer matters –
"briefly disabled while debugging X, turned out to be unrelated" – delete it once the story is
over. Keep the ones that would prevent someone from reintroducing a bug.

### Small and single-purpose

A function does one thing. A file has one job. When something grows past what fits in your head,
split it along the seam that already exists.

Prefer removing a special case over adding a flag to handle it. Every conditional is a branch
someone has to reason about later.

---

## DIAGNOSE BEFORE FIXING

The most expensive failure mode is confidently fixing something that wasn't the problem. It
produces commits that don't help, muddies the history, and – because the symptom persists – leads
to stacking more speculative fixes on top.

**The sequence:**

1. **Reproduce.** See the actual failure. If you can't observe it, you can't confirm you fixed it.
   When it's visual, have the maintainer point at it precisely – location, zoom, what it looks like.
2. **Isolate.** Change exactly one variable and observe. Toggle one layer, comment one block,
   revert one file. Changing two things at once means learning nothing from the result.
3. **Confirm the cause.** You should be able to make the symptom appear and disappear on demand.
   Until then, you have a hypothesis, not a diagnosis.
4. **Then fix**, and verify the same way you reproduced it.

**Say which stage you're at.** "I think it's X" and "I confirmed it's X by toggling it off and
on" are very different claims. Collapsing that distinction is what makes debugging feel like it's
going in circles.

**When a fix doesn't work, revert it before trying the next thing.** Stacked speculative fixes
make it impossible to tell what actually helped, and they turn a one-commit fix into a
five-commit archaeology problem.

**Useful heuristic:** when an artifact traces the *edges* of something, suspect duplicate or
offset rendering of the same geometry before suspecting the geometry itself. Two things drawn
nearly-but-not-quite on top of each other is a very common cause of visual noise.

**Separate "real bug" from "the bug being reported."** You'll often find genuine problems while
hunting something else. Fix them – but don't assume you've solved the reported issue just because
you found *a* defect. Confirm against the actual symptom.

---

## REVERTING

On a shared branch (`main`, `dev`), revert forward. `git revert <sha>` creates a new commit that
undoes the old one, leaving history intact and honest.

Reserve history rewriting (`reset --hard`, force-push) for branches nobody else has pulled.

State plainly what's being undone and why, so the history reads as a decision rather than a
mistake being hidden.

---

## BEFORE PRESENTING WORK FOR COMMIT

A short pass that catches most of what would otherwise land in the history:

- `git status` and `git diff` – is everything in the diff intentional?
- On the right branch? (features off `dev`, hotfixes off `main`)
- No leftover debug code, temporary filters, commented-out blocks, or test scaffolding
- No stale comments describing a state that no longer exists
- Derived/generated files regenerated if their sources changed
- Syntax checked (`node --check`, `python -m py_compile`, or running the thing)
- Anything visual → hand to the maintainer to look at, don't self-certify

Then present: files changed, what each change accomplishes, proposed commit message, and anything
you're unsure about. Ask.

---

## ENVIRONMENT NOTES

**Sandboxed filesystems and git locks.** Some environments can't unlink git's lock files, so
commands fail with `Operation not permitted` or leave stale `.git/index.lock`. Move them aside
before git commands:

```bash
for f in .git/index.lock .git/HEAD.lock .git/objects/maintenance.lock; do
  [ -f "$f" ] && mv "$f" "$f.old.$(date +%s%N)" 2>/dev/null
done
```

`unable to unlink` warnings *after* a command usually mean it succeeded anyway – verify with
`git log` / `git status` rather than assuming failure and retrying.

The same restriction breaks `git reset --hard` and `git checkout -- <file>`. To restore a file:
read the old content with `git show <sha>:<path>`, then write it back in place.

**Writing files in Python – build the string first.** `open(path, 'w')` truncates immediately, so
if serialization raises afterward, the file is destroyed:

```python
# Wrong - truncates, then fails, leaving an empty file
with open(path, 'w') as f:
    f.write(gdf.to_json())

# Right - if to_json() raises, the file is untouched
json_text = gdf.to_json()
with open(path, 'w') as f:
    f.write(json_text)
```

**Push access.** If the environment has no registered SSH key, `git push` fails with
`Permission denied (publickey)`. Commit locally and tell the maintainer to push from their own terminal –
don't try to work around it.


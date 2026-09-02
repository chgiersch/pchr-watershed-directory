# Releasing

Every step, in order. The guards exist because skipping them has shipped
mis-tagged releases twice (v1.1.0 and the first v1.3.0 attempt - both
tagged the previous release's commit).

1. **Feature work merges to `dev` first.** Push the branch, open a PR with
   base `dev`, confirm the commit count matches what you expect, merge
   with a merge commit, delete the branch.

2. **Run the lint:** `python3 scripts/check.py` on `dev`. All checks pass
   or the release stops here.

3. **Release PR:** base `main`, compare `dev`. The commit count should be
   your merged work plus its merge commits - if it shows the whole history
   or zero, the base is wrong. Merge with a merge commit (never squash -
   it flattens every commit message into one).

4. **Verify before tagging.** This is the guard:

       git switch main
       git pull
       git log --oneline -1

   READ the output. It must show the release merge you just made. If it
   shows the previous release, the merge did not land - stop.

5. **Tag and push the tag:**

       git tag -a vX.Y.Z -m "One line on what this release is"
       git push origin vX.Y.Z

6. **Wait for GitHub Pages** (Actions tab, ~2 minutes), then load the
   live standalone page and confirm it behaves.

7. **Rebuild the WordPress bundle from `main`:**

       python3 scripts/build_directory.py --wordpress

   The output must NOT warn about a -dirty version, and the bundle header
   must show the tag you just pushed. Paste the entire file over the
   county page's HTML block. That paste IS the deployment.

8. **Click through the county page:** map renders, popup opens with the
   bridge note, an org click scrolls to its entry, "Show on map" moves
   the map, the house button returns home, the map stays pinned while
   scrolling.

Notes:
- Commands are written without inline comments on purpose: interactive
  zsh executes `#` as a command, and comment fragments have been parsed
  as push refspecs here before.
- If a tag lands on the wrong commit: `git tag -d vX.Y.Z` then
  `git push origin :refs/tags/vX.Y.Z`, fix the merges, re-tag.

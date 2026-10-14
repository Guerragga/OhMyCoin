# Private-to-public release

## Do not publish the historical repository

The existing private repository, branches, pull requests and Actions history may contain personal data or secrets. Deleting a file in the latest commit does not remove previous versions.

Rewriting only main would not remove old branches, PR references, forks, cached views, releases or artifacts. This audit therefore does not make the existing repository public and does not force-push its history.

Rotate any secret that was ever exposed; history cleanup is not credential revocation.

## Preferred safe handoff: a new empty repository

After the exact clean commit has green tests, Docker/browser checks and a reviewed source-tree scan:

1. Keep the original repository private.
2. Create a **new, empty, private** GitHub repository, without a README/license initialization.
3. Export only the reviewed tracked tree, without copying .git, .env, database volumes, caches or backups.
4. Create one new root commit and push to the new repository.
5. Inspect its files, single-commit history and CI before considering public visibility.

Example from your local private clone, with an already reviewed clean ref:

```bash
git switch refactor/public-ready
git status --short
# Stop if the working tree contains changes you still need to include.
git archive --format=tar --output=../ohmycoin-clean.tar HEAD

mkdir ../ohmycoin-public-clean
tar -xf ../ohmycoin-clean.tar -C ../ohmycoin-public-clean
cd ../ohmycoin-public-clean

git init -b main
git add .
git commit -m "feat: initial public release"
git rev-list --count HEAD
# Expected: 1
git rev-list --parents -n 1 HEAD
# Expected: one SHA only, with no parent SHA.

git remote add origin "NEW_EMPTY_PRIVATE_REPOSITORY_URL"
git push -u origin main
```

Use your intentionally chosen public commit identity. Review that metadata too. Do not accidentally include local personal email addresses.

No command above deletes the original repository or its history. The exported archive contains tracked files only; inspect the archive itself before sharing.

## Final checks

- The source tree contains no personal records, real dumps, tokens or credentials.
- Fictional demo credentials are clearly labeled as public/local examples.
- The new repository has one root commit and no imported historical branches/tags.
- CI passes on the new repository's commit.
- No attachments, issues, PRs, releases or workflow artifacts were copied from the private repository.
- Public hosting, if desired, gets a separate security/deployment review.

Only then change the **new** repository's visibility. Do not reuse the old repository's historical object store for convenience.

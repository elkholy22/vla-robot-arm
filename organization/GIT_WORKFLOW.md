# Git Workflow (v0.3.0)

## Summary

We use the [feature branch workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow). All work happens on feature branches and is merged into `main` through merge requests. The Quality Managers review and merge MRs. `main` always holds a working, tested version of the code.

We use a **polyrepo** setup: separate repositories for `backend` , `robot` and `organization` .

## The `main` Branch

`main` is protected. Nobody pushes to it directly; changes only land via merged MRs. `main` should always contain a working version that passes CI.

When an MR is merged, the Quality Manager tags the resulting squash commit with a [SemVer](https://semver.org) version (e.g. `v0.2.0`). Tags give a clear version history and serve as recovery points for older versions.

## Feature Branches

Each piece of work gets its own feature branch, kept small enough to develop and merge quickly. Push branches as soon as they exist so the rest of the team can see what is in progress.

**Naming:** `{type}/{issue-id}/{description}`

- `type` is one of: `feature`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`
- `issue-id` is the number of the related issue (see issue board)
- `description` is short information about the task

Examples:

```
feature/16/remote-control-gui
ci/16/add-pipeline
fix/42/ik-joint-limits
```

We use the **issue ID** rather than a username so that more than one person can collaborate on a branch, and so each branch ties directly to a tracked issue.

The CI pipeline includes a branch naming check on merge requests that warns if a branch does not follow this scheme.

## Commits

Commit often; the history inside a feature branch does not need to be clean because we squash on merge. Keep the commit subject short and in the imperative mood, optionally prefixed with the conventional type:

```
feat: add Dockerfile and conda env for Octo image
ci: add lint and test pipeline
fix: correct IK joint angle clamping
```

Fetch and pull before committing, and push frequently so the team stays in sync.

## Merge Requests

Before opening an MR, make sure your branch is pushed and CI passes. You do not need to manually keep your branch up to date with `main`; if a fast forward is not possible, use the **Rebase** button on the MR (or `git rebase origin/main` locally) to replay your work on top of the latest `main`.

Please Reference the related issue in the MR description.

```
Related to ees-vla-team-1/organization#16
```

Use `Related to` (or a plain mention) while work on the issue continues. Use `Closes ees-vla-team-1/organization#16` only on the MR that actually completes the issue, so it auto-closes on merge.

## Merge Method

MRs are merged with **squash** and **fast-forward**, and the source branch is deleted on merge. This keeps `main` linear and tidy: one commit per merged feature, no merge commits.

Deleting the branch does not lose history. The full discussion stays in the MR, the squashed commit stays on `main`, and SemVer tags mark each version. To revisit an old version, check out its tag; to see why a change was made, read its MR.

## Continuous Integration

CI runs automatically on pushes that touch `src/` or `tests/`, and on merge requests. Each repo has its own pipeline:

- **backend** runs an environment check inside the Octo container image (verifies the core stack imports), and rebuilds and publishes the image when the `Dockerfile` or `environment.yml` change on `main`.
- **robot** runs lint and tests on a lightweight Python image.

`main` should only ever contain code where CI passes.

## Sources

- <https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow>
- <https://semver.org>

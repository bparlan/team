Yes. The previous prompt is too project-specific for regular use. What you want is a reusable **safe structural maintenance operation** for OMP.

The core principle should be:

> **Never reorganize for aesthetics. Reorganize only when evidence shows a structural improvement, and prove nothing broke afterward.**

Use this as a reusable OMP prompt:

# Project Structure Maintenance

Review and improve the structure of the current project directory.

This is a **stability-first maintenance task**.

The goal is to keep the project clean, understandable, and maintainable as it evolves, without breaking existing infrastructure, tooling, scripts, agent workflows, or runtime behavior.

---

## Core Rule

**Do not reorganize files merely because the structure looks messy.**

Every structural change must have a demonstrated reason and must improve at least one of:

* clarity
* maintainability
* discoverability
* separation of responsibilities
* reproducibility
* dependency isolation
* prevention of repository pollution

If there is no clear improvement, leave the structure unchanged.

**Existing working infrastructure has higher priority than aesthetic folder organization.**

---

# Phase 1 — Inspect

Inspect the current project structure before making changes.

Identify:

* source/application code
* executable scripts
* tests
* configuration
* documentation
* assets
* source/input data
* generated outputs
* temporary/staging files
* backups
* dependencies or environment artifacts
* agent/tooling infrastructure
* unknown files

Also inspect:

* Git status
* tracked vs untracked files
* `.gitignore`
* Python/package configuration where applicable
* virtual environments
* scripts and entrypoints
* relative and absolute path dependencies
* imports
* configuration references
* agent/OMP instructions and skills

Do not assume a file's purpose based only on its name.

Inspect evidence and references where necessary.

---

# Phase 2 — Diagnose Before Changing

Identify structural problems such as:

* unrelated concerns mixed together
* generated files polluting source directories
* dependencies accidentally installed into the project
* obsolete backups mixed with active source
* tests mixed with production code
* configuration scattered unnecessarily
* scripts relying on fragile relative paths
* duplicated files with unclear authority
* directories whose purpose is unclear
* artifacts that should be ignored by Git

For every proposed change, establish:

1. What is currently wrong?
2. What evidence proves it?
3. What improvement will the change provide?
4. What existing dependencies could be affected?

Do not change anything until these questions can be answered.

---

# Phase 3 — Protect Existing Infrastructure

Before moving, renaming, deleting, or reorganizing anything:

Search for references to the affected path.

Check:

* imports
* shell commands
* Python subprocess calls
* configuration files
* environment variables
* agent instructions
* skills
* tests
* documentation
* CI/tooling if present
* runtime-generated paths

Pay special attention to relative paths and working-directory assumptions.

Do not break a working path without updating every known dependency.

---

# Phase 4 — Propose the Minimum Change

Prefer the **smallest structural improvement**.

Do not introduce conventional structures merely because they are popular.

For example:

* do not add `src/` unless it provides a real benefit
* do not add abstraction directories
* do not create empty organizational folders
* do not reorganize working agent infrastructure without evidence
* do not move files solely to achieve a visually symmetrical tree

Avoid over-engineering.

The preferred outcome is:

> small project root + obvious locations + stable execution + clear ownership of files

Create a migration plan:

```text
CURRENT PATH → PROPOSED PATH → REASON → REFERENCES AFFECTED
```

If the benefit is marginal or risk exceeds value, do not perform the move.

---

# Phase 5 — Environment and Dependency Safety

If dependency packages, build artifacts, caches, or environment files appear inside the repository:

Do not blindly move them into another directory.

Determine whether they are:

* legitimate vendored dependencies
* virtual-environment contents
* build artifacts
* generated files
* accidental package installation pollution
* required runtime files

Prefer fixing the underlying environment problem rather than hiding it through folder reorganization.

Never delete environment or dependency artifacts until their role is understood.

---

# Phase 6 — Execute Safely

Only perform changes that have a clear justification.

Rules:

* preserve file contents
* preserve executable permissions
* preserve configuration
* preserve Git history where possible
* do not overwrite files
* do not delete uncertain files
* do not discard uncommitted work
* do not run destructive Git commands
* do not regenerate production outputs unnecessarily
* do not modify secrets or `.env` contents

Prefer moves over copy/delete operations.

Make changes incrementally where practical.

---

# Phase 7 — Validate

After structural changes, prove that the project remains functional.

Validation should be proportional to the project and changes made.

Check as applicable:

### Repository

* Git status
* no unexpected file disappearance
* no accidental large/generated artifacts introduced

### Runtime

* imports resolve
* package/environment resolution is correct
* scripts still execute
* configuration paths resolve
* assets/data paths resolve

### Tests

Run existing relevant tests.

Do not run unrelated expensive operations.

Do not trigger paid APIs unless explicitly necessary.

Prefer:

* syntax checks
* import checks
* unit tests
* dry-run modes
* existing validation commands

### Agent Infrastructure

Verify applicable agent tooling still works:

* project instructions
* skills
* expected working-directory assumptions
* referenced scripts
* configuration paths

### Path Integrity

Search for stale references to moved or renamed paths.

Confirm they were either:

* updated correctly, or
* intentionally retained because compatibility requires it.

---

# Phase 8 — Result Report

Report:

## Structural Improvements

What changed and why.

## Files Moved

```text
OLD → NEW
```

with a short reason.

## Files Intentionally Left Unchanged

Explain important cases where stability was preferred over reorganization.

## Risks Avoided

Identify potential breakages discovered and prevented.

## Validation

List exactly what was checked and the result.

## Remaining Issues

List anything suspicious that requires manual review.

Do not invent cleanup tasks.

---

# Decision Rule

Use this rule for every potential structural change:

> **Evidence of improvement × confidence in safe migration must exceed the risk of disrupting existing infrastructure.**

When uncertain:

**Preserve the working structure and report the issue instead of making speculative changes.**

The objective is not a perfect directory tree.

The objective is a project that becomes progressively easier to maintain while remaining stable.

## My recommendation

I would save this as a reusable OMP skill/task called something like:

**`project-structure-maintenance`**

Run it periodically after major development phases—not constantly after every edit.

The most important improvement over the original prompt is that this one gives OMP explicit permission to conclude:

> **"The current structure is good enough. No structural changes justified."**

That prevents the classic agent failure mode: *agent was asked to improve folders, therefore agent must move folders*. That is exactly how otherwise stable infrastructure gets broken.

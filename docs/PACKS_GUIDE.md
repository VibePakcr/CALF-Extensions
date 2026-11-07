# Local Pack Tools & Repository pack — 0.1.0-preview.1

[한국어](PACKS_GUIDE_KR.md)

This developer preview manages versioned local extensions without changing CALF records or host settings. Repository inspect reads a local Git repository and saves a project map with file-version evidence. It does not run your application tests. Python 3.10+ and Git 2.43+ are required; no native core, SDK, model, global pip installation or background service is needed for this mode.

## Start

1. Verify the downloaded ZIPs against SHA256SUMS, then extract Local Pack Tools into a new folder. Keep Repository Pack as a ZIP.
2. Follow `docs/REPOSITORY_PACK.md` inside Local Pack Tools: select the physical Python and Git executables, create a separate store, stage, check, qualify and explicitly activate the pack.
3. Bind a repository to a separate captures directory, run once, inspect the receipt and export a saved map. The original repository remains read only. Export includes no source text unless you request it.

Run commands from the extracted tools folder. On Windows use `python -X utf8 -B -m calf_extensions.packs.cli`; on macOS/Linux use `python3 -B -m calf_extensions.packs.cli`. Use absolute paths and a short Windows store root, for example `C:\CP`. Qualification refuses paths beyond its budget without changing Windows settings.

## Update and recover

For a pack update, stage and qualify a different version, read `status`, then activate with the current active digest. Rollback selects a retained qualified lock for future work. Existing bindings retain their original version, interpreter, tool identities and receipts. Do not remove referenced versions or dependencies.

For a manager update, extract the new tools into a sibling folder and run them against the same explicit `--home` store. Return to the retained tools folder to roll back. Do not replace the store, captures, existing settings or running executable. This delivery tests a marked next-version fixture with the same v1 protocol; it does not certify arbitrary future versions.

`recover` inspects interrupted staging/activation. After checking the observed state, `recover --acknowledge OPERATION_ID` completes confirmed bookkeeping. It does not resubmit work or rewrite evidence. A started operation with no receipt remains UNKNOWN until reconciled.

## What was verified

macOS arm64, Windows x86_64 and Debian x86_64 each passed 20 manager contracts, two 20-test pack qualifications with zero skips, 12 lifecycle groups and five manager-upgrade/rollback checks. Tests include real process exits before/after activation, staging recovery, owned-child timeout cleanup, CJK offline export, stale-pointer refusal and retained source/receipt hashes. The no-receipt case is an explicitly simulated negative fixture. See PACKS_VERIFICATION.json for platform versions and artifact identities.

The `0.1.1-preview.1` Repository ZIP and `update-fixture` tools ZIP are test fixtures, not recommended upgrades. Install the `0.1.0-preview.1` tools and Repository pack for this preview. Native Harness stays 1.8.7 and Workbench stays 1.9.2. Host-session qualification is separate; the Claude adapter remains macOS-only. Existing code keeps process-interruption recovery distinct from power-loss guarantees. No model or memory/soak test was run for this release.

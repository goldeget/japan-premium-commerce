# Run-scoped encrypted restore preparation

This isolated check extends only `tests/procurement/ci_restore.sh`. It keeps
the existing CI ownership guards and independent, run-owned temporary MariaDB
restore. A run generates a fresh age identity under a mode-0700 directory in
`RUNNER_TEMP`, encrypts the CI-only SQL snapshot, decrypts it, and requires an
exact byte comparison before any import. It also confirms that a modified
ciphertext and a separately generated wrong identity are rejected. Only then
does it import into the existing independent temporary database and run its
domain readback.

The private SQL dump, age identity, ciphertext, and plaintext are removed by
the exit trap. The only new artifact is
`$QA_ARTIFACT_DIR/encrypted-restore-outcome.json`, containing booleans and the
age CLI version. Nothing is written to production databases or uploaded from
the private directory. This does not create or validate a production backup,
full-volume snapshot, backup retention policy, or recovery-time objective.

The workflow adds the maintained `age` CLI to the existing apt
install step. Contract tests verify that dependency and run the shell flow
with mocked Docker/age commands on Linux; the mock tests exercise data ordering
and failure handling but do not claim cryptographic runtime acceptance. The
real age round-trip remains for the isolated GitHub Actions run. The current
Windows host has no usable local Linux Bash or age runtime, so only static
contract checks can run there.

Staged files:

- `ci_restore.sh` — proposed replacement for `tests/procurement/ci_restore.sh`
- `procurement-platform.yml` — current workflow with only the apt dependency
  line extended
- `tests/procurement/test_ci_restore_encryption.py` — proposed contract test

Run the staged tests from this directory with:

```powershell
py -3.12 -m unittest discover -s tests/procurement -p 'test_ci*.py' -v
```

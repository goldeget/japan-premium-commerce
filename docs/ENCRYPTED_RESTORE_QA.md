# Encrypted restore acceptance

`tests/procurement/ci_restore.sh` runs only for the exact run-owned disposable procurement project. It writes its SQL snapshot and per-run age identity to a mode-0700 runner-private directory, encrypts and decrypts the snapshot, and compares the decrypted bytes with the original before database import.

It verifies rejection of modified ciphertext and a separately generated wrong identity, then imports only the verified plaintext into an independent temporary MariaDB container. Native/domain readback verifies that restored database. The exit trap removes the run-private key, dump, ciphertext and plaintext, and the owned restore container. Keys and database bytes are never uploaded.

The retained `encrypted-restore-outcome.json` contains only the age version and bounded pass/fail booleans. Actual candidate/run/outcome and artifact digest are recorded in [TEST_RESULTS](TEST_RESULTS.md) and [release automation evidence](evidence/2026-10-29-release-automation.md).

The full acceptance workflow installs the maintained age CLI. `test_ci_restore_encryption.py` tests ordering, corruption rejection, safe artifacts and private-file cleanup through a fake Docker/age protocol on Linux. Those mocks do not establish cryptographic acceptance; the actual age/MariaDB round trip is a required runtime phase.

This validates a disposable database snapshot. It does not create a production backup destination, full-volume backup, retention policy, approved RPO/RTO, external key custody or independent production recovery acceptance. No production database or persistent backup key is changed.

```sh
python3 -m unittest discover -s tests/procurement -p 'test_ci_restore_encryption.py' -v
```

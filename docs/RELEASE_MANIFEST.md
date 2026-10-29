# Offline release manifest verifier

This is a portable, standard-library-only preparation artifact. It checks a
release record before an operator-controlled promotion; it does not build,
publish, pull, deploy, schedule, or contact any service.

## Run

From PowerShell:

```powershell
py -3.12 -m unittest discover -s tests/release -v
py -3.12 tools/release/release_manifest.py `
  --root C:\path\to\clean\checkout `
  --manifest C:\path\to\release-manifest.json
```

Keep the manifest outside the source checkout: it records the source commit
that it validates. `application.archive_path` must point to a file inside the
checkout. Since the verifier requires a clean Git worktree, generated archive
files should live in a repository-ignored build directory; tracked migration
and evidence files remain part of the source commit.

## Manifest contract

The JSON root accepts only these keys:

```json
{
  "schema_version": 1,
  "source": {
    "repository": "owner/repository",
    "commit_sha": "<40 lowercase hex characters>",
    "gitlink_path": "themes/hummingbird",
    "gitlink_sha": "<40 lowercase hex characters>"
  },
  "application": {
    "archive_path": "build/release/app-image.oci.tar",
    "archive_sha256": "<64 lowercase hex characters>"
  },
  "database_image_ref": "mariadb:10.11@sha256:<64 lowercase hex characters>",
  "build_input_refs": [
    "docker.io/library/composer:2@sha256:<64 lowercase hex characters>"
  ],
  "migrations": [
    {"path": "modules/example/upgrade.php", "sha256": "<64 lowercase hex characters>"}
  ],
  "evidence": [
    {"path": "docs/evidence/qa.txt", "sha256": "<64 lowercase hex characters>"}
  ]
}
```

`registry_image_ref` and `registry_manifest_digest` may be supplied together
under `application`. Their digest syntax and equality are checked, but this
offline tool records them as a declaration only; it does not fetch the
registry or prove the archive was published there. `archive_sha256` is the
SHA-256 of the exact archive file bytes. OCI layout/index internals are not
inspected, and the archive hash is not an OCI or registry manifest digest.

The verifier also checks that the checkout is exactly at `source.commit_sha`,
has no Git changes, and has a clean `themes/hummingbird` submodule checkout at
the commit recorded by the parent repository gitlink and `source.gitlink_sha`.
Every migration and evidence file listed must be a regular, non-symlink,
repository-relative file with the recorded SHA-256. Database and build-input
image references must be pinned to lowercase `sha256` digests.

Success means only that the supplied declarations and local bytes are
consistent. The output explicitly reports `completeness: not_checked` and
`deployment_authorized: false`; it does not decide whether all required
migrations, evidence, approvals, compatibility checks, or release gates are
present.

# Local Docker release package preparation

`package_release.py` is a standalone preparation tool. It accepts an explicit
clean checkout, builds only the application image from `docker/Dockerfile`,
exports the image to Docker's `image save` archive format, checks the archive,
removes the newly created source tag, then reloads the archive without
rebuilding. It does not use Compose, contact a production host, push an image,
upload artifacts, or read and serialize environment variables or secrets.

The output location is deliberately fixed to the checkout's
`release-artifacts/` directory. The repository excludes this exact path in both `.gitignore` and
`.dockerignore`. The tool checks both rules and confirms Git ignores
the output directory before building. This keeps the source tree clean and
prevents the archive from becoming part of its own Docker build context.

Example:

```powershell
py -3.12 tools/release/package_release.py `
  --root C:\path\to\japan-premium-commerce `
  --output-dir C:\path\to\japan-premium-commerce\release-artifacts
py -3.12 tools/release/release_manifest.py `
  --root C:\path\to\japan-premium-commerce `
  --manifest C:\path\to\japan-premium-commerce\release-artifacts\ordenowa-prestashop-sha-<commit>.release.json
```

The tool refuses a non-local Docker context, an existing source-SHA tag, an
existing artifact for that SHA, a dirty parent/theme checkout, or mutable
external `FROM` references. It tags locally as
`local-only/ordenowa-prestashop:sha-<source-commit>` and labels the image with
the source commit and theme gitlink. The source repository slug is normalized
from the local `origin` URL without recording any user or password component;
the pinned database image is read from the `mariadb` service in `compose.yaml`.
The archive is exported by the built image's config ID, then its Docker
`manifest.json`, untagged state, config bytes, and referenced layer entries are
checked. The exact archive byte hash is recorded. Only the just-created tag is
removed after its ID is rechecked; the archive is loaded untagged, then Docker
inspects the immutable config ID and labels. No image is rebuilt during that
check. The load check uses the same local daemon (image layers may remain in
its cache), so it proves archive round-trip behavior and not loading on an
independent clean host.

The `.release.json` file follows the repository's offline
`tools/release/release_manifest.py` contract. It supplies the source SHA and
theme gitlink, archive path and byte hash, pinned Compose database image,
pinned Dockerfile base references, and empty migration/evidence lists. Those
empty lists intentionally leave completeness unchecked and deployment
unauthorized. `.package.json` holds the Docker-specific config digest and
same-daemon archive-load evidence.

## Digest meanings and limits

- `archive_sha256` hashes the exact bytes of the Docker-save tar file.
- `docker_image_config_digest` is the SHA-256 image ID from Docker's image
  config object; the archived config bytes must match it.
- `registry_manifest_digest` is explicitly `not_published_or_checked`. This
  tool never pushes or contacts a registry, and the archive hash and config
  digest are not registry manifest digests.
- `runtime_acceptance` is `not_checked`; a successful local archive load is not
  browser, database migration, scheduler, security, or production acceptance.
- `docker/Dockerfile`'s `# syntax` frontend reference is recorded. The
  current project uses a mutable syntax tag (`docker/dockerfile:1`), so build
  frontend reproducibility is not established by this artifact.

Run the mocked local protocol tests with:

```powershell
py -3.12 -m unittest discover -s tests/release -v
```

Tests use a fake command runner and synthetic Docker-save archives; they do
not require Docker or perform network operations.

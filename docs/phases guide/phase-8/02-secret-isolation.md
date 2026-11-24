# Step 2: secret isolation and real automated scans

`scripts/scan_secrets.py` installs official gitleaks 8.30.1 for Windows/Linux x64,
verifies a pinned SHA-256 before extracting only the expected executable, and keeps
the tool and reports under ignored `tmp/security/`. No scanner binaries are committed.

It first proves detection using a randomly generated, disposable GitHub-token-shaped
canary. It then scans **all Git refs/history** with `git --log-opts=--all`, and the
production `apps/web/.next` directory. `BUILD_ID` must exist so a dev-only output is
not mistaken for a production bundle. Values are fully redacted; summary output
contains counts and locations only. Inline allow comments are ignored and no
baseline hides old findings. Shallow clones fail the full-history gate; fetch full
history first. Git history is never rewritten.

The initial unrestricted bundle scan flagged 12 copies of Next-generated preview
and server-action signing/encryption keys in server manifests and caches. These
are required framework server metadata, not hosted-provider credentials. Their
origin was checked in the installed Next `dist/build/preview-key-utils.js` and
server-action key generation code. `scripts/gitleaks.toml` retains every built-in
detector and adds three **AND** exceptions for exact server/cache paths, exact
generated field names and exact hex/base64 key shapes. No directory or provider
rule is excluded. The scanner self-tests prove an injected provider token in the
same manifest still fails, and copying a framework key into a client asset still
fails. See [gitleaks configuration](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md#configuration).

From the repository root:

```powershell
cd apps/web
npm run build
cd ../..
python scripts/scan_secrets.py
```

Use `--history-only` for a quick intermediate check; it explicitly leaves the
bundle acceptance gate unverified. A scanner error exits 2; findings exit 1;
zero findings exit 0. Reports and a machine-readable summary remain in
`tmp/security/`. The frontend CI checkout fetches full history and runs this script
after its production build. Remote CI execution requires pushing the branch.

Observed intermediate check: checksum verified, synthetic canary detected, all
34 existing commits scanned with **0 findings**. Final bundle results are recorded
in the verification guide after the final build.

`.env`, frontend `.env.local`, dependencies, models and build output are ignored.
Provider keys stay in backend settings. `PRIVACY_HASH_KEY` is backend-only.
`NEXT_PUBLIC_*` values must never contain credentials; a browser-visible API URL
is not a place for a key. Preserve existing local credentials when copying examples.

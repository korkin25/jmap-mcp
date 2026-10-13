# jmap-mcp

A remote [Model Context Protocol](https://modelcontextprotocol.io) server that
lets Claude and other streamable-HTTP MCP clients read, search, compose, and
organise mail in a [Stalwart](https://stalw.art) JMAP mailbox using the user's
existing [Logto](https://logto.io) identity.

jmap-mcp validates each inbound OAuth access token against Logto's JWKS and
forwards the same token to Stalwart. It stores no mailbox passwords and has no
per-user database or persistent volume.

> [!IMPORTANT]
> The current authentication bridge is specifically tested with Logto and
> Stalwart. Other JMAP or OIDC implementations may work only when their issuer,
> token, audience, claim, and dynamic-registration behaviour matches this
> deployment model.

## Features

The server exposes 47 tools with MCP read-only, destructive, and idempotency
annotations:

- **Identity:** `whoami`, `get_identities`, `create_identity`
- **Read:** mailbox listing and metadata, recent mail and activity, search,
  message and thread reading, unread summaries, headers, and attachments
- **State:** read/unread, flags, keywords, move, and copy
- **Compose:** send, reply, forward, save/update drafts, and attachments
- **Delete:** trash, permanent deletion, empty trash, and empty spam
- **Mailbox management:** create, rename, delete, subscribe, and unsubscribe
- **Profile:** profile, account information, vacation response, and session
  verification
- **Self-audit:** append envelope-only audit notes to a designated mailbox

Sender-controlled bodies, subjects, snippets, addresses, structured headers,
and attachment filenames are treated as untrusted. Returned bodies are wrapped
in `<email:message trust="external">` delimiters, prompt-injection markers are
escaped, and suspicious content is flagged.

## Requirements

- A public HTTPS hostname for jmap-mcp
- A Logto tenant with a public application and API resource
- A Stalwart server with JMAP enabled and an OIDC directory that trusts Logto
- An MCP client supporting streamable HTTP and OAuth 2.1

## Quick start

Copy the environment template, fill in your deployment-specific values, and
start the published Linux/amd64 image:

```sh
cp .env.example .env
docker compose up -d
curl http://127.0.0.1:3000/health
```

The image is published to:

```text
ghcr.io/jlxq0/jmap-mcp:0.2.14
forge.oddie.app/jlxq0/jmap-mcp:v0.2.14
```

> **`linux/amd64` only.** No `arm64` variant is published, so on Apple Silicon,
> AWS Graviton, or any other ARM host `docker pull` fails with
> `no matching manifest for linux/arm64/v8 in the manifest list entries`. Add
> `--platform linux/amd64` to run it there under emulation:
>
> ```sh
> docker pull --platform linux/amd64 ghcr.io/jlxq0/jmap-mcp:0.2.14
> ```

For a direct container invocation:

```sh
docker run --rm -p 3000:3000 --env-file .env \
  ghcr.io/jlxq0/jmap-mcp:0.2.14
```

Expose port 3000 through HTTPS and configure the MCP client with:

```text
https://jmap-mcp.your-domain.example/mcp
```

`GET /health` is public and returns the running package version:

```json
{"status":"healthy","version":"0.2.14"}
```

## Logto and Stalwart setup

The following identifiers must remain aligned:

1. Create a Logto API resource whose indicator is the bare jmap-mcp origin,
   such as `https://jmap-mcp.your-domain.example`.
2. Create a public SPA/native Logto application. Put its client ID in
   `JMAP_MCP_DCR_CLIENT_ID`; no client secret is used by the DCR flow.
3. Register `https://jmap-mcp.your-domain.example/oauth/callback` as the Logto
   application's redirect URI.
4. Put every MCP client's callback URI in `JMAP_MCP_OAUTH_REDIRECT_URIS`.
   HTTPS and native private-use callbacks match exactly. Loopback HTTP
   callbacks match the configured host, path, and query while allowing the
   client to choose an ephemeral local port, as required by RFC 8252.
5. Configure Stalwart's OIDC directory to trust the same Logto issuer, accept
   the jmap-mcp origin as the token audience, and map the token's `username`,
   `email`, or `sub` claim to the mailbox principal.
6. Confirm that a Logto access token for the resource can discover a JMAP
   session directly:

   ```sh
   curl -H "Authorization: Bearer $ACCESS_TOKEN" \
     https://mail.your-domain.example/.well-known/jmap
   ```

The JWT `aud` value accepted by jmap-mcp and Stalwart must contain the exact
bare origin. `JMAP_MCP_RESOURCE_URL` accepts either the origin or an origin
ending in `/mcp`; jmap-mcp canonicalises it to the bare origin and advertises
`<origin>/mcp` through RFC 9728 metadata.

## Configuration

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `JMAP_MCP_RESOURCE_URL` | yes | — | Public origin and required JWT audience; a trailing `/mcp` is accepted and removed |
| `JMAP_MCP_AUTHORIZATION_SERVER` | yes | — | Logto OIDC issuer, normally ending in `/oidc` |
| `JMAP_MCP_STALWART_JMAP_BASE_URL` | yes | — | Stalwart base used for `/.well-known/jmap` discovery |
| `JMAP_MCP_DCR_CLIENT_ID` | for DCR clients | disabled | Pre-provisioned public Logto client returned by `/register` |
| `JMAP_MCP_OAUTH_REDIRECT_URIS` | for OAuth proxy | empty | Comma-separated MCP client callback allowlist; only loopback HTTP ports may vary |
| `JMAP_MCP_BIND_ADDR` | no | `0.0.0.0:3000` | Public HTTP listener |
| `JMAP_MCP_METRICS_BIND_ADDR` | no | `127.0.0.1:9090` | Internal Prometheus listener; never publish it directly |
| `POD_IP` | no | — | Derives the metrics listener as `<pod-ip>:9090` in Kubernetes |
| `JMAP_MCP_RATE_LIMIT_READS_PER_MIN` | no | `60` | Per-identity read quota |
| `JMAP_MCP_RATE_LIMIT_WRITES_PER_MIN` | no | `30` | Per-identity write quota |
| `JMAP_MCP_DOWNLOAD_MAX_BYTES` | no | `5242880` | Maximum attachment download response |
| `JMAP_MCP_UPLOAD_MAX_BYTES` | no | `10485760` | Maximum remote URL attachment fetch |
| `JMAP_MCP_TRUSTED_PROXY_HOPS` | no | `1` | Trusted rightmost `X-Forwarded-For` proxy count; use `0` when directly exposed |
| `JMAP_MCP_EXTRA_FROM_ADDRESSES` | for mailbox aliases | empty | Extra sendable addresses, comma- or whitespace-separated. Stalwart exposes principal aliases only through `x:Account/*`, which need `sysAccountGet`/`sysAccountQuery` permissions an ordinary user token lacks, so aliases must be named here. Role addresses are refused |
| `JMAP_MCP_STALWART_CONNECT_IP` | no | DNS | Optional fixed Stalwart socket address for private routing while preserving TLS host validation |
| `JMAP_MCP_LOGTO_CLIENT_ID` | no | — | Opaque-token introspection client ID; must be paired with the secret |
| `JMAP_MCP_LOGTO_CLIENT_SECRET` | no | — | Opaque-token introspection client secret |
| `JMAP_MCP_LOG_FORMAT` | no | compact | Set to `json` for structured logs |
| `RUST_LOG` | no | application defaults | Standard tracing filter |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | no | disabled | Enables OTLP trace export |
| `OTEL_SERVICE_NAME` | no | `jmap-mcp` | OpenTelemetry service name |

The app fails startup when required values are missing or malformed. When DCR
is configured, an empty redirect allowlist fails authorization closed.

## Security and privacy

jmap-mcp grants an MCP client access to a user's mailbox. Operators and users
must trust the MCP client, model provider, Logto, Stalwart, and the jmap-mcp
operator.

- Access tokens are held in memory and forwarded to Stalwart; raw tokens are
  not logged or persisted.
- Audit logs include the account identity, MCP method, mailbox/message resource
  identifiers, outcome, latency, result count, error class, and the first 16
  hexadecimal characters of a SHA-256 token hash. They exclude message bodies,
  subjects, recipients, attachment contents, and free-form tool arguments.
- Remote attachment fetches require HTTPS, reject private/reserved addresses,
  pin the validated socket address, bypass environment proxies, and enforce
  byte limits.
- In-memory caches, pending OAuth state, rate-limit key maps, MCP sessions, and
  request bodies have hard bounds.
- Release CI runs formatting, Clippy, tests, independent RustSec and OSV
  dependency audits, cargo-deny, container vulnerability scanning, SBOM
  generation, provenance attestation, and keyless image signing.

See [SECURITY.md](SECURITY.md) for reporting and supported-version policy.

## Building and testing

Rust 1.93 is pinned in `rust-toolchain.toml`.

```sh
cargo fmt --all --check
cargo clippy --all-targets --all-features --locked -- -D warnings
cargo test --all-features --locked
cargo audit
cargo deny check bans licenses sources
docker build --platform linux/amd64 -t jmap-mcp:local .
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Release history is maintained in
[CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE).

## External OIDC validation behind a gateway

An OAuth-aware gateway can handle client authorization, protected-resource
metadata and token exchange, then send a backend access token to jmap-mcp.
For example, an Authentik deployment can use:

```dotenv
JMAP_MCP_RESOURCE_URL=https://mcp.your-domain.example
JMAP_MCP_AUTHORIZATION_SERVER=https://auth.your-domain.example/application/o/mail-backend/
JMAP_MCP_STALWART_JMAP_BASE_URL=https://mail.your-domain.example
JMAP_MCP_OIDC_ISSUER=https://auth.your-domain.example/application/o/mail-backend/
JMAP_MCP_OIDC_AUDIENCE=mail-backend-client-id
JMAP_MCP_OIDC_JWKS_URL=https://auth.your-domain.example/application/o/mail-backend/jwks/
JMAP_MCP_STATELESS=true
```

Set all three `JMAP_MCP_OIDC_*` variables together. Partial configuration,
non-HTTPS issuer/JWKS URLs, embedded URL credentials and an empty audience fail
at startup. The issuer is matched exactly, including any trailing slash. JWT
signature, issuer, audience, expiry and subject validation remain enabled.
Stalwart must accept the same backend token and map its subject to the caller's
mailbox. These settings do not implement token exchange or change the built-in
Logto OAuth proxy: the gateway must serve discovery and authorization endpoints.
Only expose jmap-mcp to that gateway, and leave its Logto DCR shim unconfigured.
Keep `JMAP_MCP_ALLOW_STALWART_APP_PASSWORD=false` (the default) for a JWT-only
backend. Enabling that separate option permits HTTP Basic app passwords; it
never makes opaque Bearer tokens valid.

`JMAP_MCP_STATELESS=true` creates a fresh MCP service for each POST, using that
request's authenticated identity. It issues no MCP session ID and disables GET
streams, DELETE and event replay. Supplied session headers on POST are ignored;
they do not select another caller's session. Responses may still use SSE framing
within the individual POST. Configure the gateway's MCP transport as stateless
as well (for agentgateway: `spec.mcp.sessionRouting: Stateless`). Clients requiring
session resumption or server-initiated streams cannot use this mode. Multiple
replicas need no session affinity, although in-memory rate limits remain per
process. Both overrides are opt-in: without them, existing Logto validation and
stateful MCP transport retain their defaults.

## Fork CI and images

`korkin25/jmap-mcp` builds exclusively on the ephemeral
`pure-vps-linux-x64-jmap-mcp` ARC runner. Its dedicated profile mounts no
shared registry credentials or Kubernetes token. Jobs use fresh PVC storage,
remove the checkout even on failure, and ARC deletes the Pod/PVC after each
job. There is no shared Cargo or image cache.

Only the repository owner can trigger push/manual runs or same-repository
PR runs. External fork PRs use `pull_request` and GitHub's
`all_external_contributors` approval policy; review their workflow YAML before
approval. The owner must remain the only write/admin collaborator, because
GitHub allows other write collaborators to approve external workflows too.
An approved external run retains its original actor; owner-only reruns check
`triggering_actor`. There are no privileged PR, comment or workflow-run
triggers. PR jobs get only a read-only token and cannot publish images.

The owner-only release workflow runs on `main` pushes or manual dispatch from
`main`. It repeats formatting, Clippy, tests and dependency scans on the exact
source SHA. Cargo dependencies, Rust and container bases are pinned; apt uses
a fixed Debian snapshot and exact CMake version. A candidate image is pushed
with BuildKit provenance/SBOM, scanned by immutable digest, given an SPDX
artifact and signed with Cosign before promotion to `sha-<full SHA>` and
`latest`. Candidate tags are not accepted releases; a failed scan never
promotes them. Scanning rejects fixable HIGH/CRITICAL image findings;
unfixed findings are excluded from this release gate. Deploy only the accepted
digest recorded in the successful release summary. Roll back by restoring
the previous accepted digest; never rebuild or rely on the mutable `latest`
tag. Registry: `ghcr.io/korkin25/jmap-mcp`.

Repository Actions policy is declared in `.github/repository-policy.json`.
Run `python3 scripts/configure-actions.py` to verify it; the owner can run
`python3 scripts/configure-actions.py --activate` to initialize fork workflows.
It checks approval policy, sole write/admin ownership and read-only default
token permissions before reapplying the Actions enablement setting, then
verifies active workflows. It never changes collaborator or approval settings.
GitHub can initially report `enabled: true` on a new fork with no registered
workflows; activation repairs that state without changing allowed actions.

### Dependency security update (2026-10-13)

The release lockfile upgrades `quinn-proto` 0.11.17 → 0.11.18,
`rustls` 0.23.43 → 0.23.45, `chacha20` 0.10.1 → 0.10.2 and
`rmcp`/`rmcp-macros` 1.8.0 → 2.1.0. This closes
RUSTSEC-2026-0338/0340/0343/0285 and
GHSA-33f5-2c5q-wgwj/9g45-5xwm-f3wc/9pj6-vhgr-3mwh/c9xm-49cp-xcr9;
the yanked ChaCha release is replaced without an advisory suppression.

- [Quinn 0.11.18](https://github.com/quinn-rs/quinn/releases/tag/quinn-proto-0.11.18)
  fixes ACK/datagram panics and backports transport fixes.
- [Rustls 0.23.44](https://github.com/rustls/rustls/releases/tag/v/0.23.44)
  and [0.23.45](https://github.com/rustls/rustls/releases/tag/v/0.23.45)
  tighten malformed handshake handling and include alignment/ECH fixes.
  The new aws-lc ML-DSA default does not affect this lockfile's rustls `ring`
  backend. ChaCha 0.10.2 fixes an SSE4.1 intrinsic used by the SSE2 backend;
  see its [changelog](https://github.com/RustCrypto/stream-ciphers/blob/master/chacha20/CHANGELOG.md).
- [RMCP 2.0](https://github.com/modelcontextprotocol/rust-sdk/releases/tag/rmcp-v2.0.0)
  validates initialization before session allocation and closes the session
  table leak. Its ContentBlock/non-exhaustive model API changes need no source
  adaptation here because this server already uses compatible constructors.
  [RMCP 2.1](https://github.com/modelcontextprotocol/rust-sdk/releases/tag/rmcp-v2.1.0)
  fixes redirect header leakage and preserves stateless protocol negotiation.
  Server features remain unchanged; the OAuth client is not enabled.

All 205 tests pass locally on Rust 1.93.0 with these versions, including
protocol versions 2025-03-26/2025-06-18, token validation, replay rejection,
identity isolation and stateful/stateless quotas. RustSec and OSV report no
vulnerabilities, and cargo-deny passes bans/licenses/sources. Exact-SHA runner
CI and release scanning remain mandatory before accepting an image.

The release runner uses Ubuntu 24.04. The pinned Cosign installer requires
`envsubst`, which the minimal runner does not include. Release extracts the
upstream Ubuntu `gettext-base` 0.21-14ubuntu2 amd64 package into the job's
temporary directory and adds its binaries to the job PATH. Its SHA256 is pinned
from Ubuntu noble's signed `InRelease` / `Packages` metadata; no runner image or
system package configuration is changed. Cosign's upstream binary signature
verification remains enabled. A failed installation leaves only an unaccepted
candidate, without the final `sha-…` or `latest` tags.

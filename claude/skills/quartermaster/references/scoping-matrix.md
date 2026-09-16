# Tech Stack Scoping Matrix

Quartermaster scans workspace files to identify primary frameworks and package ecosystems.

## File Manifest Heuristics

| Manifest / Signature | Detected Technology | Recommended Capabilities |
| :--- | :--- | :--- |
| `pubspec.yaml` | Flutter / Dart | `flutter`, `mobile-dev` |
| `package.json` | Web / Node / JS / TS | `modern-web-guidance`, `chrome-devtools`, `impeccable` |
| `next.config.js` / `next.config.mjs` | Next.js Fullstack Web | `modern-web-guidance`, `impeccable` |
| `vite.config.*` | Modern Frontend Web | `modern-web-guidance`, `chrome-devtools` |
| `pyproject.toml`, `requirements.txt` | Python Application | `uv`, Python testing |
| `Cargo.toml` | Rust Application | Rust guidelines, cargo testing |
| `go.mod` | Go Application | Go concurrency and testing patterns |
| `firebase.json` | Firebase Platform | `firebase` |
| `Dockerfile`, `docker-compose.yml` | Containerized Service | DevOps and container guardrails |

---

## The "I'm Not Sure Yet" Protocol

When no manifests are detected in a brand-new directory:
1. Quartermaster equips the universal Core baseline:
   - `spec`: Invisible spec-driven development.
   - `pr-review`: Reviewer-side adversarial verification.
   - `pm`: Problem definition and requirement scoping.
   - `preflight`: Workspace doctor and readiness verification.
   - `wayfinder`: Multi-session planning for complex efforts.
2. Stack-specific tools remain deferred until code manifests are created.

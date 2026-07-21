# Team Assignments

Each teammate works on their own branch, in their own folder. Read your folder's `README.md` first — it has your scope, stack, and the contract points other folders depend on. Full detail: `docs/SPEC.md`.

| Teammate role | Branch | Folder | Core feature owned |
|---|---|---|---|
| Frontend | `frontend` | `/frontend` | Dashboard management (main multi-target web dashboard) |
| CLI / Agent | `cli` | `/cli` | Live monitoring (log tailing, FIM, ships to core, local ban API) |
| Model / ML | `model` | `/model` | Vulnerability test — anomaly detection (Drain3 + ONNX + Isolation Forest) |
| Dashboard (local) | `dashboard` | `/dashboard` | Dashboard management (thin localhost status site shipped with `/cli`) |
| Core (owner) | `main` | `/backend` | Vulnerability test — scanner/FIM/scoring + shared API surface |

## Workflow
1. `git checkout <your-branch>` — already pushed to origin, tracks your folder.
2. Work only inside your assigned folder. Cross-folder contract changes (function signatures, JSON shapes) get flagged in `/docs`, not silently changed.
3. Open a PR into `main` when a slice is ready — don't work directly on `main`.
4. If you're blocked on another folder's output (e.g. `/cli` waiting on `/model`'s ONNX export), stub the dependency and keep moving — see each README's "Contract you depend on" section.

[![Tests](https://github.com/mystack-cloud/rig/actions/workflows/tests.yml/badge.svg)](https://github.com/mystack-cloud/rig/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/mystack-cloud/rig/graph/badge.svg)](https://codecov.io/gh/mystack-cloud/rig)

# rig

Secure, fast, cost-efficient ephemeral remotes with full local parity—so coding agents and humans can develop and e2e-test for real.

```bash
pip install .
rig init
rig create
```

## Architecture

Run `rig` from your machine, CI/CD, or a control plane: it provisions cloud VMs you can create and dispose anytime, and you work on `/workspace` via agent TTY or editor. SSH/HTTPS reaches VMs through the firewall; HTTPS reaches the provider. The CLI stores env state in S3-compatible object storage.

![rig architecture](docs/architecture.png)

## Cloud providers

| Provider | Status |
| --- | --- |
| [Hetzner Cloud](https://www.hetzner.com/cloud) | Supported (VMs, firewall, snapshots, S3-compatible object storage) |
| [AWS](https://aws.amazon.com/) | Coming next |
| [GCP](https://cloud.google.com/) | Coming next |

## Coding agents

Chosen at `rig init` (`agent.types` in `rig.yml`, same multi-select as git projects: numbers, names, or `all`). Every selected agent is installed and configured on the VM. When more than one is selected, init asks which is the default for `rig attach` (`agent.type`). Pass `--agent` to open another one.

| Agent | `agent.type` | API key |
| --- | --- | --- |
| [OpenCode](https://opencode.ai) | `opencode` (default) | Optional. One agent: `coding_agent_api_key`. Several agents: `opencode_api_key`. Enter skips and uses free Zen models |
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `claude` | One agent: `coding_agent_api_key` (Anthropic). Several agents: `claude_api_key` |
| [Cursor CLI](https://cursor.com/docs/cli/overview) | `cursor` | One agent: `coding_agent_api_key` (`CURSOR_API_KEY`). Several agents: `cursor_api_key` |

Each selected agent is asked for its own key. Scaffolds land under `.rig/.opencode/`, `.rig/.claude/`, and `.rig/.cursor/` (plus shared `AGENTS.md`). Independent of `editor` (local IDE for `rig dev`).

## IDEs

`rig dev` opens the remote `/workspace`. Default is local editor + Remote-SSH; `--browser` uses code-server on the VM.

| Mode | Clients |
| --- | --- |
| Remote-SSH (default) | VS Code (`code`), VS Code Insiders (`code-insiders`), Cursor (`cursor`), VSCodium (`codium`) |
| Browser (`--browser`) | code-server (password: vaulted `vscode_browser_password`) |

Chosen at `rig init` (`editor` in `rig.yml`), or override with `--editor`. Local Cursor/VS Code talks to the VM over SSH (no Cursor install on the VM). Browser login: `rig vars decrypt vscode_browser_password`.

## Layout

`rig init` writes commit-friendly files into the current directory (including a subdirectory of a git repo):

```text
rig.yml                 # workspace manifest (vm, agent, playbooks, repos)
.gitignore              # adds .rig/collections, roles, inventory (via init)
.rig/
  provision.yml         # managed; create base environment (cached)
  configure.yml         # user; image/service customizations (cached)
  authorize.yml         # managed; inject credentials (never snapshotted)
  materialize.yml       # user; populate /workspace after authorize
  finalize.yml          # user; destruction hooks before managed destroy
  destroy.yml           # managed; teardown system resources before VM delete
  vars.yml              # Shared Ansible vars (vaulted with shared data key)
  vars.<identity>.yml   # Personal secrets + master-key wraps (committed)
  requirements.yml      # Galaxy collections/roles
  AGENTS.md             # agent instructions
  .opencode/ | .claude/ | .cursor/  # agent config + MCP
  inventory.yml         # generated at create/apply (gitignored)
  collections/ roles/   # Galaxy installs (gitignored)
```

`rig.yml` defaults (edit to configure):

```yaml
vm:
  type: cax11
  availability_zone: hel1
  image: ubuntu-24.04
firewall:
  mode: dynamic_add   # open | static | dynamic_replace | dynamic_add
  allowed_ips: []     # static allow-list; also merged into dynamic modes
  ports: []           # extra inbound ports, e.g. [8080, "3000-3001", {port: 53, protocol: udp}]
agent:
  type: opencode          # default for `rig attach`; or claude | cursor
  # types: [opencode, claude, cursor]  # install every listed agent
editor: code                  # code | code-insiders | cursor | codium
playbooks:
  provision: .rig/provision.yml
  configure: .rig/configure.yml
  authorize: .rig/authorize.yml
  materialize: .rig/materialize.yml
  finalize: .rig/finalize.yml
  destroy: .rig/destroy.yml
```

Firewall modes:

| Mode | Behavior |
| --- | --- |
| `open` | SSH/ICMP from anywhere (`0.0.0.0/0`) |
| `static` | Only `allowed_ips` (no client detection) |
| `dynamic_replace` | Set allow-list to current CLI public IP (+ `allowed_ips`); drops previous IPs |
| `dynamic_add` (default) | Keep existing allow-list entries; add current CLI public IP if missing |

Attach / apply / dev / destroy refresh the firewall for dynamic modes when the client IP changes, and keep `ports` in sync.

`firewall.ports` opens extra inbound listeners with the same source-IP policy as SSH (TCP by default; use `{port, protocol}` for UDP).

Remote project files live under `/workspace` (not `/root`).

## Lifecycle

```text
init  →  create  →  attach | dev | apply  →  destroy
              ↓
         snapshots (reuse on next create)

create playbooks:
  provision → configure → [snapshot] → authorize → materialize

destroy playbooks:
  finalize → destroy → (delete VM / firewall / key)
```

| Stage | File | Owner | Meaning |
| --- | --- | --- | --- |
| **provision** | `provision.yml` | managed | Create managed base environment |
| **configure** | `configure.yml` | user | Apply user image/service customizations (cached) |
| **authorize** | `authorize.yml` | managed | Inject credentials and establish access |
| **materialize** | `materialize.yml` | user | Populate `/workspace` |
| **finalize** | `finalize.yml` | user | Run user-defined destruction hooks |
| **destroy** | `destroy.yml` | managed | Remove managed environment (before CLI deletes VM) |

| Command | What happens |
| --- | --- |
| **init** | Scaffold `rig.yml` + `.rig/`. Collect Hetzner creds, repo PATs, agent choices and a key per agent. |
| **create** | Boot VM (base/system snapshot). Run provision → configure → authorize → materialize. Snapshot after **configure** only. |
| **apply** | Default: authorize → materialize. Flags: `--provision` / `--configure` / `--authorize` / `--materialize`. |
| **attach** | SSH TTY into `opencode` / `claude` / Cursor `agent` on `/workspace`. `--agent` picks among installed agents. |
| **dev** | Open VS Code/Cursor via Remote-SSH on `/workspace` (or `--browser` for code-server). |
| **destroy** | Run finalize → destroy playbooks, then delete VM / firewall / SSH key. |

Put secret-free installs in `configure.yml` (cached). Put clone/setup that needs credentials in `materialize.yml`.

Last env name is remembered in `/tmp/.rig/last-env` (used when `name` is omitted).

After you leave an agent TTY, rig captures the printed session / resume id (when the agent prints one) under `/tmp/.rig/sessions/<env>`. A later bare `rig attach` reopens that session (`--session` for OpenCode, `--resume` for Claude Code / Cursor). Pass `-c` / `--session` / `--resume` to override.

### Snapshots

| Boot source | Skips |
| --- | --- |
| `rig-{version}-{hash}` | provision + configure (`authorize` + `materialize` still run) |
| base image | nothing |

**System hash** = var map (`coding_agent_type`, `coding_agent_types`, `git_providers`, `code_server_*`, `workspace_root`) + `provision.yml` + `configure.yml`. Secrets and `authorize.yml` / `materialize.yml` are not included.

Override with `--force-playbooks` / `--force-system` (force provision+configure) / `--force-workspace` (force materialize).

`rig cache list|clear` — show snapshots (and for clear, confirm then delete):

| Flags | Selection |
| --- | --- |
| (default) | unused system (+ legacy workspace) for current project |
| `--system` | system only |
| `--workspace` | legacy workspace snapshots (current project) |
| `--all` | include current (not only unused) |
| `--all --system` / `--all --workspace` | all of that kind, including current |

`-y` skips the confirmation on clear.

## CLI

Global: `-v` debug · `-q` warnings/errors only · `--version`

| Command | Args | Notes |
| --- | --- | --- |
| `init` | | Interactive scaffold |
| `create` | `[--name]` `[--type]` `[--availability-zone]` `[--image]` `[--no-attach]` `[--force-playbooks\|--force-system\|--force-workspace]` | VM defaults from `rig.yml`; flags override. `--region` aliases `--availability-zone`. |
| `apply` | `[name]` `[--provision\|--configure\|--authorize\|--materialize]` | Default: authorize then materialize |
| `attach` | `[name]` `[-c\|--continue]` `[-s\|--session ID]` `[--resume [ID]]` `[--agent opencode\|claude\|cursor]` `[-- …agent args]` | Reopens last remembered session by default; `--agent` picks which installed agent |
| `dev` | `[name]` `[--path /workspace]` `[--browser]` `[--editor code\|cursor\|…]` | Remote-SSH by default; `--editor` overrides `editor` in `rig.yml` |
| `list` | | Lists envs, or `No remote environments` |
| `destroy` | `[name …]` | Runs finalize then destroy playbooks first; multi-name OK |
| `cache` | `list\|clear` `[--system\|--workspace] [--all] [-y]` | List or clear; unused by default, `--all` includes current |
| `vars encrypt` | `[--stdin-name VAR]` `[--personal]` | Vault into shared or identity vars (after master-key unlock) |
| `vars decrypt` | `[VAR]` | Decrypt from shared or identity vars |
| `vars list` | | List vaulted names (`shared` / `identity`) |
| `vars export-shared-key` | | Print shared data key for teammate onboarding |

## Ansible variables

Playbooks load `.rig/vars.yml` then `.rig/vars.{identity}.yml` (personal wins), then runtime `rig_*` extras. Prefer `{{ rig_env_name }}` over hard-coding.

| Variable | Meaning |
| --- | --- |
| `rig_env_name` | Env / VM name (`dev-…`) |
| `rig_workspace_name` | `rig.yml` `name` |
| `rig_vm_name` | VM name (usually same as env) |
| `rig_vm_type` | Hetzner server type |
| `rig_availability_zone` | Hetzner location (`hel1`, …) |
| `rig_vm_image` | Boot image or snapshot id |
| `rig_vm_ip` | Public IPv4 |
| `rig_vm_id` | Hetzner server id |
| `rig_agent_type` | Default attach agent (`opencode`, `claude`, or `cursor`) |
| `rig_agent_types` | Agents installed on the VM |
| `rig_workspace_root` | `/workspace` |
| `rig_version` | Installed `rig` package version |
| `rig_boot_source` | `base` \| `system` \| `workspace` |
| `rig_action` | `create` \| `apply` \| `destroy` |
| `rig_project_dir` | Local project path |
| `rig_ssh_key_name` / `rig_ssh_key_path` | Local key under `/tmp` |
| `rig_firewall_name` | Firewall resource name |
| `rig_repos` | `[{name, url, path}, …]` (no secrets) |
| `rig_git_providers` | e.g. `github`, `gitlab` |

Also available from vars files (defaults): `workspace_root`, `coding_agent_type`, `coding_agent_types`, `git.clone_repos`. On `rig init`, git PATs and each coding agent API key default to **personal** storage in `vars.{identity}.yml` (you are asked to confirm once); shared secrets such as `vscode_browser_password` live in `vars.yml`.

`vscode_browser_password` is auto-generated (vaulted) for code-server browser login (`rig dev --browser`). Reveal with `rig vars decrypt vscode_browser_password` (also printed when opening browser mode).

## Credentials

| Source | Purpose |
| --- | --- |
| `~/.rig/config` | Hetzner token (+ optional S3) and `identity`. Profile via `RIG_PROFILE`. Env vars override. |
| Personal master key | Prompted on init/unlock; **never stored**. Unwraps data keys from `vars.{identity}.yml`. |
| `rig_identity_data_key` / `rig_shared_data_key` | Master-key wraps inside `vars.{identity}.yml` (committed). |
| `/tmp/.rig/.personal-data-key` / `.shared-data-key` | Materialized Ansible vault passwords after unlock (tmpfs). |
| `/tmp/<env>-key` | Per-env SSH private key (attach / apply / destroy finalizers). |

`RIG_IDENTITY` overrides the configured identity. Teammates joining an existing workspace paste the shared data key once (`rig vars export-shared-key` from an unlocked machine).

OpenCode without an API key uses free Zen models. With a key, config switches to the paid provider path. When several agents are selected, keys are `opencode_api_key`, `claude_api_key`, and `cursor_api_key` (`RIG_OPENCODE_API_KEY`, `RIG_ANTHROPIC_API_KEY`, `RIG_CURSOR_API_KEY`). A single agent still uses `coding_agent_api_key` (`RIG_CODING_AGENT_API_KEY`).

## Tests

```bash
python -m pytest tests/ -m "not requires_credentials"
```

## License

MIT

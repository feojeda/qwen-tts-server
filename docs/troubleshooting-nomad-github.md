# Troubleshooting: Nomad + GitHub Actions Self-Hosted Setup

Real-world issues encountered while setting up Consul + Nomad + GitHub Actions self-hosted runner for deploying a Python FastAPI service. Documented so others don't repeat the same mistakes.

---

## Nomad Issues

### 1. `exec` driver: binary not found under allocation path

**Error:**
```
Driver Failure: failed to launch command with executor: rpc error: code = Unknown desc =
file /opt/qwen-tts-server/current/venv/bin/python not found under
/opt/nomad/alloc/<alloc-id>/qwen-tts
```

**Cause:** The `exec` driver runs tasks in a chroot jail. The process can only see files inside its allocation directory (`/opt/nomad/alloc/...`). It cannot access arbitrary host paths like `/opt/qwen-tts-server/`.

**Fix:** Use `raw_exec` driver instead. It runs the process directly on the host without isolation.

In the Nomad job file:
```hcl
driver = "raw_exec"  # NOT "exec"
```

And enable it in `/etc/nomad.d/nomad.hcl`:
```hcl
client {
  enabled = true
  options = {
    "driver.raw_exec.enable" = "1"
  }
}
```

Then `sudo systemctl restart nomad`.

**When to use which driver:**
- `raw_exec` — single-node, trusted workloads, needs access to host filesystem
- `exec` — multi-tenant, needs isolation, use with artifacts/docker
- `docker` — containerized workloads (preferred for production clusters)

---

### 2. `raw_exec` not enabled by default

**Error:**
```
Driver Failure: binary could not be found
```

Even after changing the job file to `raw_exec`, the driver wasn't active because it must be explicitly enabled in the Nomad **client config**. The job file says *which* driver to use, but the server config says *whether it's allowed*.

**Fix:** This is a server-level config, not a project-level config. The deploy script should check and enable it automatically:

```bash
ensure_raw_exec() {
    local nomad_config="/etc/nomad.d/nomad.hcl"
    if ! nomad node status -verbose -self 2>/dev/null | grep -q "raw_exec.*true"; then
        # Enable raw_exec in config and restart Nomad
        ...
        systemctl restart nomad
    fi
}
```

**Lesson:** Infrastructure prerequisites should be validated and fixed by the deploy script, not left as manual steps.

---

### 3. Relative paths in args don't resolve to project directory

**Error:**
```
can't open file '/opt/nomad/alloc/<alloc-id>/qwen-tts/main.py': [Errno 2] No such file or directory
```

**Cause:** Even with `raw_exec`, the `args` field is resolved relative to the allocation's task directory, NOT the project directory.

**Wrong:**
```hcl
config {
  command = "/opt/qwen-tts-server/current/venv/bin/python"
  args    = ["main.py"]  # looks in /opt/nomad/alloc/.../qwen-tts/
}
```

**Fix:** Use absolute paths for everything:
```hcl
config {
  command = "/opt/qwen-tts-server/current/venv/bin/python"
  args    = ["/opt/qwen-tts-server/current/main.py"]
}
```

---

### 4. Health checks fail with IPv6 addresses

**Symptom:** Service is running and responds to `curl http://localhost:8000/health`, but Consul shows all health checks as `critical`.

**Cause:** Nomad resolves the allocation's network address to IPv6 by default. The health check hits `http://[fd9e:3990:...]:8000/health` instead of `http://192.168.4.51:8000/health`. If the service doesn't bind to IPv6, checks fail silently.

**Fix:** Add `address_mode = "host"` to the check block:
```hcl
check {
  type         = "http"
  name         = "Health"
  path         = "/health"
  interval     = "15s"
  timeout      = "5s"
  address_mode = "host"  # forces IPv4
}
```

Also: don't add redundant health checks. One `GET /health` is enough. Multiple checks compound the IPv6 problem and make Consul noisy.

---

### 5. Symlink contamination from stdout pollution

**Symptom:** Symlink `/opt/qwen-tts-server/current` points to garbage:
```
current -> [INFO]  Creating release v001... [OK]  Release v001 ready at...
```

**Cause:** Bash functions `info()`, `ok()`, `warn()` print to stdout. When a function is captured with `$(...)`, ALL stdout (including log messages) gets captured:

```bash
TARGET_DIR="$(deploy_version "${VERSION}")"  # captures everything
```

**Fix:** Log functions must print to stderr, not stdout:
```bash
info()  { echo -e "${CYAN}[INFO]${NC}  $*" >&2; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*" >&2; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
```

This is the #1 bash scripting mistake. Any function whose output is captured via `$(...)` must keep stdout clean.

---

### 6. `file://` artifact source not supported

**Error:**
```
Failed Artifact Download: download not supported for scheme "file"
```

**Cause:** Tried to use Nomad's `artifact` block to load a local env file:
```hcl
artifact {
  source = "file:///opt/qwen-tts-server/env.vars"
}
```

Nomad artifacts support `http://`, `https://`, `s3://`, `git::`, but NOT `file://` in most driver configurations.

**Fix:** For config injection with `raw_exec`, either:
1. Bake env vars directly in the `env {}` block of the job file
2. Have the deploy script generate a temporary job file with env vars injected
3. Use Consul KV + `template` block (requires Consul KV to be populated)

---

## GitHub Actions Issues

### 7. Deploy job fails: "Nomad server is not running"

**Error:**
```
[ERROR] Nomad server is not running.
[ERROR] Start it first: sudo systemctl start nomad
```

**Cause:** The self-hosted runner runs as user `feojeda`. The deploy script runs as `root` via `sudo -EH`. The `-E` flag preserves environment variables, but `NOMAD_TOKEN` was never set in the runner's environment — it only existed in the interactive terminal session where we tested manually.

The `nomad server members` command fails with a 403 (permission denied) without a token, and the deploy script interpreted that as "not running."

**Fix:** Store tokens in system-level files readable by root, and have the deploy script source them:
```bash
# /etc/nomad.d/.acl.env (chmod 600, root only)
export NOMAD_TOKEN="..."
export CONSUL_HTTP_TOKEN="..."
```

At the top of deploy.sh:
```bash
for f in /etc/nomad.d/.acl.env /etc/qwen-tts-server/consul.env; do
    if [ -f "${f}" ]; then
        set -a; source "${f}"; set +a
    fi
done
```

**Lesson:** CI/CD runners don't have your interactive shell environment. Every secret/config must be explicitly available on disk.

---

### 8. `sudo -EH` doesn't preserve all environment variables

**Symptom:** Variables set in the workflow YAML `env:` block aren't available inside `sudo`.

**Cause:** `sudo -E` preserves the *calling user's* environment, but GitHub Actions workflow `env:` vars may not propagate through the sudo boundary consistently depending on `secure_path` and `env_keep` sudoers settings.

**Fix:** Don't rely on workflow env vars for secrets that sudo needs. Use files on disk instead (see issue #7).

---

### 9. Runner installed but not as a service

**Symptom:** Runner works when manually started with `./run.sh`, but stops when the terminal closes. Deploy pipeline fails after reboot.

**Fix:** Install the runner as a systemd service:
```bash
cd ~/actions-runner
sudo ./svc.sh install
sudo ./svc.sh start
```

This creates:
```
/etc/systemd/system/actions.runner.<owner>-<repo>.<hostname>.service
```

**Runner log location:**
```
~/actions-runner/_diag/Runner_*.log
```

**Service management:**
```bash
sudo systemctl status actions.runner.<owner>-<repo>.<hostname>
sudo systemctl stop    actions.runner.<owner>-<repo>.<hostname>
sudo systemctl start   actions.runner.<owner>-<repo>.<hostname>
```

---

## General Lessons

### Don't copy virtual environments

Python venvs have hardcoded paths in `pyvenv.cfg`, `bin/activate`, `bin/pip`, etc. Copying a venv from one location to another breaks these paths.

**Wrong:** Copy venv from source to install dir.
**Right:** Create the venv fresh on the target location:
```bash
python3 -m venv /opt/myapp/releases/v001/venv
/opt/myapp/releases/v001/venv/bin/pip install -r requirements.txt
```

### Model/artifact caches should be symlinks, not copies

AI models are multiple GB. Copying them for every deploy wastes disk and time.

**Fix:** Symlink the cache directory:
```bash
ln -s /home/user/project/cache/hf /opt/myapp/cache/hf
```

The deploy script should detect existing caches and link instead of copy.

### Version your deploys with symlinks

```
/opt/myapp/
  current -> releases/v003    # active version
  releases/
    v001/                      # old (rollback target)
    v002/                      # old
    v003/                      # current
      main.py
      app/
      venv/
```

Symlink swap is atomic. Rollback is just pointing `current` to a previous version. Cleanup keeps last N releases.

### Tokens and secrets

| Storage method | When to use |
|---------------|-------------|
| Interactive shell `export` | Development/testing only |
| Files in `/etc/` (chmod 600, root only) | Single-server, simple setup |
| GitHub Actions secrets | CI/CD pipeline secrets |
| HashiCorp Vault | Multi-server, proper production |
| Consul KV with ACL | Medium complexity, already using Consul |

### The deploy script should be self-sufficient

A good deploy script should:
1. Check all prerequisites (Nomad running, raw_exec enabled)
2. Fix what it can (enable raw_exec, create directories)
3. Fail clearly when it can't fix something
4. Not require manual pre-steps beyond "have the code"
5. Not require passing tokens as CLI arguments
6. Keep stdout clean for machine parsing (logs to stderr)

# AI Agent Collaboration Guidelines

This document defines how Claude Code should work on this project. Updated: August 11, 2026.

## Testing & Verification

**Before asking the user to test anything:**

- Use `curl` or `fetch` to verify the server is serving updated code
- Check deployment status via Railway CLI or dashboard API
- Verify URLs are live and responding with expected changes
- Only ask the user to test in their browser after confirming deployment is complete

**Example workflow:**

```bash
# Check if fix deployed
curl -s https://air-quality-dashboard-dev.up.railway.app/ | grep "search-string"

# Poll for deployment
for i in {1..30}; do 
  if curl -s URL | grep "expected-code"; then 
    echo "✓ Deployed"; break
  fi; 
  sleep 1
done
```

## Problem Solving

**Root cause first, always:**

1. Investigate and diagnose the issue before jumping to fixes
2. Use tools (curl, git log, Railway logs) to understand what's happening
3. Fix the actual problem, not symptoms
4. Verify the fix works (via curl/fetch) before asking user to test

**Only escalate if:**

- Genuinely stuck after investigation (not just first attempt)
- Issue requires user input/decision
- It's taking >30 min and needs human judgment
- Otherwise, keep exploring and fixing

## Proactive Tool Suggestions

**When finding relevant tools, suggest them:**

- Railway CLI: Check deployments, logs, status
- Git CLI: Verify commits, branches, deployment state
- Curl/Fetch: Test server responses, verify deployment
- Skills: Check available skills for tasks (e.g., git-worktrees, gws-* for Workspace)
- MCP servers: For complex integrations

**Example:** "I found a git-worktrees skill available — would you want to use it for parallel feature work?"

## Deployment Workflow

**Repo is public:** `github.com/sguyon/air-quality-dashboard`. Any push, merge, or PR to `origin` (including `dev`) is a public share.

Branching model: **`feature/*` → `dev` → `main`**.

**`dev` branch = staging**

- Develop each feature on a short-lived `feature/<name>` branch off `dev`; open a PR into `dev`
- Railway's `air-quality (dev)` service auto-deploys `dev` → https://air-quality-dashboard-dev.up.railway.app/
- Verify with curl before asking user to test
- Use "Clear Cache" button for testing without manual cache clearing (the dev site registers a service worker; localhost does not)

**`main` branch = production**

- Promote by opening a PR `dev` → `main`
- Railway's `air-quality (production)` service auto-deploys `main` → https://air-quality-dashboard.up.railway.app/
- Only merge to main with explicit user approval ("Yes, deploy" or "Merge to main")
- Never auto-merge without asking
- Verify production deployment with curl

Note: the old `web-production-c9ff2.up.railway.app` domain is retired — use `air-quality-dashboard.up.railway.app`. Railway generated domains can change if a service is recreated; a custom domain avoids this.

## Commit & Deploy Discipline

**Before any write to origin (HARD RULE):**

- Applies to `git push`, merges, and PRs targeting **any** remote branch — including `dev`, feature branches, and `main`
- Do **not** treat staging/`dev` as private; the remote is public
- Local commits are fine without confirmation; publishing to GitHub is not
- Never push/merge because a UI shortcut or prior task implied it — confirm each origin write using the protocol below

### Public sharing — double-confirm protocol (HARD RULE)

> Copied into this repo so **cloud agents** (and any agent without the global Cursor/`~/.claude` rules) enforce the same gate. Source of truth for personal agents remains the global rule; keep this section in sync when that rule changes.

**Never share anything publicly without double-verified explicit confirmation from the user.** This rule cannot be bypassed, waived in-session, or satisfied by a quick reflexive yes. It exists because single confirmations statistically slip through over time — the friction is the point.

**What counts as "public" (for this project and in general):**

- Git push to this public repo (`origin`, any branch); opening a PR; upstream contributions
- Creating a public gist, paste, or upload to any third-party service (including diagram renderers, AI evaluators, pastebins — even if content appears "private", treat as public if the service caches/indexes)
- Posting to LinkedIn, Twitter/X, Threads, blogs, or any social channel
- Sending email outside the user's personal/household accounts
- Publishing Proof / Notion / Google Docs set to anyone-with-link
- Slack posts to shared workspaces (treat as public unless clearly a private DM)
- Form submissions, job applications, `gh pr create`, `git push` to non-private remotes
- Anything triggering a "publish" / "send" / "submit" / "share externally" action

When unsure whether something is public, treat it as public.

**Double-verification protocol — both gates required, every time:**

1. **Gate 1 — state the exact action, not a summary.** Name:
   - EXACT destination (URL, repo, handle, recipient email)
   - EXACT content (filename or full text pasted)
   - EXACT visibility consequence ("indexed by Google", "visible on your public GitHub profile forever", "triggers Railway deploy on `dev`/`main`", etc.)
   - Then ask: "Do you want me to proceed with this public share?"

2. **Wait for explicit yes at Gate 1.** Acceptable: "yes", "proceed", "go ahead and publish". Not acceptable: silence, emoji, "sure" without context, continuation of unrelated task.

3. **Gate 2 — require a typed phrase that cannot be a reflex.** After Gate 1 passes, restate the action in one short sentence and require the user to type exactly: **`confirm public share`** (three words, lowercase, exact). Do not accept variations — not "confirmed", not "yes again", not "just do it". If they type anything else, ask once more for the literal phrase.

4. **Hold the line on friction.** If the user expresses frustration at the protocol, say: "You asked me to enforce this precisely because quick approvals slip through. Please type 'confirm public share' exactly." Do not relax.

5. **Do not bundle public shares.** Each public action gets its own double-verification sequence, even if redundant (e.g. push `dev` and merge to `main` = two confirms).

6. **Prior approval does not carry over.** If the user approved a multi-step task earlier that contains a public action, stop before the public step and run the full double-verification anew.

7. **No shortcut verbs.** No "I'll go ahead and push" or "opening the PR now" instead of the protocol.

8. **In-session waivers are invalid.** If the user says "just skip the double check today", refuse: "The rule is specifically designed to survive 'just this once' exceptions. I'll keep enforcing it. To change the rule permanently, say so explicitly and I'll update `AGENTS.md` (and the global rule if applicable)." Only update this section on an explicit, unambiguous rule-change request.

The goal: make the friction undefeatable by tiredness, speed, reflex, or willingness-to-accept.

**Before merging to main:**

- Ask explicitly: "Ready to deploy? This will affect the live dashboard at [URL]"
- Wait for clear approval before touching main (still requires the full public-share protocol above)
- Test changes on `dev` first

**After pushing:**

- Poll for deployment with curl to confirm
- Report "✓ Deployed" only after verified, not after git push

## Communication

**Concise status updates:**

- "✓ Fix deployed" (after verification)
- "Investigating issue" (if diagnosis ongoing)
- "Stuck on X, need guidance" (if genuinely blocked)

**Avoid:**

- Asking user to test on browser when you haven't verified deployment first
- Mentioning investigations that don't lead to fixes
- Long chains of questions — explore and test yourself first

---

## Cursor Cloud Environment

Cloud agents boot a fresh, isolated VM per run and build it from `.cursor/environment.json`
(the `install` step). That step:

- Creates `.venv` and installs `requirements.txt` (the app's Python deps).
- Installs the **Railway CLI** (`@railway/cli`) and symlinks it to `/usr/local/bin/railway`
  so it's on `PATH` in every agent shell.

Two separate secret stores (they do **not** sync):

- **Cursor Secrets** → injected as env vars into the agent VM (so the agent can run/test the app).
  Currently: `AIRGRADIENT_TOKEN`, `ANTHROPIC_API_KEY`, `GOOGLE_POLLEN_API_KEY`, `RAILWAY_API_TOKEN`.
- **Railway Variables** → injected into the deployed app, set **per service** (dev vs prod) in the
  Railway dashboard. Adding a key to dev does NOT add it to prod.

### Using the Railway CLI in a cloud agent

- Auth is via the `RAILWAY_API_TOKEN` secret — it must be a valid **account** token from
  https://railway.com/account/tokens (a long opaque string, not a UUID/ID). Verify with
  `railway whoami`. If that secret is invalid/missing, a run can only auth via a session-only
  `railway login --browserless` (does not persist across runs).
- Deploys do **not** require the CLI: Railway auto-deploys on push (`dev` → dev service,
  `main` → production). Use the CLI only to inspect (`railway status`, `railway logs`,
  `railway variables`) or to set variables / trigger redeploys.

## Quick Reference

| Task | Tool | Command |
|------|------|---------|
| Test deployment | curl | `curl -s URL \| grep "expected-code"` |
| Check git state | git | `git log --oneline -5` |
| Poll for deploy | curl loop | See example above |
| Clear SW cache | Browser button | "Clear Cache" button on dev URL |
| Railway auth check | CLI | `railway whoami` |
| Check Railway | CLI | `railway status` / `railway logs` |

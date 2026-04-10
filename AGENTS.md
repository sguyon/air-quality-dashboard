# AI Agent Collaboration Guidelines

This document defines how Claude Code should work on this project. Updated: April 10, 2026.

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

**v2 branch = testing/staging**
- Work on `v2/ai-insights-redesign` branch
- Test on https://air-quality-dashboard-dev.up.railway.app/
- Verify with curl before asking user to test
- Use "Clear Cache" button for testing without manual cache clearing

**main branch = production**
- Only merge to main with explicit user approval ("Yes, deploy" or "Merge to main")
- Never auto-merge without asking
- Verify production deployment with curl

## Commit & Deploy Discipline

**Before merging to main:**
- Ask explicitly: "Ready to deploy? This will affect the live dashboard at [URL]"
- Wait for clear approval before touching main
- Test changes on v2 branch first

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

## Quick Reference

| Task | Tool | Command |
|------|------|---------|
| Test deployment | curl | `curl -s URL \| grep "expected-code"` |
| Check git state | git | `git log --oneline -5` |
| Poll for deploy | curl loop | See example above |
| Clear SW cache | Browser button | "Clear Cache" button on dev URL |
| Check Railway | CLI | `railway deployment list` |


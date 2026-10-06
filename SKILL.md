---
name: hermes-fix
description: Fix Hermes Agent weaknesses: context death spiral, config bugs, silent failures, security vulnerabilities, skill issues.
category: devops
---

# Hermes Fix Skill

This skill fixes known Hermes Agent weaknesses and vulnerabilities.

## Trigger
Use when Hermes Agent experiences:
- Context compression failures or death spiral
- Config key mismatches
- Silent failures on skill/config loading
- Prompt injection concerns
- Skill quality issues
- Sycophantic self-evaluation
- Global state race conditions

## Fixes

### 1. Context Death Spiral Fix
**Problem**: Three-layer compression fails simultaneously → infinite API disconnect loops.

**Solution**: Enable aggressive compression monitoring in plugin:
```yaml
context:
  aggressive_compression: true
  compression_threshold: 0.6
  max_tokens_before_compression: 80000
  death_spiral_detection: true
  auto_recovery: true
```

**Commands**:
```bash
# Check context health
hermes context health

# Check for death spiral
hermes context check-death-spiral

# Emergency recovery
hermes recovery emergency
```

### 2. Config Key Mismatch Fix (Issue #8015)
**Problem**: Code reads `context_length`, docs say `context_window`.

**Solution**: Plugin validates and auto-fixes at startup:
```yaml
config_validation:
  enforce_context_keys: true
  validate_on_startup: true
  validate_on_reload: true
```

**Manual fix** - Set BOTH keys in `~/.hermes/config.yaml`:
```yaml
model:
  context_length: 100000
  context_window: 100000  # Must match!
```

**Validation**:
```bash
hermes config validate --strict
```

### 3. Prompt Injection Hardening (F-1, F-2)
**Problem**: 60% success rate for indirect injection → RCE via untrusted content.

**Solution**: Structural separation + out-of-band confirmation:
```yaml
injection_protection:
  enabled: true
  structural_separation: true
  require_out_of_band_confirmation: true
  scan_untrusted_content: true
  block_shell_from_untrusted: true
```

**Key rules**:
- Untrusted content cannot directly authorize shell/file tools
- Shell commands during untrusted content require explicit confirmation
- Content scanned for injection patterns before processing

**Scan for injection**:
```bash
hermes security scan-injection --all
```

### 4. Fail-Silent Elimination
**Problem**: Critical ops swallow exceptions, return neutral values.

**Solution**: Enable validation and loud failure logging:
```yaml
validation:
  enabled: true
  log_all_failures: true
  fail_loud_on_critical: true
  skill_scan_on_load: true
  config_validate_on_change: true
```

**Key validations added**:
- Skill frontmatter truncation detection (< 2000 chars)
- Skill size limits
- Config key validation on every change
- Tool dispatch validation

### 5. Skill Quality Gates (Issue #7390, #54722)
**Problem**: Auto-generated skills encode wrong approaches; injection persists.

**Solution**: Disable auto-generation, require human review:
```yaml
skills:
  auto_generate: false
  human_review_required: true
  scan_for_injection: true
  scan_for_truncation: true
  max_skill_size_chars: 50000
  weekly_audit: true
  audit_schedule: "0 3 * * 0"
```

**Audit**:
```bash
# Full skill audit
hermes skill audit --full

# Quality audit
hermes skill audit-quality --all
```

### 6. Global State Protection (Issue #7798)
**Problem**: Process-global state causes race conditions in parallel subagents.

**Solution**: Thread locks during subagent execution:
```yaml
global_state:
  protect: true
  warn_on_stale_read: true
  lock_during_subagent: true
```

### 7. Token Budget Enforcement
**Problem**: 46% context consumed by tool definitions (8,759 tokens/request).

**Solution**: Minimal toolsets by default:
```yaml
token_budget:
  enabled: true
  max_tool_definition_tokens: 5000
  prefer_cli_over_gateway: true
  minimal_toolsets_by_default: true
```

**Workaround**:
```bash
hermes toolset minimal
```

### 8. Sycophantic Evaluation Guard
**Problem**: Agent rates own work as successful regardless of quality.

**Solution**: Disable auto-evaluation, require human review:
```yaml
evaluation:
  auto_evaluate: false
  human_review_required: true
  min_confidence_threshold: 0.9
```

### 9. Memory Bounds Protection
**Problem**: MEMORY.md caps at 2,200 chars, USER.md at 1,375 chars.

**Solution**: Warning threshold, no auto-compact:
```yaml
memory:
  max_chars: 2200
  auto_compact: false
  warn_at_percent: 80
```

**Workaround**: Consolidate aggressively, use skills for procedural knowledge.

### 10. Recovery Commands
```bash
# Full system health check
hermes doctor --full

# Emergency recovery (clears context, resets session)
hermes recovery emergency

# Specific recovery
hermes recovery context
hermes recovery session
hermes recovery skills
```

## Monitoring Metrics

The plugin tracks:
- `context_health`: OK/WARNING/CRITICAL
- `death_spiral_risk`: LOW/MEDIUM/HIGH
- `config_valid`: true/false
- `injection_protection_active`: true/false
- `skill_quality_score`: 0-100
- `token_budget_usage`: percentage
- `global_state_health`: OK/WARNING
- `memory_usage`: percentage

## Full Configuration Template

```yaml
# ~/.hermes/config.yaml
plugins:
  hermes_fix_plugin:
    enabled: true
    config:
      context:
        aggressive_compression: true
        compression_threshold: 0.6
        max_tokens_before_compression: 80000
        death_spiral_detection: true
        auto_recovery: true
      config_validation:
        enforce_context_keys: true
        validate_on_startup: true
        validate_on_reload: true
      injection_protection:
        enabled: true
        structural_separation: true
        require_out_of_band_confirmation: true
        scan_untrusted_content: true
        block_shell_from_untrusted: true
      validation:
        enabled: true
        log_all_failures: true
        fail_loud_on_critical: true
        skill_scan_on_load: true
        config_validate_on_change: true
      skills:
        auto_generate: false
        human_review_required: true
        scan_for_injection: true
        scan_for_truncation: true
        max_skill_size_chars: 50000
        weekly_audit: true
        audit_schedule: "0 3 * * 0"
      token_budget:
        enabled: true
        max_tool_definition_tokens: 5000
        prefer_cli_over_gateway: true
        minimal_toolsets_by_default: true
      evaluation:
        auto_evaluate: false
        human_review_required: true
        min_confidence_threshold: 0.9
      memory:
        max_chars: 2200
        auto_compact: false
        warn_at_percent: 80
      global_state:
        protect: true
        warn_on_stale_read: true
        lock_during_subagent: true
      recovery:
        auto_recovery: true
        max_recovery_attempts: 3
        recovery_cooldown_seconds: 30

# Model config (MUST match!)
model:
  context_length: 100000
  context_window: 100000
  compression_threshold: 0.6
```

## Security Notes

- **Never run Hermes on production machines with sensitive credentials until upstream fixes land for prompt injection**
- Enable all injection protection before processing untrusted content (emails, web pages, PDFs)
- Disable auto-skill generation until you've established human review workflow
- Run periodic security scans: `hermes security scan --full`

## References

- Context Death Spiral: Issue #2153
- Config Key Mismatch: Issue #8015
- Skill Truncation: Issue #7390
- Global State Race: Issue #7798
- Prompt Injection → RCE: https://trust-shell.com/en/redteam/ts-2026-004-hermes-indirect-injection-rce
- Technical Review: https://medium.com/@leif.markthaler/hermes-agent-a-deep-technical-review-of-nousresearchs-self-improving-ai-agent-b48c64f8e3cc

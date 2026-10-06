# Hermes Fix Plugin - Hardening & Weakness Mitigation

A comprehensive plugin that fixes known Hermes Agent weaknesses including context death spiral, config bugs, silent failures, security vulnerabilities, and skill issues.

## Features

- **Context Death Spiral Prevention** - Aggressive compression monitoring with automatic recovery
- **Config Key Validation** - Ensures `context_length` == `context_window` at startup
- **Prompt Injection Hardening** - Structural separation of data vs instructions for tool calls
- **Fail-Silent Elimination** - Adds validation, logging, and explicit error handling
- **Skill Quality Gates** - Scans for injection, truncation, and quality issues
- **Global State Protection** - Guards against mutable state race conditions
- **Token Budget Enforcement** - Enforces minimal toolsets and compression budgets
- **Sycophantic Evaluation Guard** - Disables auto-evaluation, requires human review

## Installation

```bash
# Copy to Hermes plugins directory
cp -r hermes_fix_plugin ~/.hermes/plugins/hermes_fix_plugin

# Enable in config.yaml
plugins:
  enabled:
    - hermes_fix_plugin
```

## Configuration

```yaml
# In ~/.hermes/config.yaml
plugins:
  hermes_fix_plugin:
    enabled: true
    config:
      # Context protection
      context:
        aggressive_compression: true
        compression_threshold: 0.6
        max_tokens_before_compression: 80000
        death_spiral_detection: true
        auto_recovery: true
      
      # Config validation
      config_validation:
        enforce_context_keys: true
        validate_on_startup: true
        validate_on_reload: true
      
      # Prompt injection hardening
      injection_protection:
        enabled: true
        structural_separation: true
        require_out_of_band_confirmation: true
        scan_untrusted_content: true
        block_shell_from_untrusted: true
      
      # Fail-silent elimination
      validation:
        enabled: true
        log_all_failures: true
        fail_loud_on_critical: true
        skill_scan_on_load: true
        config_validate_on_change: true
      
      # Skill quality gates
      skills:
        auto_generate: false
        human_review_required: true
        scan_for_injection: true
        scan_for_truncation: true
        max_skill_size_chars: 50000
        weekly_audit: true
        audit_schedule: "0 3 * * 0"  # Weekly Sunday 3am
      
      # Token budget enforcement
      token_budget:
        enabled: true
        max_tool_definition_tokens: 5000
        prefer_cli_over_gateway: true
        minimal_toolsets_by_default: true
      
      # Evaluation guard
      evaluation:
        auto_evaluate: false
        human_review_required: true
        min_confidence_threshold: 0.9
      
      # Memory protection
      memory:
        max_chars: 2200
        auto_compact: false
        warn_at_percent: 80
      
      # Global state protection
      global_state:
        protect: true
        warn_on_stale_read: true
        lock_during_subagent: true
      
      # Recovery
      recovery:
        auto_recovery: true
        max_recovery_attempts: 3
        recovery_cooldown_seconds: 30
```

## Commands Added

```bash
# Context health check
hermes context health

# Config validation
hermes config validate --strict

# Skill audit
hermes skill audit --full

# Security scan
hermes security scan --full

# Context death spiral check
hermes context check-death-spiral

# Prompt injection scan
hermes security scan-injection --all

# Skill quality audit
hermes skill audit-quality --all

# Full system health check
hermes doctor --full

# Emergency recovery
hermes recovery emergency
```

## How It Works

### 1. Context Death Spiral Prevention
- Monitors token usage in real-time
- Triggers aggressive compression at 60% threshold (configurable)
- Detects death spiral pattern (3+ failed compressions in 5 minutes)
- Automatic recovery: clears session, resets context, restarts gateway

### 2. Config Key Validation
- Validates `context_length` == `context_window` at startup
- Warns if only one key is set
- Auto-copies value if only one is set
- Validates on config reload

### 3. Prompt Injection Hardening
- **Structural separation**: Content marked as "untrusted" can never directly authorize tool calls
- **Out-of-band confirmation**: Shell/file-write tools require explicit confirmation when processing untrusted content
- **Content scanning**: Scans untrusted content for injection patterns before processing
- **Shell blocking**: Blocks shell commands when processing untrusted content unless explicitly confirmed

### 4. Fail-Silent Elimination
- All critical operations log failures explicitly
- Skill loading validates frontmatter, body, and size
- Config changes validated immediately
- Tool dispatch logs all failures with context

### 5. Skill Quality Gates
- Scans for injection patterns in skill content
- Checks frontmatter truncation (< 2000 chars)
- Validates skill size limits
- Weekly automated audit with report

### 6. Global State Protection
- Thread locks around global state access during subagent execution
- Warns on stale reads
- Isolates subagent contexts completely

### 7. Token Budget Enforcement
- Limits tool definition tokens to 5000
- Prefers CLI over gateway
- Minimal toolsets by default

### 7. Sycophantic Evaluation Guard
- Disables auto-evaluation by default
- Requires human review for all evaluations
- Minimum confidence threshold: 0.9

## Recovery Commands

```bash
# Full system health check
hermes doctor --full

# Emergency context recovery
hermes recovery emergency

# Specific recovery
hermes recovery context
hermes recovery session
hermes recovery skills
```

## Monitoring

The plugin adds these metrics to `hermes doctor`:

- `context_health`: OK/WARNING/CRITICAL
- `death_spiral_risk`: LOW/MEDIUM/HIGH
- `config_valid`: true/false
- `injection_protection_active`: true/false
- `skill_quality_score`: 0-100
- `token_budget_usage`: percentage
- `global_state_health`: OK/WARNING
- `memory_usage`: percentage

## Integration

The plugin hooks into:
- `on_startup` - Config validation, protection initialization
- `on_context_update` - Death spiral monitoring
- `on_tool_dispatch` - Injection protection, validation
- `on_skill_load` - Skill scanning
- `on_subagent_spawn` - Global state locking
- `on_evaluation` - Sycophantic evaluation guard
- `on_shutdown` - Cleanup, metric persistence

## Compatibility

- Hermes v0.12.0+ (Curator Release)
- Works with all sandbox backends (local, Docker, SSH, Modal, Daytona)
- Compatible with all model providers
- No breaking changes to existing skills/config

## License

MIT - Part of Vortex ecosystem
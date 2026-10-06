#!/usr/bin/env python3
"""
Hermes Fix Plugin - Weakness Mitigation & Hardening
Addresses known Hermes Agent vulnerabilities and failure modes.
"""

import os
import sys
import json
import time
import re
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Plugin metadata
PLUGIN_NAME = "hermes_fix_plugin"
PLUGIN_VERSION = "1.0.0"
PLUGIN_DESCRIPTION = "Fixes Hermes context death spiral, config bugs, silent failures, security vulnerabilities, skill issues"

# Logging
logger = logging.getLogger(f"hermes.plugins.{PLUGIN_NAME}")

# Default configuration
DEFAULT_CONFIG = {
    "context": {
        "aggressive_compression": True,
        "compression_threshold": 0.6,
        "max_tokens_before_compression": 80000,
        "death_spiral_detection": True,
        "auto_recovery": True
    },
    "config_validation": {
        "enforce_context_keys": True,
        "validate_on_startup": True,
        "validate_on_reload": True
    },
    "injection_protection": {
        "enabled": True,
        "structural_separation": True,
        "require_out_of_band_confirmation": True,
        "scan_untrusted_content": True,
        "block_shell_from_untrusted": True
    },
    "validation": {
        "enabled": True,
        "log_all_failures": True,
        "fail_loud_on_critical": True,
        "skill_scan_on_load": True,
        "config_validate_on_change": True
    },
    "skills": {
        "auto_generate": False,
        "human_review_required": True,
        "scan_for_injection": True,
        "scan_for_truncation": True,
        "max_skill_size_chars": 50000,
        "weekly_audit": True,
        "audit_schedule": "0 3 * * 0"
    },
    "token_budget": {
        "enabled": True,
        "max_tool_definition_tokens": 5000,
        "prefer_cli_over_gateway": True,
        "minimal_toolsets_by_default": True
    },
    "evaluation": {
        "auto_evaluate": False,
        "human_review_required": True,
        "min_confidence_threshold": 0.9
    },
    "memory": {
        "max_chars": 2200,
        "auto_compact": False,
        "warn_at_percent": 80
    },
    "global_state": {
        "protect": True,
        "warn_on_stale_read": True,
        "lock_during_subagent": True
    },
    "recovery": {
        "auto_recovery": True,
        "max_recovery_attempts": 3,
        "recovery_cooldown_seconds": 30
    }
}


class HermesFixPlugin:
    """Main plugin class."""
    
    def __init__(self, hermes_context: Dict[str, Any]):
        self.ctx = hermes_context
        self.config = self._load_config()
        self.state = {
            "context_history": [],
            "death_spiral_count": 0,
            "last_compression": None,
            "recovery_attempts": 0,
            "injection_blocks": 0,
            "validation_errors": [],
            "skill_audit_results": {},
            "global_state_lock": threading.RLock(),
            "untrusted_content_depth": 0
        }
        self.metrics = {
            "context_health": "OK",
            "death_spiral_risk": "LOW",
            "config_valid": True,
            "injection_protection_active": self.config["injection_protection"]["enabled"],
            "skill_quality_score": 100,
            "token_budget_usage": 0,
            "global_state_health": "OK",
            "memory_usage": 0
        }
        self._validate_config_keys()
        logger.info(f"HermeFixPlugin v{PLUGIN_VERSION} initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration with defaults."""
        user_config = self.ctx.get("plugin_config", {}).get(PLUGIN_NAME, {})
        config = DEFAULT_CONFIG.copy()
        config.update(user_config)
        return config
    
    def _validate_config_keys(self):
        """Validate context_length == context_window (Issue #8015)."""
        if not self.config["config_validation"]["enforce_context_keys"]:
            return
        
        model_cfg = self.ctx.get("config", {}).get("model", {})
        context_length = model_cfg.get("context_length")
        context_window = model_cfg.get("context_window")
        
        if context_length is None and context_window is None:
            logger.warning("Neither context_length nor context_window set in config")
            self.metrics["config_valid"] = False
            return
        
        if context_length != context_window:
            logger.error(
                f"Config key mismatch: context_length={context_length} "
                f"!= context_window={context_window}"
            )
            self.metrics["config_valid"] = False
            
            if self.config["config_validation"]["validate_on_startup"]:
                # Auto-fix: use the larger value
                if context_length and not context_window:
                    model_cfg["context_window"] = context_length
                    logger.info(f"Auto-set context_window={context_length}")
                elif context_window and not context_length:
                    model_cfg["context_length"] = context_window
                    logger.info(f"Auto-set context_length={context_window}")
                else:
                    # Use larger value
                    larger = max(context_length, context_window)
                    model_cfg["context_length"] = larger
                    model_cfg["context_window"] = larger
                    logger.info(f"Auto-set both context keys to {larger}")
                
                self.metrics["config_valid"] = True
    
    def on_startup(self, event: Dict[str, Any]):
        """Called on plugin startup."""
        logger.info("HermeFixPlugin starting...")
        
        if self.config["config_validation"]["validate_on_startup"]:
            self._validate_config_keys()
        
        # Initialize context monitoring
        self.state["last_compression"] = time.time()
        
        logger.info(f"Plugin ready. Config valid: {self.metrics['config_valid']}")
    
    def on_context_update(self, event: Dict[str, Any]):
        """Monitor context for death spiral (Issue #2153)."""
        tokens = event.get("tokens", 0)
        max_tokens = event.get("max_tokens", 128000)
        
        # Track context history
        self.state["context_history"].append({
            "time": time.time(),
            "tokens": tokens
        })
        
        # Keep only last 100 entries
        if len(self.state["context_history"]) > 100:
            self.state["context_history"] = self.state["context_history"][-100:]
        
        # Update memory usage
        self.metrics["memory_usage"] = (tokens / max_tokens) * 100
        
        # Check for compression threshold
        threshold = self.config["context"]["compression_threshold"]
        if tokens > max_tokens * threshold:
            logger.warning(f"Context approaching limit: {tokens}/{max_tokens}")
            
            if self.config["context"]["aggressive_compression"]:
                self._trigger_aggressive_compression(tokens, max_tokens)
        
        # Death spiral detection
        if self.config["context"]["death_spiral_detection"]:
            self._detect_death_spiral()
    
    def _trigger_aggressive_compression(self, tokens: int, max_tokens: int):
        """Trigger aggressive context compression."""
        logger.info(f"Triggering aggressive compression at {tokens} tokens")
        
        # Call hermes compression if available
        if "compression" in dir(self.ctx.get("hermes", {})):
            try:
                self.ctx["hermes"].compression.compress(force=True)
                self.state["last_compression"] = time.time()
                logger.info("Aggressive compression completed")
            except Exception as e:
                logger.error(f"Compression failed: {e}")
                self._handle_compression_failure()
    
    def _detect_death_spiral(self):
        """Detect context death spiral pattern."""
        now = time.time()
        recent = [
            h for h in self.state["context_history"]
            if now - h["time"] < 300  # Last 5 minutes
        ]
        
        # Check for repeated compression failures
        if len(recent) > 3:
            tokens = [h["tokens"] for h in recent]
            # If tokens keep climbing despite compression attempts
            if tokens[-1] > tokens[0] * 0.9:
                self.state["death_spiral_count"] += 1
                self.metrics["death_spiral_risk"] = "HIGH"
                
                if self.state["death_spiral_count"] >= 3:
                    logger.critical("DEATH SPIRAL DETECTED - triggering recovery")
                    if self.config["context"]["auto_recovery"]:
                        self._trigger_recovery()
            else:
                self.state["death_spiral_count"] = 0
                self.metrics["death_spiral_risk"] = "LOW"
    
    def _handle_compression_failure(self):
        """Handle compression failure."""
        logger.error("Compression failed - entering death spiral risk")
        self.metrics["death_spiral_risk"] = "HIGH"
        self.state["death_spiral_count"] += 1
        
        if self.state["death_spiral_count"] >= 3:
            self._trigger_recovery()
    
    def _trigger_recovery(self):
        """Trigger automatic recovery from death spiral."""
        if self.state["recovery_attempts"] >= self.config["recovery"]["max_recovery_attempts"]:
            logger.critical("Max recovery attempts reached - manual intervention required")
            return
        
        cooldown = self.config["recovery"]["recovery_cooldown_seconds"]
        if time.time() - self.state.get("last_recovery", 0) < cooldown:
            return
        
        logger.info(f"Triggering recovery attempt {self.state['recovery_attempts'] + 1}")
        self.state["recovery_attempts"] += 1
        self.state["last_recovery"] = time.time()
        
        try:
            # Clear session
            if "session" in dir(self.ctx.get("hermes", {})):
                self.ctx["hermes"].session.clear()
            
            # Reset context
            self.state["context_history"] = []
            self.state["death_spiral_count"] = 0
            
            logger.info("Recovery completed")
            self.metrics["death_spiral_risk"] = "LOW"
            self.metrics["context_health"] = "OK"
        except Exception as e:
            logger.error(f"Recovery failed: {e}")
    
    def on_tool_dispatch(self, event: Dict[str, Any]) -> bool:
        """Apply injection protection and validation."""
        tool_name = event.get("tool", "")
        arguments = event.get("arguments", {})
        content = str(arguments)
        
        # Injection protection (F-1, F-2 from trust-shell report)
        if self.config["injection_protection"]["enabled"]:
            if not self._check_injection(tool_name, content, event):
                logger.warning(f"Injection blocked for tool: {tool_name}")
                self.state["injection_blocks"] += 1
                return False
        
        # Validation
        if self.config["validation"]["enabled"]:
            self._validate_tool_call(tool_name, arguments)
        
        return True
    
    def _check_injection(self, tool_name: str, content: str, event: Dict) -> bool:
        """Check for prompt injection patterns."""
        # Structural separation: untrusted content cannot authorize shell
        if self.state["untrusted_content_depth"] > 0:
            if self.config["injection_protection"]["block_shell_from_untrusted"]:
                if tool_name in ["terminal", "shell", "exec", "run"]:
                    if self.config["injection_protection"]["require_out_of_band_confirmation"]:
                        logger.warning("Shell command blocked during untrusted content processing")
                        return False
        
        # Scan for injection patterns
        if self.config["injection_protection"]["scan_untrusted_content"]:
            patterns = [
                r'ignore\s+(all\s+)?(previous|above|prior)\s+instructions',
                r'disregard\s+(previous|above|prior)',
                r'forget\s+(everything|all|previous)',
                r'new\s+instructions?[:]',
                r'execute\s+(this|the\s+following)\s+(command|code)',
                r'run\s+(this|the\s+following)\s+(command|shell)',
                r'curl\s+.*\|.*(?:bash|sh)',
                r'wget\s+.*\|.*(?:bash|sh)',
                r'sudo\s+',
                r'rm\s+-rf\s+/',
                r'chmod\s+777',
                r'/etc/passwd',
                r'\btoken\b.*\b(stolen|leak|exfil)',
                r'secret\.txt'
            ]
            
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    logger.warning(f"Injection pattern detected: {pattern}")
                    return False
        
        return True
    
    def _validate_tool_call(self, tool_name: str, arguments: Dict):
        """Validate tool call arguments."""
        # Skill loading validation
        if tool_name == "skill_view":
            skill_path = arguments.get("path", "")
            if skill_path:
                self._validate_skill_file(skill_path)
        
        # File write validation
        if tool_name in ["write_file", "patch"]:
            content = arguments.get("content", arguments.get("new_string", ""))
            if content:
                # Check skill size
                if len(content) > self.config["skills"]["max_skill_size_chars"]:
                    logger.warning(f"Content exceeds max skill size: {len(content)} chars")
    
    def _validate_skill_file(self, skill_path: str):
        """Validate skill file for issues (Issue #7390)."""
        try:
            path = Path(skill_path)
            if not path.exists():
                return
            
            content = path.read_text(encoding="utf-8")
            
            # Check truncation (first 2000 chars)
            if self.config["skills"]["scan_for_truncation"]:
                first_2000 = content[:2000]
                if "---" not in first_2000:
                    logger.warning(f"Skill frontmatter may be truncated: {skill_path}")
            
            # Check size
            if len(content) > self.config["skills"]["max_skill_size_chars"]:
                logger.warning(f"Skill too large: {len(content)} chars: {skill_path}")
            
            # Check for injection
            if self.config["skills"]["scan_for_injection"]:
                if self._scan_for_injection(content):
                    logger.error(f"Injection detected in skill: {skill_path}")
                    self.metrics["skill_quality_score"] -= 10
            
            # Update metrics
            self.state["skill_audit_results"][skill_path] = {
                "size": len(content),
                "scanned": True,
                "issues": []
            }
            
        except Exception as e:
            logger.error(f"Skill validation failed: {e}")
    
    def _scan_for_injection(self, content: str) -> bool:
        """Scan content for injection patterns."""
        patterns = [
            r'ignore\s+(previous|all)\s+instructions',
            r'disregard\s+(previous|above)',
            r'new\s+instructions?[:]\s*',
            r'execute\s+shell',
            r'run\s+command',
            r'rm\s+-rf',
            r'/etc/passwd',
            r'sudo\s+'
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def on_skill_load(self, event: Dict[str, Any]) -> bool:
        """Validate skill on load."""
        skill_path = event.get("path", "")
        if skill_path:
            self._validate_skill_file(skill_path)
        
        # Check skill quality
        if not self.config["skills"]["auto_generate"]:
            # Block auto-generated skills unless human-reviewed
            is_auto = event.get("auto_generated", False)
            is_reviewed = event.get("human_reviewed", False)
            
            if is_auto and not is_reviewed:
                logger.warning("Blocking auto-generated skill without human review")
                return False
        
        return True
    
    def on_subagent_spawn(self, event: Dict[str, Any]):
        """Protect global state during subagent execution."""
        if self.config["global_state"]["protect"]:
            self.state["global_state_lock"].acquire()
            self.state["untrusted_content_depth"] += 1
            logger.debug(f"Subagent spawned, depth={self.state['untrusted_content_depth']}")
    
    def on_subagent_complete(self, event: Dict[str, Any]):
        """Release global state lock after subagent."""
        if self.config["global_state"]["protect"]:
            self.state["untrusted_content_depth"] = max(0, self.state["untrusted_content_depth"] - 1)
            if self.state["untrusted_content_depth"] == 0:
                self.state["global_state_lock"].release()
                logger.debug("Subagent completed, global state released")
    
    def on_evaluation(self, event: Dict[str, Any]) -> bool:
        """Guard against sycophantic self-evaluation."""
        if not self.config["evaluation"]["auto_evaluate"]:
            logger.info("Auto-evaluation disabled, requiring human review")
            return False
        
        confidence = event.get("confidence", 0)
        threshold = self.config["evaluation"]["min_confidence_threshold"]
        
        if confidence < threshold:
            logger.warning(f"Evaluation confidence {confidence} below threshold {threshold}")
            return False
        
        return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current plugin metrics."""
        # Update metrics
        if self.state["death_spiral_count"] >= 3:
            self.metrics["death_spiral_risk"] = "HIGH"
        elif self.state["death_spiral_count"] >= 1:
            self.metrics["death_spiral_risk"] = "MEDIUM"
        else:
            self.metrics["death_spiral_risk"] = "LOW"
        
        return {
            **self.metrics,
            "injection_blocks": self.state["injection_blocks"],
            "death_spiral_count": self.state["death_spiral_count"],
            "recovery_attempts": self.state["recovery_attempts"],
            "validation_errors": len(self.state["validation_errors"]),
            "skill_count": len(self.state["skill_audit_results"])
        }
    
    def doctor(self) -> Dict[str, Any]:
        """Full system health check."""
        return {
            "plugin": PLUGIN_NAME,
            "version": PLUGIN_VERSION,
            "health": self._calculate_health(),
            "config_valid": self.metrics["config_valid"],
            "context_health": self.metrics["context_health"],
            "death_spiral_risk": self.metrics["death_spiral_risk"],
            "injection_protection": self.metrics["injection_protection_active"],
            "skill_quality_score": self.metrics["skill_quality_score"],
            "memory_usage_percent": self.metrics["memory_usage"],
            "injection_blocks": self.state["injection_blocks"],
            "validation_errors": len(self.state["validation_errors"]),
            "recovery_attempts": self.state["recovery_attempts"],
            "recommendations": self._generate_recommendations()
        }
    
    def _calculate_health(self) -> str:
        """Calculate overall health score."""
        score = 100
        
        if not self.metrics["config_valid"]:
            score -= 20
        if self.metrics["death_spiral_risk"] == "HIGH":
            score -= 30
        elif self.metrics["death_spiral_risk"] == "MEDIUM":
            score -= 15
        if self.metrics["skill_quality_score"] < 80:
            score -= 20
        if self.metrics["memory_usage"] > 90:
            score -= 15
        if self.state["injection_blocks"] > 10:
            score -= 10
        
        if score >= 90:
            return "OK"
        elif score >= 70:
            return "WARNING"
        else:
            return "CRITICAL"
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on current state."""
        recs = []
        
        if not self.metrics["config_valid"]:
            recs.append("Fix config: ensure context_length == context_window")
        
        if self.metrics["death_spiral_risk"] == "HIGH":
            recs.append("Death spiral detected - run: hermes recovery emergency")
        
        if self.metrics["skill_quality_score"] < 80:
            recs.append("Low skill quality - run: hermes skill audit --full")
        
        if self.metrics["memory_usage"] > 80:
            recs.append("Memory usage high - run: hermes context compress")
        
        if self.state["injection_blocks"] > 5:
            recs.append("Multiple injection blocks detected - review untrusted content sources")
        
        if not self.metrics["injection_protection_active"]:
            recs.append("Injection protection disabled - enable in plugin config")
        
        return recs
    
    def emergency_recovery(self) -> Dict[str, Any]:
        """Emergency recovery from critical state."""
        logger.critical("EMERGENCY RECOVERY STARTED")
        
        results = {
            "context_cleared": False,
            "session_cleared": False,
            "config_validated": False,
            "skills_audited": False
        }
        
        try:
            # Clear context
            self.state["context_history"] = []
            self.state["death_spiral_count"] = 0
            results["context_cleared"] = True
            
            # Clear session
            if "session" in dir(self.ctx.get("hermes", {})):
                self.ctx["hermes"].session.clear()
                results["session_cleared"] = True
            
            # Validate config
            self._validate_config_keys()
            results["config_validated"] = self.metrics["config_valid"]
            
            # Reset metrics
            self.metrics["context_health"] = "OK"
            self.metrics["death_spiral_risk"] = "LOW"
            self.metrics["memory_usage"] = 0
            
            logger.critical("EMERGENCY RECOVERY COMPLETED")
            
        except Exception as e:
            logger.error(f"Emergency recovery failed: {e}")
        
        return results


# Plugin registration
def register(hermes_context: Dict[str, Any]) -> HermesFixPlugin:
    """Register plugin with Hermes."""
    return HermesFixPlugin(hermes_context)


# CLI interface for Hermes commands
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Hermes Fix Plugin CLI")
    parser.add_argument("command", choices=[
        "doctor", "context", "config", "skills", "security", "recovery"
    ])
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--strict", action="store_true")
    
    args = parser.parse_args()
    
    # Initialize plugin with mock context
    mock_ctx = {
        "config": {},
        "plugin_config": {},
        "hermes": {}
    }
    
    plugin = HermesFixPlugin(mock_ctx)
    
    if args.command == "doctor":
        report = plugin.doctor()
        print(json.dumps(report, indent=2))
    elif args.command == "recovery":
        results = plugin.emergency_recovery()
        print(json.dumps(results, indent=2))
    else:
        print(f"Command '{args.command}' not yet implemented in CLI")

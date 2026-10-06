#!/usr/bin/env python3
"""
Install script for Hermes Fix Plugin.
Installs the plugin into Hermes plugins directory.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PLUGIN_NAME = "hermes_fix_plugin"
PLUGIN_DIR = Path(__file__).parent
HERMES_PLUGINS_DIR = Path.home() / ".hermes" / "plugins"
TARGET_DIR = HERMES_PLUGINS_DIR / PLUGIN_NAME

def main():
    print(f"Installing {PLUGIN_NAME}...")
    
    # Check if Hermes is installed
    try:
        import hermes
        print("Hermes Agent found")
    except ImportError:
        print("WARNING: Hermes Agent not found. Install with: pip install hermes-agent")
    
    # Create plugins directory if it doesn't exist
    HERMES_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Remove existing installation
    if TARGET_DIR.exists():
        print(f"Removing existing installation at {TARGET_DIR}")
        shutil.rmtree(TARGET_DIR)
    
    # Copy plugin files
    print(f"Copying plugin to {TARGET_DIR}")
    shutil.copytree(PLUGIN_DIR, TARGET_DIR, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".git", ".gitignore", "*.md", "*.txt", "test*", "install.py"
    ))
    
    # Verify installation
    plugin_file = TARGET_DIR / "plugin.py"
    skill_file = TARGET_DIR / "SKILL.md"
    
    if plugin_file.exists() and skill_file.exists():
        print("✅ Plugin installed successfully!")
        print(f"Location: {TARGET_DIR}")
        print()
        print("Next steps:")
        print("1. Add to your ~/.hermes/config.yaml:")
        print("""
plugins:
  hermes_fix_plugin:
    enabled: true
    config:
      context:
        aggressive_compression: true
        compression_threshold: 0.6
      injection_protection:
        enabled: true
      validation:
        enabled: true
      skills:
        auto_generate: false
        human_review_required: true
      evaluation:
        auto_evaluate: false
""")
        print("2. Run health check:")
        print("   hermes doctor --full")
        print("3. Test commands:")
        print("   hermes doctor --full")
        print("   hermes context health")
        print("   hermes skill audit --full")
    else:
        print("❌ Installation failed - missing files")
        sys.exit(1)

if __name__ == "__main__":
    main()
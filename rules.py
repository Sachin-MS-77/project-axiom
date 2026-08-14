"""
rules.py — PROJECT AXIOM

Defines the security audit rules and the command allowlist.
Only commands defined in RULES may be executed by connector.py.
"""

# List of rule definitions. Each rule is a dictionary containing an 'id' and a 'command'.
RULES = [
    {
        "id": "ssh_root_login",
        "description": "Check if SSH root login is disabled",
        "command": "grep -i '^PermitRootLogin' /etc/ssh/sshd_config",
        "category": "ssh",
        "severity": "HIGH",
    },
    {
        "id": "ssh_password_auth",
        "description": "Check if SSH password authentication is disabled",
        "command": "grep -i '^PasswordAuthentication' /etc/ssh/sshd_config",
        "category": "ssh",
        "severity": "MEDIUM",
    },
    {
        "id": "world_writable_files",
        "description": "Check for world-writable files in /etc",
        "command": "find /etc -type f -perm -0002",
        "category": "filesystem",
        "severity": "HIGH",
    },
    {
        "id": "listening_ports",
        "description": "List all listening network ports",
        "command": "ss -tuln",
        "category": "network",
        "severity": "LOW",
    },
    {
        "id": "shadow_file_permissions",
        "description": "Check permissions and ownership of /etc/shadow",
        "command": "stat -c '%a %U %G' /etc/shadow 2>/dev/null || ls -l /etc/shadow",
        "category": "filesystem",
        "severity": "HIGH",
    },
    {
        "id": "sudoers_nopasswd",
        "description": "Check for unauthenticated root escalation rules in sudoers",
        "command": "grep -ri 'NOPASSWD:' /etc/sudoers /etc/sudoers.d/ 2>/dev/null || true",
        "category": "privilege",
        "severity": "CRITICAL",
    },
    {
        "id": "empty_password_accounts",
        "description": "Check for accounts with empty password fields in /etc/shadow",
        "command": "awk -F: '($2 == \"\") {print $1}' /etc/shadow 2>/dev/null || true",
        "category": "accounts",
        "severity": "CRITICAL",
    },
    {
        "id": "outdated_packages",
        "description": "Check for pending package security updates",
        "command": "apt-get -s upgrade 2>/dev/null | grep -i 'upgraded,' || true",
        "category": "packages",
        "severity": "LOW",
    },
]


def get_command_allowlist():
    """
    Returns a dictionary mapping rule_id -> command string
    for all rules defined in RULES.
    """
    allowlist = {}
    if isinstance(RULES, dict):
        for key, val in RULES.items():
            if isinstance(val, dict):
                allowlist[key] = val.get("command", "")
            else:
                allowlist[key] = str(val)
    elif isinstance(RULES, (list, tuple)):
        for rule in RULES:
            if isinstance(rule, dict):
                rule_id = rule.get("id") or rule.get("rule_id")
                if rule_id and "command" in rule:
                    allowlist[rule_id] = rule["command"]
    return allowlist

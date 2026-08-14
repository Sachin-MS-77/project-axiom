"""
connector.py — PROJECT AXIOM

Handles opening a connection to a target (SSH or Docker) and running commands
against it. This is the ONLY file allowed to open a connection or execute
anything on a target.

Safety contract:
  - Every command run through this file MUST come from rules.py's allowlist.
  - There is exactly one execution path (_execute) and it is always reached
    through run(), which always checks the allowlist first. No other function
    in this file, or any other file, should call _execute directly.
"""

import subprocess
import paramiko
import docker

from rules import get_command_allowlist


class RefusedCommandError(Exception):
    """Raised when a command is not on the approved allowlist."""
    pass


class ConnectionResult:
    """Simple container for a single command's outcome."""

    def __init__(self, rule_id, command, success, output, error=None):
        self.rule_id = rule_id
        self.command = command
        self.success = success
        self.output = output
        self.error = error


class Connector:
    def __init__(self, method, target, **kwargs):
        """
        method: "ssh" or "docker"
        target: hostname/IP (ssh) or container name (docker)
        kwargs (ssh): username, key_path (preferred) or password, port=22
        kwargs (docker): none required beyond target
        """
        self.method = method
        self.target = target
        self.kwargs = kwargs
        self._ssh_client = None
        self._docker_client = None
        self._docker_container = None
        self.allowlist = get_command_allowlist()  # {rule_id: command}

    # ------------------------------------------------------------------
    # Connection setup
    # ------------------------------------------------------------------

    def connect(self):
        """Opens the connection. Returns (success: bool, error: str or None)."""
        try:
            if self.method == "ssh":
                return self._connect_ssh()
            elif self.method == "docker":
                return self._connect_docker()
            else:
                return False, f"Unknown method '{self.method}' (expected 'ssh' or 'docker')."
        except Exception as e:
            return False, f"Connection failed: {e}"

    def _connect_ssh(self):
        username = self.kwargs.get("username")
        key_path = self.kwargs.get("key_path")
        password = self.kwargs.get("password")
        port = self.kwargs.get("port", 22)

        if not username:
            return False, "SSH connection requires a 'username'."

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if key_path:
            client.connect(self.target, port=port, username=username, key_filename=key_path, timeout=10)
        elif password:
            client.connect(self.target, port=port, username=username, password=password, timeout=10)
        else:
            return False, "SSH connection requires either 'key_path' or 'password'."

        self._ssh_client = client
        return True, None

    def _connect_docker(self):
        client = docker.from_env()
        container = client.containers.get(self.target)
        if container.status != "running":
            return False, f"Container '{self.target}' exists but is not running (status: {container.status})."
        self._docker_client = client
        self._docker_container = container
        return True, None

    def close(self):
        if self._ssh_client:
            self._ssh_client.close()
        # Docker SDK client needs no explicit close for this usage.

    # ------------------------------------------------------------------
    # Guarded execution — the ONLY path to running anything on a target
    # ------------------------------------------------------------------

    def run(self, rule_id, timeout=15):
        """
        Public entry point. Always checks the allowlist before running anything.
        Returns a ConnectionResult. Never raises out to the caller — failures,
        refusals, and timeouts are all captured in the result.
        """
        if rule_id not in self.allowlist:
            reason = (
                f"REFUSED: rule_id '{rule_id}' is not in rules.py's allowlist. "
                f"Only commands defined in RULES[] may be executed. "
                f"See rules.py -> get_command_allowlist()."
            )
            return ConnectionResult(rule_id, command=None, success=False, output=None, error=reason)

        command = self.allowlist[rule_id]

        try:
            output = self._execute(command, timeout=timeout)
            return ConnectionResult(rule_id, command, success=True, output=output)
        except subprocess.TimeoutExpired:
            return ConnectionResult(rule_id, command, success=False, output=None, error="Command timed out.")
        except Exception as e:
            return ConnectionResult(rule_id, command, success=False, output=None, error=str(e))

    def _execute(self, command, timeout=15):
        """
        Private. Do not call directly — always go through run().
        Executes the given command string against the connected target.
        """
        if self.method == "ssh":
            if not self._ssh_client:
                raise RuntimeError("SSH client not connected. Call connect() first.")
            stdin, stdout, stderr = self._ssh_client.exec_command(command, timeout=timeout)
            out = stdout.read().decode(errors="replace")
            err = stderr.read().decode(errors="replace")
            return out if out else err

        elif self.method == "docker":
            if not self._docker_container:
                raise RuntimeError("Docker container not connected. Call connect() first.")
            # exec_run runs a shell so pipes/grep in rules.py commands work correctly
            result = self._docker_container.exec_run(["sh", "-c", command])
            return result.output.decode(errors="replace")

        else:
            raise RuntimeError(f"Unknown method '{self.method}'.")


# ----------------------------------------------------------------------
# Self-test: confirms the refusal guard actually works.
# Run directly with: python3 connector.py
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("Running connector.py self-test (refusal guard only, no live target needed)...\n")

    dummy = Connector(method="ssh", target="unused-for-this-test", username="unused")
    dummy.allowlist = get_command_allowlist()  # normally set in __init__, kept explicit here

    result = dummy.run("this-rule-id-does-not-exist")

    if not result.success and result.error and "REFUSED" in result.error:
        print("PASS: off-allowlist command was correctly refused.")
        print(f"Reason given: {result.error}")
    else:
        print("FAIL: the refusal guard did not behave as expected.")
        print(f"Result: success={result.success}, error={result.error}")
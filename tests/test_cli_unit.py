import pytest
import sys
import os
import importlib.util
from unittest.mock import patch, MagicMock, call

from importlib.machinery import SourceFileLoader

# Helper to import sanity-cli as a module
def load_sanity_cli():
    if "sanity_cli" in sys.modules:
        return sys.modules["sanity_cli"]
        
    file_path = os.path.abspath("sanity-cli")
    # SourceFileLoader works even without .py extension
    loader = SourceFileLoader("sanity_cli", file_path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("sanity_cli", loader))
    sys.modules["sanity_cli"] = module
    loader.exec_module(module)
    return module

sanity_cli = load_sanity_cli()

class TestStatusDiscovery:
    """Tests for get_active_projects function."""

    @patch("sanity_cli.run_command")
    def test_get_active_projects_discovery(self, mock_run):
        # Mock docker ps output
        # Current logic uses 'docker ps --filter label=...' and expects just project names
        mock_output = """project-a
project-b
project-c"""
        
        mock_run.return_value = mock_output
        
        projects = sanity_cli.get_active_projects()
        
        # Verify projects are parsed correctly
        assert "project-a" in projects
        assert "project-b" in projects
        assert "project-c" in projects
        assert len(projects) == 3
        
    @patch("sanity_cli.run_command")
    def test_get_active_projects_empty(self, mock_run):
        mock_run.return_value = ""
        projects = sanity_cli.get_active_projects()
        assert projects == []

    @patch("sanity_cli.run_command")
    def test_get_active_projects_error(self, mock_run):
        mock_run.side_effect = Exception("Docker error")
        projects = sanity_cli.get_active_projects()
        assert projects == []

class TestConfigSync:
    """Tests for sync_config function."""

    @pytest.fixture
    def mock_env(self):
        with patch("os.path.exists") as mock_exists, \
             patch("os.makedirs") as mock_makedirs, \
             patch("shutil.copy2") as mock_copy, \
             patch("sanity_cli.run_command") as mock_run, \
             patch("builtins.print") as mock_print:
            yield mock_exists, mock_makedirs, mock_copy, mock_run, mock_print

    def test_sync_config_non_interactive(self, mock_env):
        mock_exists, _, _, mock_run, _ = mock_env
        
        # Simulate config dir missing
        mock_exists.side_effect = lambda p: p != "config"
        
        # Simulate non-interactive TTY
        with patch("sys.stdin.isatty", return_value=False):
            sanity_cli.sync_config("test-proj", "test-container", "user")
            
            # Should NOT call input
            # Should NOT call docker cp (since it skips)
            # Verify no docker cp command was run
            for call_args in mock_run.call_args_list:
                cmd = call_args[0][0]
                assert "docker cp" not in cmd

    def test_sync_config_interactive_copy(self, mock_env):
        mock_exists, mock_makedirs, mock_copy, mock_run, _ = mock_env
        
        # Simulate config dir missing, but ~/.gemini files exist
        def exists_side_effect(path):
            if path == "config": return False
            if "GEMINI.md" in path: return True
            if "settings.json" in path: return True
            return False
        mock_exists.side_effect = exists_side_effect
        
        # Simulate interactive TTY and user input 'a'
        with patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", return_value="a"):
            
            sanity_cli.sync_config("test-proj", "test-container", "user")
            
            # Should copy files
            assert mock_copy.call_count >= 2 # GEMINI.md and settings.json
            
            # Should sync to container (mocking that config dir exists now? 
            # Logic in sync_config checks os.path.exists(config_dir) AGAIN before syncing.
            # We need to ensure the second check returns True.
            # Side effect is tricky if called multiple times with same arg.
            # Let's assume os.makedirs makes it exist.
            # But os.path.exists is mocked.
            # We can use a side_effect that checks a state variable.
            pass

    # Refined interactive test with state
    def test_sync_config_interactive_flow(self):
        # We need a more complex mock for os.path.exists to simulate directory creation
        fs_state = {"config": False, "home_gemini": True}
        
        def exists_mock(path):
            if path == "config": return fs_state["config"]
            if ".gemini" in path: return True
            return False
            
        def makedirs_mock(path, exist_ok=True):
            if path == "config": fs_state["config"] = True

        with patch("os.path.exists", side_effect=exists_mock), \
             patch("os.makedirs", side_effect=makedirs_mock), \
             patch("shutil.copy2") as mock_copy, \
             patch("sanity_cli.run_command") as mock_run, \
             patch("sys.stdin.isatty", return_value=True), \
             patch("builtins.input", return_value="a"), \
             patch("builtins.print"):
             
            sanity_cli.sync_config("test-proj", "test-container", "user")
            
            # Verify files copied from host
            assert mock_copy.call_count >= 2
            
            # Verify docker commands (mkdir and cp)
            # We expect: mkdir -p ... and docker cp config/. ...
            docker_cmds = [args[0][0] for args in mock_run.call_args_list]
            assert any("docker cp config/." in cmd for cmd in docker_cmds)

    def test_sync_config_safe_simulation(self):
        """Test sync_config with a custom source directory (simulation)."""
        import tempfile
        import shutil
        
        # Create a temporary directory to act as the config source
        with tempfile.TemporaryDirectory() as temp_config_dir:
            # Create a dummy GEMINI.md in it
            gemini_path = os.path.join(temp_config_dir, "GEMINI.md")
            with open(gemini_path, "w") as f:
                f.write("# Safe Simulation Test")
                
            with patch("sanity_cli.run_command") as mock_run, \
                 patch("builtins.print"):
                
                # Call sync_config with the temp dir as source
                sanity_cli.sync_config("safe-proj", "safe-container", "user", config_source=temp_config_dir)
                
                # Check that docker cp was called with the temp dir
                docker_cmds = [args[0][0] for args in mock_run.call_args_list]
                
                # We expect: docker cp {temp_config_dir}/. safe-container:/home/user/.gemini/
                expected_cp_part = f"docker cp {temp_config_dir}/."
                
                # Filter commands that are copy commands
                cp_commands = [cmd for cmd in docker_cmds if "docker cp" in cmd]
                
                assert len(cp_commands) > 0, "No docker cp command found"
                assert expected_cp_part in cp_commands[0], f"Expected source {temp_config_dir} in {cp_commands[0]}"
                
                # Also verify mkdir and chown calls
                assert any("mkdir -p /home/user/.gemini" in cmd for cmd in docker_cmds)
                assert any("chown -R user:user /home/user/.gemini" in cmd for cmd in docker_cmds)

class TestRunResourceArgs:
    """Tests for resource quota arguments."""
    
    @patch("sanity_cli.run_command")
    @patch("sanity_cli.get_uid_gid_user", return_value=(1000, 1000, "dev"))
    @patch("sanity_cli.generate_resource_compose")
    def test_run_with_resources(self, mock_gen_res, mock_user, mock_run):
        # Setup mocks
        mock_gen_res.return_value = "config/docker-compose.resources.yml"
        
        args = MagicMock()
        args.variant = "core"
        args.cpus = "1.5"
        args.memory = "2G"
        # set other defaults
        args.skip_check = True
        args.ssh_port = "2222"
        args.kasm_port = "8444"
        args.vnc_port = "5901"
        args.novnc_port = "6901"
        args.workspace = None
        args.name = "sanity-gravity"
        args.gpu = False
        args.password = "pass"
        
        sanity_cli.up(args)
        
        # Verify generate_resource_compose called
        mock_gen_res.assert_called_with("1.5", "2G")
        
        # Verify docker compose command includes the new file
        # We need to check all calls to run_command
        # Look for the one that has 'up -d'
        up_calls = [args[0][0] for args in mock_run.call_args_list if "up -d" in args[0][0]]
        assert len(up_calls) > 0
        cmd = up_calls[0]
        assert "-f config/docker-compose.resources.yml" in cmd

class TestNewCommands:
    """Tests for shell and open commands."""
    
    @patch("sanity_cli.run_command")
    @patch("subprocess.check_call")
    def test_shell_command(self, mock_check_call, mock_run):
        # Mock finding container
        mock_run.return_value = "true" # docker inspect running
        
        args = MagicMock()
        args.name = "sanity-gravity"
        args.user = None # Default behavior
        
        with patch("sanity_cli.get_active_projects", return_value=["sanity-gravity"]):
            sanity_cli.shell_cmd(args)
            
            # Check if docker exec was called
            # We assume it finds sanity-gravity-core-1 (first in VARIANTS)
            # developer is default user
            expected_cmd = "docker exec -it -u developer sanity-gravity-core-1 zsh"
            mock_check_call.assert_called_with(expected_cmd, shell=True)

    @patch("sanity_cli.run_command")
    @patch("subprocess.check_call")
    def test_shell_command_with_user(self, mock_check_call, mock_run):
        # Mock finding container
        mock_run.return_value = "true" 
        
        args = MagicMock()
        args.name = "sanity-gravity"
        args.user = "root" # Custom user
        
        with patch("sanity_cli.get_active_projects", return_value=["sanity-gravity"]):
            sanity_cli.shell_cmd(args)
            
            # Verify user passed to docker exec
            expected_cmd = "docker exec -it -u root sanity-gravity-core-1 zsh"
            mock_check_call.assert_called_with(expected_cmd, shell=True)

    @patch("sanity_cli.run_command")
    @patch("webbrowser.open")
    def test_open_command_kasm(self, mock_browser, mock_run):
         def run_side_effect(cmd, **kwargs):
            if "core-1" in cmd: return "false"
            if "kasm-1" in cmd: return "true"
            if "port kasm 8444" in cmd: return "0.0.0.0:12345"
            return ""
         mock_run.side_effect = run_side_effect
         
         args = MagicMock()
         args.name = "sanity-gravity"
         with patch("sanity_cli.get_active_projects", return_value=["sanity-gravity"]):
             sanity_cli.open_cmd(args)
             
             mock_browser.assert_called_with("https://localhost:12345")

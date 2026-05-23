import os
import yaml
import pytest
from unittest.mock import patch

# Helper to import sanity-cli as a module
import sys
import importlib.util
from importlib.machinery import SourceFileLoader

def load_sanity_cli():
    if "sanity_cli" in sys.modules:
        return sys.modules["sanity_cli"]

    file_path = os.path.abspath("sanity-cli")
    loader = SourceFileLoader("sanity_cli", file_path)
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("sanity_cli", loader))
    loader.exec_module(module)
    sys.modules["sanity_cli"] = module
    return module

class TestVolumeIsolation:
    def test_volume_isolation_different_agents(self, tmpdir):
        """Classic Case: Different agents must mount different sanity_home volumes."""
        sanity_cli = load_sanity_cli()
        
        # Patch config_dir so it writes to tmpdir instead of the actual workspace config/
        old_cwd = os.getcwd()
        os.chdir(str(tmpdir))
        
        try:
                out_ag, _ = sanity_cli.generate_compose_for_tag("ag-xfce-kasm")
                out_gc, _ = sanity_cli.generate_compose_for_tag("gc-none-ssh")
                
                assert os.path.exists(out_ag)
                assert os.path.exists(out_gc)
                
                with open(out_ag, 'r') as f:
                    yaml_ag = yaml.safe_load(f)
                with open(out_gc, 'r') as f:
                    yaml_gc = yaml.safe_load(f)
                    
                volumes_ag = yaml_ag.get("volumes", {})
                volumes_gc = yaml_gc.get("volumes", {})
                
                # Check top-level volume declarations
                assert "sg_ag-xfce-kasm" in volumes_ag
                assert "sg_gc-none-ssh" not in volumes_ag
                
                assert "sg_gc-none-ssh" in volumes_gc
                assert "sg_ag-xfce-kasm" not in volumes_gc
                
                # Check explicitly named volume property
                assert volumes_ag["sg_ag-xfce-kasm"]["name"] == "sg-${COMPOSE_PROJECT_NAME:-sanity-gravity}-ag-xfce-kasm"
                assert volumes_gc["sg_gc-none-ssh"]["name"] == "sg-${COMPOSE_PROJECT_NAME:-sanity-gravity}-gc-none-ssh"
                
                # Check service volume mounts
                service_vols_ag = yaml_ag["services"]["ag-xfce-kasm"]["volumes"]
                assert any(v.startswith("sg_ag-xfce-kasm:") for v in service_vols_ag)
                
                service_vols_gc = yaml_gc["services"]["gc-none-ssh"]["volumes"]
                assert any(v.startswith("sg_gc-none-ssh:") for v in service_vols_gc)
                
        finally:
                os.chdir(old_cwd)

    def test_volume_isolation_same_agent_different_connectors(self, tmpdir):
        """Edge Case: Same agent with different connectors must NOT share the same sanity_home volume."""
        sanity_cli = load_sanity_cli()
        
        old_cwd = os.getcwd()
        os.chdir(str(tmpdir))
        
        try:
            out_kasm, _ = sanity_cli.generate_compose_for_tag("ag-xfce-kasm")
            out_ssh, _ = sanity_cli.generate_compose_for_tag("ag-xfce-ssh")
            
            with open(out_kasm, 'r') as f:
                yaml_kasm = yaml.safe_load(f)
            with open(out_ssh, 'r') as f:
                yaml_ssh = yaml.safe_load(f)
                
            # Both must declare exactly their own tag volume
            assert "sg_ag-xfce-kasm" in yaml_kasm.get("volumes", {})
            assert "sg_ag-xfce-ssh" in yaml_ssh.get("volumes", {})
            
            # Check explicit name property
            assert yaml_kasm["volumes"]["sg_ag-xfce-kasm"]["name"] == "sg-${COMPOSE_PROJECT_NAME:-sanity-gravity}-ag-xfce-kasm"
            assert yaml_ssh["volumes"]["sg_ag-xfce-ssh"]["name"] == "sg-${COMPOSE_PROJECT_NAME:-sanity-gravity}-ag-xfce-ssh"
            
            # They must NOT be the same
            assert "sg_ag-xfce-ssh" not in yaml_kasm.get("volumes", {})
            assert "sg_ag-xfce-kasm" not in yaml_ssh.get("volumes", {})
            
            # Both must mount their own tag volume
            assert any(v.startswith("sg_ag-xfce-kasm:") for v in yaml_kasm["services"]["ag-xfce-kasm"]["volumes"])
            assert any(v.startswith("sg_ag-xfce-ssh:") for v in yaml_ssh["services"]["ag-xfce-ssh"]["volumes"])
            
        finally:
            os.chdir(old_cwd)

    def test_volume_isolation_runtime(self, tmpdir):
        """Live Integration: Run two agents in the SAME project and verify they do not overwrite each other's home volume files."""
        import subprocess
        import time
        import getpass
        
        username = getpass.getuser()
        project_name = "test-iso-runtime"
        workspace = os.path.join(str(tmpdir), "workspace")
        os.makedirs(workspace, exist_ok=True)
        
        def run_cli(args):
            return subprocess.run(f"./sanity-cli {args}", shell=True, capture_output=True, text=True, check=True)
        
        try:
            # 1. Start ag-xfce-kasm
            run_cli(f"up -v ag-xfce-kasm -n {project_name} -w {workspace} --skip-check")
            # 2. Start ag-xfce-ssh in the SAME project (tests same agent, different tags)
            run_cli(f"up -v ag-xfce-ssh -n {project_name} -w {workspace} --skip-check")
            
            kasm_container = f"{project_name}-ag-xfce-kasm-1"
            ssh_container = f"{project_name}-ag-xfce-ssh-1"
            
            # Wait for containers to be ready
            time.sleep(3)
            
            # 3. Write 'KASM_DATA' to kasm container's home
            subprocess.run(f"docker exec {kasm_container} sh -c 'echo KASM_DATA > /home/{username}/isolation.txt'", shell=True, check=True)
            
            # 4. Write 'SSH_DATA' to ssh container's home
            subprocess.run(f"docker exec {ssh_container} sh -c 'echo SSH_DATA > /home/{username}/isolation.txt'", shell=True, check=True)
            
            # 5. Read back from both containers
            kasm_read = subprocess.run(f"docker exec {kasm_container} cat /home/{username}/isolation.txt", shell=True, capture_output=True, text=True, check=True).stdout.strip()
            ssh_read = subprocess.run(f"docker exec {ssh_container} cat /home/{username}/isolation.txt", shell=True, capture_output=True, text=True, check=True).stdout.strip()
            
            # 6. Verify data is perfectly isolated
            assert kasm_read == "KASM_DATA", f"Isolation failed! Expected KASM_DATA but got {kasm_read}"
            assert ssh_read == "SSH_DATA", f"Isolation failed! Expected SSH_DATA but got {ssh_read}"
            
        finally:
            # Cleanup
            run_cli(f"down -n {project_name}")

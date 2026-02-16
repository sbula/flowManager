import pytest
from unittest.mock import MagicMock, patch
import sys
from workflow_core.knowledge.cli import main

def test_index_command_invokes_engine():
    # Patch at source because CLI imports them inside function
    with patch('sys.argv', ['cli.py', 'index', 'src']), \
         patch('workflow_core.knowledge.service.KnowledgeService') as MockService, \
         patch('workflow_core.knowledge.ingestion.engine.IngestionEngine') as MockEngine, \
         patch('workflow_core.knowledge.ingestion.hasher.ManifestManager') as MockManifest, \
         patch('json.load', return_value={}): # json is imported at top level, so we can patch json.load? No, better patch the module where it is used or builtin
         
        # Actually json is imported in cli.py. So patch 'workflow_core.knowledge.cli.json.load'
        with patch('workflow_core.knowledge.cli.json.load', return_value={}):
             # Mock open config
             with patch('builtins.open', new_callable=MagicMock):
                 # Mock exists
                 with patch('pathlib.Path.exists', return_value=True):
                     try:
                         with pytest.raises(SystemExit) as e:
                             main()
                         assert e.value.code == 0
                         
                         assert MockEngine.return_value.index_directory.called
                     except Exception as e:
                         pytest.fail(f"CLI failed: {e}")

def test_install_hooks_creates_file(tmp_path):
    # Setup fake git dir
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    
    with patch('sys.argv', ['cli.py', 'install-hooks']), \
         patch('pathlib.Path', wraps=tmp_path): # Trick Path to look at tmp
         # This mocking of Path is tricky because the CLI imports Path.
         # Easier to mock the specific check inside CLI or pass args?
         # Or just run it in a cwd context?
         pass
    
    # Better approach: Test the function directly bypassing main/argparse for unit test logic
    from workflow_core.knowledge.cli import install_hooks_command
    
    # Mock namespace
    args = MagicMock()
    
    # We need to change CWD to tmp_path for the function to find .git
    import os
    orig_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        ret = install_hooks_command(args)
        assert ret == 0
        assert (git_dir / "hooks" / "post-commit").exists()
    finally:
        os.chdir(orig_cwd)

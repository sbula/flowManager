
import sys
import unittest
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure we can import from workflow_core
root = Path(__file__).parent.parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from workflow_core.flow_manager.status_parser import StatusParser, StatusParsingError
import workflow_core.flow_manager.main as flow_main

# config_validator might not be importable if not yet renamed or path issue
try:
    from workflow_core.config_validator import validate_config
except ImportError:
    pass 

class TestFlowManagerHardening(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(__file__).parent / "temp_test_hardening"
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)
        
        self.config_dir = self.test_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir = self.test_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a dummy status file so parser doesn't crash on root finding
        (self.test_dir / "gemini.md").touch()
        (self.test_dir / "status.md").write_text("- [ ] 1. Test", encoding="utf-8")

    def tearDown(self):
         if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_01_config_auto_generation(self):
        """
        Proposal C: If config is missing, it should regenerate from Default Template.
        """
        # 1. Setup: Create Config Template
        default_config = {
            "prefixes": {}, 
            "strict_mode": True, 
            "generated": True,
            "root_markers": ["gemini.md"]
        }
        (self.templates_dir / "default_flow_config.json").write_text(json.dumps(default_config), encoding='utf-8')
        
        # 2. Setup: Ensure Target Config does NOT exist
        target_config = self.config_dir / "flow_config.json"
        if target_config.exists():
            target_config.unlink()
            
        # 3. Action: Initialize Parser (should trigger _load_config)
        parser = StatusParser(start_path=self.test_dir, config_root=self.config_dir)
        
        # 4. Assertion: Config file should have been created
        self.assertTrue(target_config.exists(), "Config file was not auto-generated")
        self.assertEqual(parser.config.get("generated"), True, "Config content mismatch")


    def test_02_strict_mode(self):
        """
        Proposal A: Strict Mode should raise error on unknown prefix.
        """
        # Setup Config with Strict Mode
        config = {
            "prefixes": {"planning": ["Plan"], "execution": ["Impl"]},
            "strict_mode": True,
            "root_markers": ["gemini.md"]
        }
        (self.config_dir / "flow_config.json").write_text(json.dumps(config), encoding='utf-8')
        
        parser = StatusParser(start_path=self.test_dir, config_root=self.config_dir)
        
        # Test Case: Unknown Prefix
        with self.assertRaises(StatusParsingError) as cm:
            parser._determine_workflow("Unknown.Prefix")
            
        self.assertIn("Unknown prefix", str(cm.exception))

    @patch("workflow_core.config_validator.validate_config")
    @patch("sys.exit")
    def test_03_validation_command(self, mock_exit, mock_validate_config):
        """
        Proposal B: Validate command should run config_validator.
        """
        # Setup: Mock StatusParser validation to pass
        with patch("workflow_core.flow_manager.main.StatusParser") as MockParser:
            instance = MockParser.return_value
            instance.validate_structure.return_value = None
            instance.get_active_context.return_value = {}
            
            # Mock argparse
            with patch("argparse.ArgumentParser.parse_args") as mock_args:
                mock_args.return_value.command = "validate"
                mock_args.return_value.debug = False
                mock_args.return_value.task_id = None
                mock_args.return_value.force_workflow = None

                # Setup: Config Validator returns True (Pass)
                mock_validate_config.return_value = True
                
                # Action
                flow_main.main()
                
                # Assertion
                mock_validate_config.assert_called_once()
                mock_exit.assert_not_called() 
                
                # Setup: Config Validator returns False (Fail)
                mock_validate_config.reset_mock()
                mock_validate_config.return_value = False
                mock_exit.reset_mock()
                
                # Action
                flow_main.main()
                
                # Assertion
                mock_validate_config.assert_called_once()
                mock_exit.assert_called_with(1)

if __name__ == "__main__":
    unittest.main()

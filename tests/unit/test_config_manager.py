"""
Unit tests for Configuration Manager module
"""

import pytest
import json
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET

# Add the lib directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/opnsense/scripts/hilink/lib'))

from config_manager import ConfigManager, ModemConfig, GeneralConfig, AlertConfig


class TestModemConfig:
    """Test cases for ModemConfig dataclass"""
    
    def test_default_values(self):
        """Test default values for ModemConfig"""
        config = ModemConfig()
        
        assert config.name == "HiLink Modem"
        assert config.enabled is True
        assert config.ip_address == "192.168.8.1"
        assert config.username == "admin"
        assert config.password == ""
        assert config.auto_connect is True
        assert config.roaming_enabled is False
        assert config.max_idle_time == 0
        assert config.network_mode == "auto"
        assert config.reconnect_interval == 60
        assert config.max_reconnect_attempts == 3
        assert config.collect_interval == 30
        assert config.signal_threshold == -90
        assert config.data_limit_enabled is False
        assert config.data_limit_mb == 10240
        assert config.alert_email == ""
    
    def test_custom_values(self):
        """Test creating ModemConfig with custom values"""
        config = ModemConfig(
            name="Test Modem",
            ip_address="192.168.10.1",
            username="testuser",
            password="testpass",
            roaming_enabled=True,
            network_mode="4g_only"
        )
        
        assert config.name == "Test Modem"
        assert config.ip_address == "192.168.10.1"
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.roaming_enabled is True
        assert config.network_mode == "4g_only"
    
    def test_to_dict(self):
        """Test converting ModemConfig to dictionary"""
        config = ModemConfig(name="Test Modem")
        data = config.to_dict()
        
        assert isinstance(data, dict)
        assert data['name'] == "Test Modem"
        assert 'uuid' in data
        assert 'enabled' in data
        assert 'ip_address' in data
    
    def test_from_dict(self):
        """Test creating ModemConfig from dictionary"""
        data = {
            'uuid': 'test-uuid-123',
            'name': 'Test Modem',
            'enabled': False,
            'ip_address': '192.168.20.1',
            'network_mode': '3g_preferred'
        }
        
        config = ModemConfig.from_dict(data)
        
        assert config.uuid == 'test-uuid-123'
        assert config.name == 'Test Modem'
        assert config.enabled is False
        assert config.ip_address == '192.168.20.1'
        assert config.network_mode == '3g_preferred'


class TestGeneralConfig:
    """Test cases for GeneralConfig dataclass"""
    
    def test_default_values(self):
        """Test default values for GeneralConfig"""
        config = GeneralConfig()
        
        assert config.enabled is True
        assert config.update_interval == 30
        assert config.data_retention == 30
        assert config.debug_logging is False
    
    def test_to_from_dict(self):
        """Test dictionary conversion"""
        config = GeneralConfig(
            enabled=False,
            update_interval=60,
            data_retention=7,
            debug_logging=True
        )
        
        data = config.to_dict()
        assert data['enabled'] is False
        assert data['update_interval'] == 60
        assert data['data_retention'] == 7
        assert data['debug_logging'] is True
        
        config2 = GeneralConfig.from_dict(data)
        assert config2.enabled is False
        assert config2.update_interval == 60
        assert config2.data_retention == 7
        assert config2.debug_logging is True


class TestAlertConfig:
    """Test cases for AlertConfig dataclass"""
    
    def test_default_values(self):
        """Test default values for AlertConfig"""
        config = AlertConfig()
        
        assert config.low_signal_threshold == -90
        assert config.data_limit_enabled is False
        assert config.data_limit_mb == 10240
        assert config.email_alerts is False
        assert config.smtp_port == 587
        assert config.smtp_use_tls is True


class TestConfigManager:
    """Test cases for ConfigManager class"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create ConfigManager instance with temp directory"""
        return ConfigManager(config_path=temp_config_dir)
    
    def test_initialization(self, config_manager, temp_config_dir):
        """Test ConfigManager initialization"""
        assert config_manager.config_path == Path(temp_config_dir)
        assert config_manager.config_file == Path(temp_config_dir) / "config.json"
        assert isinstance(config_manager.general, GeneralConfig)
        assert isinstance(config_manager.alerts, AlertConfig)
        assert isinstance(config_manager.modems, list)
    
    def test_ensure_directories(self, temp_config_dir):
        """Test directory creation"""
        subdir = os.path.join(temp_config_dir, "subdir")
        config_manager = ConfigManager(config_path=subdir)
        
        assert os.path.exists(subdir)
        assert os.path.isdir(subdir)
    
    def test_save_to_json(self, config_manager):
        """Test saving configuration to JSON"""
        # Add a modem
        modem = ModemConfig(name="Test Modem", ip_address="192.168.10.1")
        config_manager.modems.append(modem)
        
        # Save configuration
        result = config_manager._save_to_json()
        
        assert result is True
        assert config_manager.config_file.exists()
        
        # Load and verify JSON
        with open(config_manager.config_file, 'r') as f:
            data = json.load(f)
        
        assert 'general' in data
        assert 'modems' in data
        assert 'alerts' in data
        assert len(data['modems']) == 1
        assert data['modems'][0]['name'] == "Test Modem"
    
    def test_load_from_json(self, config_manager):
        """Test loading configuration from JSON"""
        # Create test configuration
        test_config = {
            'general': {
                'enabled': False,
                'update_interval': 60,
                'data_retention': 7,
                'debug_logging': True
            },
            'modems': [
                {
                    'uuid': 'test-uuid',
                    'name': 'Test Modem 1',
                    'ip_address': '192.168.8.1'
                },
                {
                    'uuid': 'test-uuid-2',
                    'name': 'Test Modem 2',
                    'ip_address': '192.168.10.1'
                }
            ],
            'alerts': {
                'low_signal_threshold': -85,
                'email_alerts': True
            }
        }
        
        # Save test configuration
        with open(config_manager.config_file, 'w') as f:
            json.dump(test_config, f)
        
        # Load configuration
        result = config_manager._load_from_json()
        
        assert result is True
        assert config_manager.general.enabled is False
        assert config_manager.general.update_interval == 60
        assert len(config_manager.modems) == 2
        assert config_manager.modems[0].name == "Test Modem 1"
        assert config_manager.modems[1].name == "Test Modem 2"
        assert config_manager.alerts.low_signal_threshold == -85
        assert config_manager.alerts.email_alerts is True
    
    def test_add_modem(self, config_manager):
        """Test adding a modem"""
        modem1 = ModemConfig(name="Modem 1")
        modem2 = ModemConfig(name="Modem 2")
        
        result1 = config_manager.add_modem(modem1)
        result2 = config_manager.add_modem(modem2)
        
        assert result1 is True
        assert result2 is True
        assert len(config_manager.modems) == 2
        
        # Try adding duplicate UUID
        modem3 = ModemConfig(uuid=modem1.uuid, name="Modem 3")
        result3 = config_manager.add_modem(modem3)
        
        assert result3 is False
        assert len(config_manager.modems) == 2
    
    def test_remove_modem(self, config_manager):
        """Test removing a modem"""
        modem1 = ModemConfig(name="Modem 1")
        modem2 = ModemConfig(name="Modem 2")
        
        config_manager.add_modem(modem1)
        config_manager.add_modem(modem2)
        
        assert len(config_manager.modems) == 2
        
        # Remove modem1
        result = config_manager.remove_modem(modem1.uuid)
        assert result is True
        assert len(config_manager.modems) == 1
        assert config_manager.modems[0].name == "Modem 2"
        
        # Try removing non-existent modem
        result = config_manager.remove_modem("non-existent-uuid")
        assert result is False
        assert len(config_manager.modems) == 1
    
    def test_get_modem(self, config_manager):
        """Test getting a modem by UUID"""
        modem = ModemConfig(name="Test Modem")
        config_manager.add_modem(modem)
        
        # Get existing modem
        retrieved = config_manager.get_modem(modem.uuid)
        assert retrieved is not None
        assert retrieved.name == "Test Modem"
        
        # Get non-existent modem
        retrieved = config_manager.get_modem("non-existent-uuid")
        assert retrieved is None
    
    def test_update_modem(self, config_manager):
        """Test updating modem configuration"""
        modem = ModemConfig(name="Original Name")
        config_manager.add_modem(modem)
        
        # Update modem
        updates = {
            'name': 'Updated Name',
            'ip_address': '192.168.20.1',
            'roaming_enabled': True
        }
        
        result = config_manager.update_modem(modem.uuid, updates)
        assert result is True
        
        updated = config_manager.get_modem(modem.uuid)
        assert updated.name == 'Updated Name'
        assert updated.ip_address == '192.168.20.1'
        assert updated.roaming_enabled is True
        
        # Try updating non-existent modem
        result = config_manager.update_modem("non-existent-uuid", updates)
        assert result is False
    
    def test_validate(self, config_manager):
        """Test configuration validation"""
        # Valid configuration
        errors = config_manager.validate()
        assert len(errors) == 1  # No modems configured
        
        # Add valid modem
        modem = ModemConfig(name="Test Modem")
        config_manager.add_modem(modem)
        errors = config_manager.validate()
        assert len(errors) == 0
        
        # Invalid update interval
        config_manager.general.update_interval = 5
        errors = config_manager.validate()
        assert len(errors) > 0
        assert any("Update interval" in error for error in errors)
        
        # Reset and test invalid IP
        config_manager.general.update_interval = 30
        modem.ip_address = "invalid-ip"
        errors = config_manager.validate()
        assert len(errors) > 0
        assert any("Invalid IP address" in error for error in errors)
        
        # Test invalid network mode
        modem.ip_address = "192.168.8.1"
        modem.network_mode = "invalid_mode"
        errors = config_manager.validate()
        assert len(errors) > 0
        assert any("Invalid network mode" in error for error in errors)
    
    def test_export_import_config(self, config_manager, temp_config_dir):
        """Test exporting and importing configuration"""
        # Setup configuration
        config_manager.general.update_interval = 45
        modem = ModemConfig(name="Export Test Modem")
        config_manager.add_modem(modem)
        config_manager.alerts.email_alerts = True
        # Add required email configuration when email_alerts is enabled
        config_manager.alerts.email_to = "test@example.com"
        config_manager.alerts.smtp_server = "smtp.example.com"
        
        # Export configuration
        export_file = os.path.join(temp_config_dir, "export.json")
        result = config_manager.export_config(export_file)
        assert result is True
        assert os.path.exists(export_file)
        
        # Create new config manager and import
        config_manager2 = ConfigManager(config_path=temp_config_dir)
        result = config_manager2.import_config(export_file)
        assert result is True
        
        # Verify imported configuration
        assert config_manager2.general.update_interval == 45
        assert len(config_manager2.modems) == 1
        assert config_manager2.modems[0].name == "Export Test Modem"
        assert config_manager2.alerts.email_alerts is True
        assert config_manager2.alerts.email_to == "test@example.com"
        assert config_manager2.alerts.smtp_server == "smtp.example.com"
    
    def test_password_encryption(self, config_manager):
        """Test password encryption/decryption"""
        password = "test_password_123"
        
        encrypted = config_manager._encrypt_password(password)
        assert encrypted != password
        assert len(encrypted) > 0
        
        decrypted = config_manager._decrypt_password(encrypted)
        assert decrypted == password
        
        # Test empty password
        encrypted = config_manager._encrypt_password("")
        assert encrypted == ""
        
        decrypted = config_manager._decrypt_password("")
        assert decrypted == ""
    
    def test_create_default_config(self, config_manager):
        """Test creating default configuration"""
        config_manager._create_default_config()
        
        assert len(config_manager.modems) == 1
        assert config_manager.modems[0].name == "HiLink Modem"
        assert config_manager.modems[0].ip_address == "192.168.8.1"
    
    def test_save_and_load_cycle(self, config_manager):
        """Test complete save and load cycle"""
        # Setup configuration
        config_manager.general.debug_logging = True
        modem1 = ModemConfig(name="Modem 1", ip_address="192.168.8.1")
        modem2 = ModemConfig(name="Modem 2", ip_address="192.168.10.1")
        config_manager.add_modem(modem1)
        config_manager.add_modem(modem2)
        config_manager.alerts.low_signal_threshold = -85
        
        # Save configuration
        result = config_manager.save()
        assert result is True
        
        # Create new instance and load
        config_manager2 = ConfigManager(config_path=config_manager.config_path)
        result = config_manager2.load()
        assert result is True
        
        # Verify loaded configuration
        assert config_manager2.general.debug_logging is True
        assert len(config_manager2.modems) == 2
        assert config_manager2.modems[0].name == "Modem 1"
        assert config_manager2.modems[1].name == "Modem 2"
        assert config_manager2.alerts.low_signal_threshold == -85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
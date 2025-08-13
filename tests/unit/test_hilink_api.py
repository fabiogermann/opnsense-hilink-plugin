"""
Unit tests for HiLink API module
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os

# Add the lib directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/opnsense/scripts/hilink/lib'))

from hilink_api import HiLinkModem, ModemStatus, SignalInfo, DataUsage, NetworkMode, ConnectionStatus, HiLinkException


class TestHiLinkModem:
    """Test cases for HiLinkModem class"""
    
    @pytest.fixture
    def modem(self):
        """Create a modem instance for testing"""
        return HiLinkModem(
            host="192.168.8.1",
            username="admin",
            password="admin123",
            name="Test Modem"
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, modem):
        """Test modem initialization"""
        assert modem.host == "192.168.8.1"
        assert modem.username == "admin"
        assert modem.password == "admin123"
        assert modem.name == "Test Modem"
        assert modem.base_url == "http://192.168.8.1"
        assert modem.session is None
        assert modem.logged_in is False
    
    @pytest.mark.asyncio
    async def test_connect_success(self, modem):
        """Test successful connection"""
        with patch.object(modem, '_initialize_session', new_callable=AsyncMock) as mock_init:
            with patch.object(modem, '_check_login_required', new_callable=AsyncMock) as mock_check:
                with patch.object(modem, 'login', new_callable=AsyncMock) as mock_login:
                    with patch('aiohttp.ClientSession') as mock_session:
                        mock_check.return_value = None
                        modem.login_required = False
                        
                        await modem.connect()
                        
                        assert modem.session is not None
                        mock_init.assert_called_once()
                        mock_check.assert_called_once()
                        mock_login.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_connect_with_login(self, modem):
        """Test connection with login required"""
        with patch.object(modem, '_initialize_session', new_callable=AsyncMock) as mock_init:
            with patch.object(modem, '_check_login_required', new_callable=AsyncMock) as mock_check:
                with patch.object(modem, 'login', new_callable=AsyncMock) as mock_login:
                    with patch('aiohttp.ClientSession') as mock_session:
                        mock_check.return_value = None
                        modem.login_required = True
                        modem.logged_in = False
                        
                        await modem.connect()
                        
                        assert modem.session is not None
                        mock_init.assert_called_once()
                        mock_check.assert_called_once()
                        mock_login.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, modem):
        """Test disconnection"""
        mock_session = AsyncMock()
        modem.session = mock_session
        modem.logged_in = True
        
        await modem.disconnect()
        
        mock_session.close.assert_called_once()
        assert modem.session is None
        assert modem.logged_in is False
    
    @pytest.mark.asyncio
    async def test_get_status(self, modem):
        """Test getting modem status"""
        mock_response_device = """
        <response>
            <DeviceName>E3372h-320</DeviceName>
            <Imei>123456789012345</Imei>
            <Iccid>89000000000000000000</Iccid>
        </response>
        """
        
        mock_response_status = """
        <response>
            <ConnectionStatus>901</ConnectionStatus>
            <CurrentNetworkType>19</CurrentNetworkType>
            <WanIPAddress>10.0.0.1</WanIPAddress>
            <SimStatus>1</SimStatus>
            <CurrentConnectTime>3600</CurrentConnectTime>
            <RoamingStatus>0</RoamingStatus>
        </response>
        """
        
        mock_response_network = """
        <response>
            <FullName>Test Carrier</FullName>
        </response>
        """
        
        with patch.object(modem, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                mock_response_device,
                mock_response_status,
                mock_response_network
            ]
            
            status = await modem.get_status()
            
            assert isinstance(status, ModemStatus)
            assert status.connected is True
            assert status.connection_status == ConnectionStatus.CONNECTED
            assert status.device_name == "E3372h-320"
            assert status.wan_ip == "10.0.0.1"
            assert status.network_operator == "Test Carrier"
    
    @pytest.mark.asyncio
    async def test_get_signal_info(self, modem):
        """Test getting signal information"""
        mock_response = """
        <response>
            <rssi>-65</rssi>
            <rsrp>-95</rsrp>
            <rsrq>-10</rsrq>
            <sinr>15</sinr>
            <cell_id>12345</cell_id>
            <band>B3</band>
            <arfcn>1800</arfcn>
        </response>
        """
        
        with patch.object(modem, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            signal = await modem.get_signal_info()
            
            assert isinstance(signal, SignalInfo)
            assert signal.rssi == -65
            assert signal.rsrp == -95
            assert signal.rsrq == -10
            assert signal.sinr == 15
            assert signal.signal_quality == "excellent"
            assert signal.signal_bars == 5
    
    @pytest.mark.asyncio
    async def test_get_data_usage(self, modem):
        """Test getting data usage"""
        mock_response_traffic = """
        <response>
            <CurrentUpload>1048576</CurrentUpload>
            <CurrentDownload>10485760</CurrentDownload>
            <CurrentConnectTime>3600</CurrentConnectTime>
            <TotalUpload>5242880</TotalUpload>
            <TotalDownload>52428800</TotalDownload>
            <TotalConnectTime>7200</TotalConnectTime>
        </response>
        """
        
        mock_response_month = """
        <response>
            <CurrentMonthUpload>1073741824</CurrentMonthUpload>
            <CurrentMonthDownload>10737418240</CurrentMonthDownload>
        </response>
        """
        
        with patch.object(modem, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                mock_response_traffic,
                mock_response_month
            ]
            
            usage = await modem.get_data_usage()
            
            assert isinstance(usage, DataUsage)
            assert usage.session_upload == 1048576
            assert usage.session_download == 10485760
            assert usage.total_upload == 5242880
            assert usage.total_download == 52428800
            assert usage.monthly_upload == 1073741824
            assert usage.monthly_download == 10737418240
    
    @pytest.mark.asyncio
    async def test_connect_modem(self, modem):
        """Test connecting the modem to network"""
        with patch.object(modem, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "<response>OK</response>"
            
            result = await modem.connect_modem()
            
            assert result is True
            mock_request.assert_called_once()
            # Check the positional arguments (method, endpoint, data)
            call_args = mock_request.call_args
            assert call_args[0][0] == 'POST'  # First arg is method
            assert '/api/dialup/mobile-dataswitch' in call_args[0][1]  # Second arg is endpoint
            if len(call_args[0]) > 2:
                assert '<dataswitch>1</dataswitch>' in call_args[0][2]  # Third arg is data
    
    @pytest.mark.asyncio
    async def test_disconnect_modem(self, modem):
        """Test disconnecting the modem from network"""
        with patch.object(modem, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = "<response>OK</response>"
            
            result = await modem.disconnect_modem()
            
            assert result is True
            mock_request.assert_called_once()
            # Check the positional arguments (method, endpoint, data)
            call_args = mock_request.call_args
            assert call_args[0][0] == 'POST'  # First arg is method
            assert '/api/dialup/mobile-dataswitch' in call_args[0][1]  # Second arg is endpoint
            if len(call_args[0]) > 2:
                assert '<dataswitch>0</dataswitch>' in call_args[0][2]  # Third arg is data
    
    @pytest.mark.asyncio
    async def test_set_network_mode(self, modem):
        """Test setting network mode"""
        mock_response = """
        <response>
            <NetworkBand>3FFFFFFF</NetworkBand>
            <LTEBand>7FFFFFFFFFFFFFFF</LTEBand>
        </response>
        """
        
        with patch.object(modem, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                mock_response,  # GET request
                "<response>OK</response>"  # POST request
            ]
            
            result = await modem.set_network_mode(NetworkMode.LTE_ONLY)
            
            assert result is True
            assert mock_request.call_count == 2
    
    @pytest.mark.asyncio
    async def test_set_roaming(self, modem):
        """Test enabling/disabling roaming"""
        mock_response = """
        <response>
            <MaxIdelTime>0</MaxIdelTime>
            <ConnectMode>0</ConnectMode>
            <MTU>1500</MTU>
            <auto_dial_switch>1</auto_dial_switch>
            <pdp_always_on>0</pdp_always_on>
        </response>
        """
        
        with patch.object(modem, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [
                mock_response,  # GET request
                "<response>OK</response>"  # POST request
            ]
            
            result = await modem.set_roaming(True)
            
            assert result is True
            assert mock_request.call_count == 2
            
            # Check that roaming was enabled in the POST data
            post_call = mock_request.call_args_list[1]
            # The second call should be POST with data
            assert post_call[0][0] == 'POST'  # First arg is method
            if len(post_call[0]) > 2:
                assert '<RoamAutoConnectEnable>1</RoamAutoConnectEnable>' in post_call[0][2]  # Third arg is data
    
    @pytest.mark.asyncio
    async def test_error_handling(self, modem):
        """Test error response handling"""
        error_response = """
        <error>
            <code>125003</code>
            <message>Wrong session token</message>
        </error>
        """
        
        # Should raise HiLinkException for error response
        with pytest.raises(HiLinkException) as exc_info:
            modem._check_response_error(error_response)
        
        assert exc_info.value.code == 125003
        assert "ERROR_WRONG_SESSION_TOKEN" in str(exc_info.value)
    
    def test_parse_int(self, modem):
        """Test integer parsing helper"""
        assert modem._parse_int("123") == 123
        assert modem._parse_int("-456") == -456
        assert modem._parse_int(None) is None
        assert modem._parse_int("invalid") is None
        assert modem._parse_int("") is None


class TestNetworkMode:
    """Test NetworkMode enum"""
    
    def test_network_mode_values(self):
        """Test network mode enum values"""
        assert NetworkMode.AUTO.value == "00"
        assert NetworkMode.GSM_ONLY.value == "01"
        assert NetworkMode.WCDMA_ONLY.value == "02"
        assert NetworkMode.LTE_ONLY.value == "03"
        assert NetworkMode.LTE_WCDMA_GSM.value == "030201"


class TestConnectionStatus:
    """Test ConnectionStatus enum"""
    
    def test_connection_status_values(self):
        """Test connection status enum values"""
        assert ConnectionStatus.DISCONNECTED.value == 0
        assert ConnectionStatus.CONNECTING.value == 1
        assert ConnectionStatus.CONNECTED.value == 2
        assert ConnectionStatus.DISCONNECTING.value == 3
        assert ConnectionStatus.UNKNOWN.value == -1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
"""
Async HiLink API wrapper for Huawei modems
Based on the original HiLinkAPI but with async support and enhanced features
"""

import asyncio
import aiohttp
import logging
import hashlib
import base64
import hmac
import uuid
import time
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import xmltodict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class NetworkMode(Enum):
    """Network mode enumeration"""
    AUTO = "00"
    GSM_ONLY = "01"
    WCDMA_ONLY = "02"
    LTE_ONLY = "03"
    WCDMA_GSM = "0201"
    LTE_WCDMA = "0302"
    LTE_GSM = "0301"
    LTE_WCDMA_GSM = "030201"


class ConnectionStatus(Enum):
    """Connection status enumeration"""
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3
    UNKNOWN = -1


@dataclass
class ModemStatus:
    """Modem status information"""
    connected: bool
    connection_status: ConnectionStatus
    network_type: str
    network_operator: str
    wan_ip: Optional[str]
    sim_status: str
    device_name: str
    imei: str
    iccid: str
    connection_time: int
    roaming: bool


@dataclass
class SignalInfo:
    """Signal information"""
    rssi: int  # Signal strength in dBm
    rsrp: Optional[int]  # Reference Signal Received Power (LTE)
    rsrq: Optional[int]  # Reference Signal Received Quality (LTE)
    sinr: Optional[int]  # Signal to Interference plus Noise Ratio (LTE)
    signal_bars: int  # 0-5 bars
    signal_quality: str  # excellent/good/fair/poor
    cell_id: Optional[int]
    band: Optional[str]
    frequency: Optional[int]


@dataclass
class DataUsage:
    """Data usage statistics"""
    session_upload: int  # Bytes
    session_download: int  # Bytes
    session_total: int  # Bytes
    total_upload: int  # Bytes
    total_download: int  # Bytes
    total_total: int  # Bytes
    monthly_upload: int  # Bytes
    monthly_download: int  # Bytes
    monthly_total: int  # Bytes


class HiLinkException(Exception):
    """HiLink API exception"""
    def __init__(self, message: str, code: Optional[int] = None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class HiLinkModem:
    """Async HiLink modem API wrapper"""
    
    # Error codes mapping
    ERROR_CODES = {
        100002: "ERROR_SYSTEM_NO_SUPPORT",
        100003: "ERROR_SYSTEM_NO_RIGHTS",
        100004: "ERROR_BUSY",
        108001: "ERROR_LOGIN_USERNAME_WRONG",
        108002: "ERROR_LOGIN_PASSWORD_WRONG",
        108003: "ERROR_LOGIN_ALREADY_LOGIN",
        108006: "ERROR_LOGIN_USERNAME_OR_PASSWORD_ERROR",
        108007: "ERROR_LOGIN_TOO_MANY_TIMES",
        125001: "ERROR_WRONG_TOKEN",
        125002: "ERROR_WRONG_SESSION",
        125003: "ERROR_WRONG_SESSION_TOKEN",
    }
    
    def __init__(self, 
                 host: str,
                 username: str = "admin",
                 password: str = "",
                 timeout: int = 10,
                 name: str = "HiLink Modem"):
        """
        Initialize HiLink modem connection
        
        Args:
            host: Modem IP address (e.g., "192.168.8.1")
            username: Admin username
            password: Admin password
            timeout: HTTP request timeout in seconds
            name: Friendly name for the modem
        """
        self.host = host
        self.base_url = f"http://{host}"
        self.username = username
        self.password = password
        self.timeout = timeout
        self.name = name
        
        # Session management
        self.session: Optional[aiohttp.ClientSession] = None
        self.session_id: Optional[str] = None
        self.request_token: Optional[str] = None
        self.webui_version: Optional[int] = None
        self.login_required: bool = False
        self.logged_in: bool = False
        
        # Device info cache
        self._device_info: Dict[str, Any] = {}
        self._last_status_update: float = 0
        self._status_cache_ttl: float = 5.0  # Cache for 5 seconds
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
        
    async def connect(self):
        """Initialize connection to modem"""
        if self.session:
            await self.disconnect()
            
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        
        try:
            # Initialize session
            await self._initialize_session()
            
            # Check if login is required
            await self._check_login_required()
            
            # Login if necessary
            if self.login_required and not self.logged_in:
                await self.login()
                
            logger.info(f"Connected to modem {self.name} at {self.host}")
            
        except Exception as e:
            await self.disconnect()
            raise HiLinkException(f"Failed to connect to modem: {e}")
            
    async def disconnect(self):
        """Close connection to modem"""
        if self.session:
            await self.session.close()
            self.session = None
            self.logged_in = False
            logger.info(f"Disconnected from modem {self.name}")
            
    async def _request(self, 
                      method: str,
                      endpoint: str,
                      data: Optional[str] = None,
                      headers: Optional[Dict[str, str]] = None) -> str:
        """
        Make HTTP request to modem
        
        Args:
            method: HTTP method (GET/POST)
            endpoint: API endpoint
            data: Request body (XML string)
            headers: Additional headers
            
        Returns:
            Response text
        """
        if not self.session:
            raise HiLinkException("Not connected to modem")
            
        url = f"{self.base_url}{endpoint}"
        
        # Build headers
        request_headers = {
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        if self.request_token:
            request_headers['__RequestVerificationToken'] = self.request_token
            
        if headers:
            request_headers.update(headers)
            
        # Build cookies
        cookies = {}
        if self.session_id:
            cookies['SessionID'] = self.session_id
            
        try:
            async with self.session.request(
                method=method,
                url=url,
                data=data,
                headers=request_headers,
                cookies=cookies
            ) as response:
                # Update session info from response
                self._update_session_info(response)
                
                text = await response.text()
                
                # Check for errors
                self._check_response_error(text)
                
                return text
                
        except aiohttp.ClientError as e:
            raise HiLinkException(f"Request failed: {e}")
            
    def _update_session_info(self, response: aiohttp.ClientResponse):
        """Update session ID and request token from response"""
        # Update session ID from cookies
        if 'SessionID' in response.cookies:
            self.session_id = response.cookies['SessionID'].value
            
        # Update request token from headers
        if '__RequestVerificationToken' in response.headers:
            token = response.headers['__RequestVerificationToken']
            if '#' in token:
                token = token.split('#')[0]
            self.request_token = token
            
    def _check_response_error(self, response_text: str):
        """Check response for errors"""
        try:
            data = xmltodict.parse(response_text)
            if 'error' in data:
                error_code = int(data['error'].get('code', 0))
                error_msg = self.ERROR_CODES.get(error_code, "Unknown error")
                raise HiLinkException(f"{error_msg} (code: {error_code})", error_code)
        except (ValueError, KeyError):
            # Not an error response
            pass
            
    async def _initialize_session(self):
        """Initialize session and get tokens"""
        # Get initial session
        await self._request('GET', '/')
        
        # Try to get token (WebUI 10/21)
        try:
            response = await self._request('GET', '/api/webserver/token')
            token_data = xmltodict.parse(response)
            if 'response' in token_data and 'token' in token_data['response']:
                token = token_data['response']['token']
                self.request_token = token[-32:]
                self.webui_version = 10
                
                # Check if it's version 21
                try:
                    response = await self._request('GET', '/api/device/basic_information')
                    device_data = xmltodict.parse(response)
                    if 'response' in device_data and 'WebUIVersion' in device_data['response']:
                        if '21.' in device_data['response']['WebUIVersion']:
                            self.webui_version = 21
                except:
                    pass
                    
        except:
            # Try WebUI 17
            try:
                response = await self._request('GET', '/html/home.html')
                soup = BeautifulSoup(response, 'html.parser')
                meta = soup.find('meta', {'name': 'csrf_token'})
                if meta:
                    self.request_token = meta.get('content')
                    self.webui_version = 17
            except:
                pass
                
        if not self.request_token:
            raise HiLinkException("Failed to get request token")
            
        logger.debug(f"WebUI version: {self.webui_version}")
        
    async def _check_login_required(self):
        """Check if login is required"""
        try:
            response = await self._request('GET', '/api/user/hilink_login')
            data = xmltodict.parse(response)
            
            if 'response' in data and 'hilink_login' in data['response']:
                hilink_login = int(data['response']['hilink_login'])
                self.login_required = (hilink_login == 1)
                
                # Get device info to check if it's a wingle/mobile-wifi
                response = await self._request('GET', '/api/device/basic_information')
                device_data = xmltodict.parse(response)
                
                if 'response' in device_data:
                    device_classify = device_data['response'].get('classify', '').upper()
                    if device_classify in ('WINGLE', 'MOBILE-WIFI'):
                        self.login_required = True
                        
        except Exception as e:
            logger.warning(f"Could not check login requirement: {e}")
            self.login_required = False
            
    async def login(self):
        """Login to modem"""
        if not self.username or not self.password:
            raise HiLinkException("Username and password required for login")
            
        # Check login state first
        response = await self._request('GET', '/api/user/state-login')
        state_data = xmltodict.parse(response)
        
        if 'response' in state_data:
            state = int(state_data['response'].get('State', -1))
            if state == 0:
                self.logged_in = True
                return  # Already logged in
                
            password_type = int(state_data['response'].get('password_type', 4))
            
        if self.webui_version in (17, 21):
            await self._login_webui_17_21(password_type)
        else:
            await self._login_webui_10()
            
        self.logged_in = True
        logger.info(f"Successfully logged in to modem {self.name}")
        
    async def _login_webui_17_21(self, password_type: int):
        """Login for WebUI version 17 and 21"""
        # Hash password
        password_hash = hashlib.sha256(self.password.encode()).hexdigest()
        password_base64 = base64.b64encode(bytes.fromhex(password_hash)).decode()
        
        # Hash username + password + token
        auth_string = f"{self.username}{password_base64}{self.request_token}"
        auth_hash = hashlib.sha256(auth_string.encode()).hexdigest()
        auth_base64 = base64.b64encode(bytes.fromhex(auth_hash)).decode()
        
        # Build login XML
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <Username>{self.username}</Username>
            <Password>{auth_base64}</Password>
            <password_type>{password_type}</password_type>
        </request>"""
        
        response = await self._request('POST', '/api/user/login', data=xml_data)
        login_data = xmltodict.parse(response)
        
        if 'response' not in login_data or login_data['response'] != 'OK':
            raise HiLinkException("Login failed")
            
    async def _login_webui_10(self):
        """Login for WebUI version 10"""
        # Get fresh token
        response = await self._request('GET', '/api/webserver/token')
        token_data = xmltodict.parse(response)
        if 'response' in token_data and 'token' in token_data['response']:
            token = token_data['response']['token']
            self.request_token = token[-32:]
            
        # Generate client nonce
        client_nonce = uuid.uuid4().hex + uuid.uuid4().hex
        
        # Challenge login
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <username>{self.username}</username>
            <firstnonce>{client_nonce}</firstnonce>
            <mode>1</mode>
        </request>"""
        
        response = await self._request('POST', '/api/user/challenge_login', data=xml_data)
        challenge_data = xmltodict.parse(response)
        
        if 'response' not in challenge_data:
            raise HiLinkException("Challenge login failed")
            
        salt = challenge_data['response']['salt']
        server_nonce = challenge_data['response']['servernonce']
        iterations = int(challenge_data['response']['iterations'])
        
        # Calculate auth proof
        msg = f"{client_nonce},{server_nonce},{server_nonce}"
        salted_pass = hashlib.pbkdf2_hmac(
            'sha256',
            self.password.encode(),
            bytes.fromhex(salt),
            iterations
        )
        
        client_key = hmac.new(b'Client Key', salted_pass, hashlib.sha256).digest()
        stored_key = hashlib.sha256(client_key).digest()
        signature = hmac.new(msg.encode(), stored_key, hashlib.sha256).digest()
        
        client_proof = bytes(a ^ b for a, b in zip(client_key, signature))
        
        # Authentication login
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <clientproof>{client_proof.hex()}</clientproof>
            <finalnonce>{server_nonce}</finalnonce>
        </request>"""
        
        response = await self._request('POST', '/api/user/authentication_login', data=xml_data)
        login_data = xmltodict.parse(response)
        
        if 'response' not in login_data:
            raise HiLinkException("Authentication login failed")
            
    async def get_status(self) -> ModemStatus:
        """Get current modem status"""
        # Get device information
        response = await self._request('GET', '/api/device/information')
        device_data = xmltodict.parse(response)
        
        # Get monitoring status
        response = await self._request('GET', '/api/monitoring/status')
        status_data = xmltodict.parse(response)
        
        # Get network info
        response = await self._request('GET', '/api/net/current-plmn')
        network_data = xmltodict.parse(response)
        
        # Parse data
        device_info = device_data.get('response', {})
        status_info = status_data.get('response', {})
        network_info = network_data.get('response', {})
        
        # Determine connection status
        connection_status_code = int(status_info.get('ConnectionStatus', '0'))
        if connection_status_code == 901:
            connection_status = ConnectionStatus.CONNECTED
            connected = True
        elif connection_status_code == 900:
            connection_status = ConnectionStatus.CONNECTING
            connected = False
        elif connection_status_code == 902:
            connection_status = ConnectionStatus.DISCONNECTED
            connected = False
        elif connection_status_code == 903:
            connection_status = ConnectionStatus.DISCONNECTING
            connected = False
        else:
            connection_status = ConnectionStatus.UNKNOWN
            connected = False
            
        return ModemStatus(
            connected=connected,
            connection_status=connection_status,
            network_type=status_info.get('CurrentNetworkType', 'Unknown'),
            network_operator=network_info.get('FullName', 'Unknown'),
            wan_ip=status_info.get('WanIPAddress'),
            sim_status=status_info.get('SimStatus', 'Unknown'),
            device_name=device_info.get('DeviceName', 'Unknown'),
            imei=device_info.get('Imei', ''),
            iccid=device_info.get('Iccid', ''),
            connection_time=int(status_info.get('CurrentConnectTime', '0')),
            roaming=status_info.get('RoamingStatus', '0') == '1'
        )
        
    async def get_signal_info(self) -> SignalInfo:
        """Get signal information"""
        response = await self._request('GET', '/api/device/signal')
        data = xmltodict.parse(response)
        
        if 'response' not in data:
            raise HiLinkException("Failed to get signal info")
            
        signal_data = data['response']
        
        # Parse signal strength
        rssi = int(signal_data.get('rssi', '0'))
        if rssi > 0:
            rssi = -113 + (rssi * 2)  # Convert to dBm
            
        # Determine signal quality
        if rssi >= -65:
            quality = "excellent"
            bars = 5
        elif rssi >= -75:
            quality = "good"
            bars = 4
        elif rssi >= -85:
            quality = "fair"
            bars = 3
        elif rssi >= -95:
            quality = "poor"
            bars = 2
        elif rssi >= -105:
            quality = "very poor"
            bars = 1
        else:
            quality = "no signal"
            bars = 0
            
        return SignalInfo(
            rssi=rssi,
            rsrp=self._parse_int(signal_data.get('rsrp')),
            rsrq=self._parse_int(signal_data.get('rsrq')),
            sinr=self._parse_int(signal_data.get('sinr')),
            signal_bars=bars,
            signal_quality=quality,
            cell_id=self._parse_int(signal_data.get('cell_id')),
            band=signal_data.get('band'),
            frequency=self._parse_int(signal_data.get('arfcn'))
        )
        
    async def get_data_usage(self) -> DataUsage:
        """Get data usage statistics"""
        response = await self._request('GET', '/api/monitoring/traffic-statistics')
        data = xmltodict.parse(response)
        
        if 'response' not in data:
            raise HiLinkException("Failed to get data usage")
            
        traffic_data = data['response']
        
        # Get monthly statistics
        response = await self._request('GET', '/api/monitoring/month_statistics')
        month_data = xmltodict.parse(response)
        
        monthly_stats = month_data.get('response', {})
        
        return DataUsage(
            session_upload=int(traffic_data.get('CurrentUpload', '0')),
            session_download=int(traffic_data.get('CurrentDownload', '0')),
            session_total=int(traffic_data.get('CurrentConnectTime', '0')),
            total_upload=int(traffic_data.get('TotalUpload', '0')),
            total_download=int(traffic_data.get('TotalDownload', '0')),
            total_total=int(traffic_data.get('TotalConnectTime', '0')),
            monthly_upload=int(monthly_stats.get('CurrentMonthUpload', '0')),
            monthly_download=int(monthly_stats.get('CurrentMonthDownload', '0')),
            monthly_total=(
                int(monthly_stats.get('CurrentMonthUpload', '0')) +
                int(monthly_stats.get('CurrentMonthDownload', '0'))
            )
        )
        
    async def connect_modem(self) -> bool:
        """Connect the modem to the network"""
        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <dataswitch>1</dataswitch>
        </request>"""
        
        try:
            await self._request('POST', '/api/dialup/mobile-dataswitch', data=xml_data)
            logger.info(f"Modem {self.name} connected to network")
            return True
        except HiLinkException as e:
            logger.error(f"Failed to connect modem: {e}")
            return False
            
    async def disconnect_modem(self) -> bool:
        """Disconnect the modem from the network"""
        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <dataswitch>0</dataswitch>
        </request>"""
        
        try:
            await self._request('POST', '/api/dialup/mobile-dataswitch', data=xml_data)
            logger.info(f"Modem {self.name} disconnected from network")
            return True
        except HiLinkException as e:
            logger.error(f"Failed to disconnect modem: {e}")
            return False
            
    async def reboot(self) -> bool:
        """Reboot the modem"""
        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <Control>1</Control>
        </request>"""
        
        try:
            # This will timeout as modem reboots, but that's expected
            await self._request('POST', '/api/device/control', data=xml_data)
        except:
            pass  # Expected to fail as modem reboots
            
        logger.info(f"Modem {self.name} reboot initiated")
        return True
        
    async def set_network_mode(self, mode: NetworkMode) -> bool:
        """Set network mode"""
        # Get current band settings
        response = await self._request('GET', '/api/net/net-mode')
        data = xmltodict.parse(response)
        
        if 'response' not in data:
            return False
            
        current_data = data['response']
        
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <NetworkMode>{mode.value}</NetworkMode>
            <NetworkBand>{current_data.get('NetworkBand', '3FFFFFFF')}</NetworkBand>
            <LTEBand>{current_data.get('LTEBand', '7FFFFFFFFFFFFFFF')}</LTEBand>
        </request>"""
        
        try:
            await self._request('POST', '/api/net/net-mode', data=xml_data)
            logger.info(f"Network mode set to {mode.name} for modem {self.name}")
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set network mode: {e}")
            return False
            
    async def set_roaming(self, enabled: bool) -> bool:
        """Enable or disable roaming"""
        # Get current connection settings
        response = await self._request('GET', '/api/dialup/connection')
        data = xmltodict.parse(response)
        
        if 'response' not in data:
            return False
            
        current_data = data['response']
        
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <RoamAutoConnectEnable>{1 if enabled else 0}</RoamAutoConnectEnable>
            <MaxIdelTime>{current_data.get('MaxIdelTime', '0')}</MaxIdelTime>
            <ConnectMode>{current_data.get('ConnectMode', '0')}</ConnectMode>
            <MTU>{current_data.get('MTU', '1500')}</MTU>
            <auto_dial_switch>{current_data.get('auto_dial_switch', '1')}</auto_dial_switch>
            <pdp_always_on>{current_data.get('pdp_always_on', '0')}</pdp_always_on>
        </request>"""
        
        try:
            await self._request('POST', '/api/dialup/connection', data=xml_data)
            logger.info(f"Roaming {'enabled' if enabled else 'disabled'} for modem {self.name}")
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set roaming: {e}")
            return False
            
    def _parse_int(self, value: Any) -> Optional[int]:
        """Safely parse integer value"""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None


# Example usage and testing
async def test_modem():
    """Test modem connection and operations"""
    modem = HiLinkModem(
        host="192.168.8.1",
        username="admin",
        password="admin"
    )
    
    async with modem:
        # Get status
        status = await modem.get_status()
        print(f"Modem Status: {status}")
        
        # Get signal info
        signal = await modem.get_signal_info()
        print(f"Signal Info: {signal}")
        
        # Get data usage
        usage = await modem.get_data_usage()
        print(f"Data Usage: {usage}")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_modem())
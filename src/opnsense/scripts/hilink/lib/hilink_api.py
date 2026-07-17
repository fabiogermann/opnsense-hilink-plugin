"""
Async HiLink API wrapper for Huawei modems
Based on the original HiLinkAPI but with async support and enhanced features
"""

import asyncio
import httpx
import logging
import hashlib
import base64
import hmac
import uuid
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


import xml.etree.ElementTree as _ET
from html.parser import HTMLParser as _HTMLParser


def _elem_to_dict(elem):
    """Convert an ElementTree Element to a dict, mimicking xmltodict semantics."""
    out = {}
    for k, v in elem.attrib.items():
        out["@" + k] = v
    text = (elem.text or "").strip()
    children = list(elem)
    if children:
        for child in children:
            tag = child.tag
            if isinstance(tag, str) and "}" in tag:
                tag = tag.split("}", 1)[1]
            child_val = _elem_to_dict(child)
            if tag in out:
                if not isinstance(out[tag], list):
                    out[tag] = [out[tag]]
                out[tag].append(child_val)
            else:
                out[tag] = child_val
        return out
    return text if text else None


def xml_to_dict(xml_text):
    """Mimic xmltodict.parse(): returns {root_tag: <root content>}."""
    root = _ET.fromstring(xml_text)
    tag = root.tag
    if isinstance(tag, str) and "}" in tag:
        tag = tag.split("}", 1)[1]
    return {tag: _elem_to_dict(root)}


class _MetaExtractor(_HTMLParser):
    def __init__(self):
        super().__init__()
        self.metas = []

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            self.metas.append(dict(attrs))


def _find_meta_content(html_text, name):
    p = _MetaExtractor()
    try:
        p.feed(html_text)
    except Exception:
        return None
    for m in p.metas:
        if m.get("name") == name:
            return m.get("content")
    return None


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

    # CurrentNetworkType codes as reported by /api/monitoring/status
    NETWORK_TYPES = {
        0: "No Service",
        1: "GSM",
        2: "GPRS (2G)",
        3: "EDGE (2G)",
        4: "WCDMA (3G)",
        5: "HSDPA (3G)",
        6: "HSUPA (3G)",
        7: "HSPA (3G)",
        8: "TD-SCDMA (3G)",
        9: "HSPA+ (3G)",
        10: "EV-DO rev. 0",
        11: "EV-DO rev. A",
        12: "EV-DO rev. B",
        13: "1xRTT",
        16: "1xEV-DV",
        17: "3xRTT",
        18: "HSPA+ 64QAM (3G)",
        19: "LTE (4G)",
        41: "WCDMA (3G)",
        44: "HSPA (3G)",
        45: "HSPA+ (3G)",
        46: "DC-HSPA+ (3G)",
        64: "HSPA (3G)",
        65: "HSPA+ (3G)",
        101: "LTE (4G)",
        111: "NR (5G)",
    }

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

    def __init__(  # nosec
        self,
        host: str,
        username: str = "admin",
        password: str = "",
        timeout: int = 10,
        name: str = "HiLink Modem",
    ):
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
        self.session: Optional[httpx.AsyncClient] = None
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

        self.session = httpx.AsyncClient(timeout=self.timeout)

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
            await self.session.aclose()
            self.session = None
            self.logged_in = False
            logger.info(f"Disconnected from modem {self.name}")

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> str:
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
        request_headers = {"X-Requested-With": "XMLHttpRequest"}

        if self.request_token:
            request_headers["__RequestVerificationToken"] = self.request_token

        if headers:
            request_headers.update(headers)

        # Build cookies
        cookies = {}
        if self.session_id:
            cookies["SessionID"] = self.session_id

        try:
            response = await self.session.request(
                method, url, content=data, headers=request_headers, cookies=cookies,
            )
            self._update_session_info(response)
            text = response.text
            self._check_response_error(text)
            return text

        except httpx.HTTPError as e:
            raise HiLinkException(f"Request failed: {e}")

    def _update_session_info(self, response: httpx.Response):
        """Update session ID and request token from response"""
        # Update session ID from cookies
        if "SessionID" in response.cookies:
            self.session_id = response.cookies["SessionID"]

        # Update request token from headers
        if "__RequestVerificationToken" in response.headers:
            token = response.headers["__RequestVerificationToken"]
            if "#" in token:
                token = token.split("#")[0]
            self.request_token = token

    def _check_response_error(self, response_text: str):
        """Check response for errors"""
        try:
            data = xml_to_dict(response_text)
        except Exception:
            # Not XML (e.g. an HTML page) - nothing to check
            return

        try:
            if "error" in data:
                error_code = int(data["error"].get("code", 0))
                error_msg = self.ERROR_CODES.get(error_code, "Unknown error")
                raise HiLinkException(f"{error_msg} (code: {error_code})", error_code)
        except (ValueError, KeyError, TypeError):
            # Malformed error payload - treat as non-error response
            pass

    async def _initialize_session(self):
        """Initialize session and get tokens"""
        # Get initial session
        await self._request("GET", "/")

        # Try to get token (WebUI 10/21)
        try:
            response = await self._request("GET", "/api/webserver/token")
            token_data = xml_to_dict(response)
            if "response" in token_data and "token" in token_data["response"]:
                token = token_data["response"]["token"]
                self.request_token = token[-32:]
                self.webui_version = 10

                # Check if it's version 21
                try:
                    response = await self._request(
                        "GET", "/api/device/basic_information"
                    )
                    device_data = xml_to_dict(response)
                    if (
                        "response" in device_data
                        and "WebUIVersion" in device_data["response"]
                    ):
                        if "21." in device_data["response"]["WebUIVersion"]:
                            self.webui_version = 21
                except:
                    pass  # nosec

        except:
            # Try WebUI 17
            try:
                response = await self._request("GET", "/html/home.html")
                content = _find_meta_content(response, "csrf_token")
                if content:
                    self.request_token = content
                    self.webui_version = 17
            except:
                pass  # nosec

        if not self.request_token:
            raise HiLinkException("Failed to get request token")

        logger.debug(f"WebUI version: {self.webui_version}")

    async def _check_login_required(self):
        """Check if login is required"""
        try:
            response = await self._request("GET", "/api/user/hilink_login")
            data = xml_to_dict(response)

            if "response" in data and "hilink_login" in data["response"]:
                hilink_login = int(data["response"]["hilink_login"])
                self.login_required = hilink_login == 1

                # Get device info to check if it's a wingle/mobile-wifi
                response = await self._request("GET", "/api/device/basic_information")
                device_data = xml_to_dict(response)

                if "response" in device_data:
                    device_classify = (
                        device_data["response"].get("classify", "").upper()
                    )
                    if device_classify in ("WINGLE", "MOBILE-WIFI"):
                        self.login_required = True

        except Exception as e:
            logger.warning(f"Could not check login requirement: {e}")
            self.login_required = False

    async def login(self):
        """Login to modem"""
        if not self.username or not self.password:
            raise HiLinkException("Username and password required for login")

        # Check login state first
        password_type = 4
        response = await self._request("GET", "/api/user/state-login")
        state_data = xml_to_dict(response)

        if "response" in state_data:
            state = int(state_data["response"].get("State", -1))
            if state == 0:
                self.logged_in = True
                return  # Already logged in

            password_type = int(state_data["response"].get("password_type", 4))

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

        response = await self._request("POST", "/api/user/login", data=xml_data)
        login_data = xml_to_dict(response)

        if "response" not in login_data or login_data["response"] != "OK":
            raise HiLinkException("Login failed")

    async def _login_webui_10(self):
        """Login for WebUI version 10"""
        # Get fresh token
        response = await self._request("GET", "/api/webserver/token")
        token_data = xml_to_dict(response)
        if "response" in token_data and "token" in token_data["response"]:
            token = token_data["response"]["token"]
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

        response = await self._request(
            "POST", "/api/user/challenge_login", data=xml_data
        )
        challenge_data = xml_to_dict(response)

        if "response" not in challenge_data:
            raise HiLinkException("Challenge login failed")

        salt = challenge_data["response"]["salt"]
        server_nonce = challenge_data["response"]["servernonce"]
        iterations = int(challenge_data["response"]["iterations"])

        # Calculate auth proof
        msg = f"{client_nonce},{server_nonce},{server_nonce}"
        salted_pass = hashlib.pbkdf2_hmac(
            "sha256", self.password.encode(), bytes.fromhex(salt), iterations
        )

        client_key = hmac.new(b"Client Key", salted_pass, hashlib.sha256).digest()
        stored_key = hashlib.sha256(client_key).digest()
        signature = hmac.new(msg.encode(), stored_key, hashlib.sha256).digest()

        client_proof = bytes(a ^ b for a, b in zip(client_key, signature))

        # Authentication login
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <clientproof>{client_proof.hex()}</clientproof>
            <finalnonce>{server_nonce}</finalnonce>
        </request>"""

        response = await self._request(
            "POST", "/api/user/authentication_login", data=xml_data
        )
        login_data = xml_to_dict(response)

        if "response" not in login_data:
            raise HiLinkException("Authentication login failed")

    async def get_status(self) -> ModemStatus:
        """Get current modem status"""
        # Get device information
        response = await self._request("GET", "/api/device/information")
        device_data = xml_to_dict(response)

        # Get monitoring status
        response = await self._request("GET", "/api/monitoring/status")
        status_data = xml_to_dict(response)

        # Get network info
        response = await self._request("GET", "/api/net/current-plmn")
        network_data = xml_to_dict(response)

        # Parse data
        device_info = device_data.get("response", {})
        status_info = status_data.get("response", {})
        network_info = network_data.get("response", {})

        # Determine connection status
        connection_status_code = int(status_info.get("ConnectionStatus", "0"))
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

        # Translate the numeric CurrentNetworkType code to a readable name
        raw_network_type = status_info.get("CurrentNetworkType", "")
        network_type_code = self._parse_int(raw_network_type)
        if network_type_code is not None:
            network_type = self.NETWORK_TYPES.get(
                network_type_code, f"Unknown ({network_type_code})"
            )
        else:
            network_type = raw_network_type or "Unknown"

        return ModemStatus(
            connected=connected,
            connection_status=connection_status,
            network_type=network_type,
            network_operator=network_info.get("FullName", "Unknown"),
            wan_ip=status_info.get("WanIPAddress"),
            sim_status=status_info.get("SimStatus", "Unknown"),
            device_name=device_info.get("DeviceName", "Unknown"),
            imei=device_info.get("Imei", ""),
            iccid=device_info.get("Iccid", ""),
            connection_time=int(status_info.get("CurrentConnectTime", "0")),
            roaming=status_info.get("RoamingStatus", "0") == "1",
        )

    async def get_signal_info(self) -> SignalInfo:
        """Get signal information"""
        response = await self._request("GET", "/api/device/signal")
        data = xml_to_dict(response)

        if "response" not in data:
            raise HiLinkException("Failed to get signal info")

        signal_data = data["response"]

        # Parse signal strength
        rssi = int(signal_data.get("rssi", "0"))
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
            rsrp=self._parse_int(signal_data.get("rsrp")),
            rsrq=self._parse_int(signal_data.get("rsrq")),
            sinr=self._parse_int(signal_data.get("sinr")),
            signal_bars=bars,
            signal_quality=quality,
            cell_id=self._parse_int(signal_data.get("cell_id")),
            band=signal_data.get("band"),
            frequency=self._parse_int(signal_data.get("arfcn")),
        )

    async def get_data_usage(self) -> DataUsage:
        """Get data usage statistics"""
        response = await self._request("GET", "/api/monitoring/traffic-statistics")
        data = xml_to_dict(response)

        if "response" not in data:
            raise HiLinkException("Failed to get data usage")

        traffic_data = data["response"]

        # Get monthly statistics
        response = await self._request("GET", "/api/monitoring/month_statistics")
        month_data = xml_to_dict(response)

        monthly_stats = month_data.get("response", {})

        session_upload = int(traffic_data.get("CurrentUpload", "0"))
        session_download = int(traffic_data.get("CurrentDownload", "0"))
        total_upload = int(traffic_data.get("TotalUpload", "0"))
        total_download = int(traffic_data.get("TotalDownload", "0"))

        return DataUsage(
            session_upload=session_upload,
            session_download=session_download,
            session_total=session_upload + session_download,
            total_upload=total_upload,
            total_download=total_download,
            total_total=total_upload + total_download,
            monthly_upload=int(monthly_stats.get("CurrentMonthUpload", "0")),
            monthly_download=int(monthly_stats.get("CurrentMonthDownload", "0")),
            monthly_total=(
                int(monthly_stats.get("CurrentMonthUpload", "0"))
                + int(monthly_stats.get("CurrentMonthDownload", "0"))
            ),
        )

    async def connect_modem(self) -> bool:
        """Connect the modem to the network"""
        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <dataswitch>1</dataswitch>
        </request>"""

        try:
            await self._request("POST", "/api/dialup/mobile-dataswitch", data=xml_data)
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
            await self._request("POST", "/api/dialup/mobile-dataswitch", data=xml_data)
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
            await self._request("POST", "/api/device/control", data=xml_data)
        except:
            pass  # Expected to fail as modem reboots # nosec

        logger.info(f"Modem {self.name} reboot initiated")
        return True

    async def set_network_mode(self, mode: NetworkMode) -> bool:
        """Set network mode"""
        # Get current band settings
        response = await self._request("GET", "/api/net/net-mode")
        data = xml_to_dict(response)

        if "response" not in data:
            return False

        current_data = data["response"]

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <NetworkMode>{mode.value}</NetworkMode>
            <NetworkBand>{current_data.get('NetworkBand', '3FFFFFFF')}</NetworkBand>
            <LTEBand>{current_data.get('LTEBand', '7FFFFFFFFFFFFFFF')}</LTEBand>
        </request>"""

        try:
            await self._request("POST", "/api/net/net-mode", data=xml_data)
            logger.info(f"Network mode set to {mode.name} for modem {self.name}")
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set network mode: {e}")
            return False

    async def set_roaming(self, enabled: bool) -> bool:
        """Enable or disable roaming"""
        # Get current connection settings
        response = await self._request("GET", "/api/dialup/connection")
        data = xml_to_dict(response)

        if "response" not in data:
            return False

        current_data = data["response"]

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
            await self._request("POST", "/api/dialup/connection", data=xml_data)
            logger.info(
                f"Roaming {'enabled' if enabled else 'disabled'} for modem {self.name}"
            )
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set roaming: {e}")
            return False

    async def set_auto_disconnect(self, minutes: int) -> bool:
        """Set the auto-disconnect idle interval (in minutes).

        The modem's MaxIdelTime is expressed in seconds; 0 disables the
        auto-disconnect feature. All other connection fields are preserved
        from the current device setting.
        """
        response = await self._request("GET", "/api/dialup/connection")
        data = xml_to_dict(response)

        if "response" not in data:
            return False

        current_data = data["response"]
        max_idle_seconds = str(int(minutes) * 60)

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <RoamAutoConnectEnable>{current_data.get('RoamAutoConnectEnable', '0')}</RoamAutoConnectEnable>
            <MaxIdelTime>{max_idle_seconds}</MaxIdelTime>
            <ConnectMode>{current_data.get('ConnectMode', '0')}</ConnectMode>
            <MTU>{current_data.get('MTU', '1500')}</MTU>
            <auto_dial_switch>{current_data.get('auto_dial_switch', '1')}</auto_dial_switch>
            <pdp_always_on>{current_data.get('pdp_always_on', '0')}</pdp_always_on>
        </request>"""

        try:
            await self._request("POST", "/api/dialup/connection", data=xml_data)
            logger.info(
                f"Auto disconnect set to {int(minutes)} minutes "
                f"({max_idle_seconds}s) for modem {self.name}"
            )
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set auto disconnect: {e}")
            return False

    async def set_bands(self, lte_band_hex: str, network_band_hex: str) -> bool:
        """Lock LTE and UMTS/GSM band selection via hex bitmasks.

        Both arguments are hex strings (e.g. '7FFFFFFFFFFFFFFF' for all LTE
        bands, '3FFFFFFF' for all 3G/2G bands). The current NetworkMode is
        preserved from the device.
        """
        response = await self._request("GET", "/api/net/net-mode")
        data = xml_to_dict(response)

        if "response" not in data:
            return False

        current_data = data["response"]
        lte_band_hex = str(lte_band_hex).upper()
        network_band_hex = str(network_band_hex).upper()

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <NetworkMode>{current_data.get('NetworkMode', '00')}</NetworkMode>
            <NetworkBand>{network_band_hex}</NetworkBand>
            <LTEBand>{lte_band_hex}</LTEBand>
        </request>"""

        try:
            await self._request("POST", "/api/net/net-mode", data=xml_data)
            logger.info(
                f"Bands set to LTE={lte_band_hex}, 3G/2G={network_band_hex} "
                f"for modem {self.name}"
            )
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set bands: {e}")
            return False

    async def set_network_search(self, mode: str, plmn: str = "", rat: str = "auto") -> bool:
        """Set PLMN network search mode (auto/manual).

        ``mode`` is 'auto' or 'manual'. When manual, ``plmn`` is the numeric
        PLMN code and ``rat`` selects the radio access technology
        ('auto', '2g', '3g', '4g'), mapped to the modem Rat values
        ('' / 0 / 2 / 7).
        """
        rat_map = {"auto": "", "2g": "0", "3g": "2", "4g": "7"}
        rat_value = rat_map.get(str(rat).lower(), "")

        if str(mode).lower() == "manual":
            mode_value = "1"
            plmn_value = str(plmn) if plmn is not None else ""
        else:
            mode_value = "0"
            plmn_value = ""

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request>
            <Mode>{mode_value}</Mode>
            <Plmn>{plmn_value}</Plmn>
            <Rat>{rat_value}</Rat>
        </request>"""

        try:
            await self._request("POST", "/api/net/register", data=xml_data)
            logger.info(
                f"Network search set to {mode}"
                + (f" PLMN={plmn_value} Rat={rat_value}" if mode_value == "1" else "")
                + f" for modem {self.name}"
            )
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set network search: {e}")
            return False

    async def get_plmn_list(self) -> list:
        """Return the list of available PLMNs from the modem.

        Each entry is a dict with keys ``Name``, ``Numeric`` and ``Rat``.
        Returns an empty list on failure or when no networks are reported.
        """
        try:
            response = await self._request("GET", "/api/net/plmn-list")
            data = xml_to_dict(response)
        except HiLinkException as e:
            logger.error(f"Failed to fetch PLMN list: {e}")
            return []

        resp = data.get("response") if isinstance(data, dict) else None
        if not resp or not isinstance(resp, dict):
            return []

        networks = resp.get("Networks")
        if not networks or not isinstance(networks, dict):
            return []

        network = networks.get("Network")
        if network is None:
            return []
        if isinstance(network, dict):
            network = [network]
        elif not isinstance(network, list):
            return []

        result = []
        for net in network:
            if not isinstance(net, dict):
                continue
            result.append({
                "Name": net.get("Name", ""),
                "Numeric": net.get("Numeric", ""),
                "Rat": net.get("Rat", ""),
            })
        return result

    async def get_profiles(self) -> list:
        """List the modem's dialup/connection (APN) profiles.

        Returns a list of dicts: {Index, Name, Apn, Username, AuthName,
        DialNumber, IpType}. Returns [] on failure.
        """
        try:
            response = await self._request("GET", "/api/dialup/profiles")
            data = xml_to_dict(response)
            profiles = data.get("response", {}).get("Profiles", {}).get("Profile", [])
            if isinstance(profiles, dict):
                profiles = [profiles]
            elif not isinstance(profiles, list):
                return []
            result = []
            for p in profiles:
                if not isinstance(p, dict):
                    continue
                result.append({
                    "Index": p.get("Index", ""),
                    "Name": p.get("Name", ""),
                    "Apn": p.get("Apn", ""),
                    "Username": p.get("Username", ""),
                    "AuthName": p.get("AuthName", ""),
                    "DialNumber": p.get("DialNumber", ""),
                    "IpType": p.get("IpType", ""),
                })
            return result
        except HiLinkException as e:
            logger.error(f"Failed to list profiles for modem {self.name}: {e}")
            return []

    async def get_active_profile(self) -> str:
        """Return the Index of the currently active dialup profile, or ''."""
        try:
            response = await self._request("GET", "/api/dialup/profiles")
            data = xml_to_dict(response)
            return str(data.get("response", {}).get("Profiles", {}).get("CurrentProfile", ""))
        except HiLinkException as e:
            logger.error(f"Failed to get active profile for modem {self.name}: {e}")
            return ""

    async def set_active_profile(self, profile_index: str) -> bool:
        """Set the active dialup profile by its Index.

        Reads the current profile list, finds the matching profile, and
        re-POSTs it as the active profile. The Huawei API expects the full
        profile record with the CurrentProfile field set.
        """
        try:
            response = await self._request("GET", "/api/dialup/profiles")
            data = xml_to_dict(response)
            profiles = data.get("response", {}).get("Profiles", {}).get("Profile", [])
            if isinstance(profiles, dict):
                profiles = [profiles]
            elif not isinstance(profiles, list):
                profiles = []

            target = next(
                (p for p in profiles if isinstance(p, dict) and str(p.get("Index")) == str(profile_index)),
                None,
            )
            if target is None:
                logger.error(f"Profile index {profile_index} not found on modem {self.name}")
                return False

            # Re-post the chosen profile; CurrentProfile selects it.
            fields = [
                "Index", "Name", "Apn", "Username", "Password", "AuthName",
                "DialNumber", "IpType",
            ]
            body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<request>"
            body += f"<Profiles><CurrentProfile>{profile_index}</CurrentProfile>"
            body += "<Profile>"
            for f in fields:
                body += f"<{f}>{target.get(f, '')}</{f}>"
            body += "</Profile></Profiles>"
            body += "</request>"

            await self._request("POST", "/api/dialup/profiles", data=body)
            logger.info(f"Active profile set to {profile_index} for modem {self.name}")
            return True
        except HiLinkException as e:
            logger.error(f"Failed to set active profile for modem {self.name}: {e}")
            return False

    # Reverse mapping of modem NetworkMode codes to plugin network_mode values
    NETWORK_MODE_TO_CONFIG = {
        NetworkMode.AUTO.value: "auto",
        NetworkMode.LTE_ONLY.value: "4g_only",
        NetworkMode.WCDMA_ONLY.value: "3g_only",
        NetworkMode.LTE_WCDMA_GSM.value: "4g_preferred",
        NetworkMode.LTE_WCDMA.value: "4g_preferred",
        NetworkMode.LTE_GSM.value: "4g_preferred",
        NetworkMode.WCDMA_GSM.value: "3g_preferred",
    }

    async def get_settings(self) -> Dict[str, Any]:
        """Read the current device settings without modifying anything.

        Returns the settings this plugin manages, keyed by their
        ModemConfig field names, so they can be imported directly.
        """
        settings: Dict[str, Any] = {}

        response = await self._request("GET", "/api/net/net-mode")
        data = xml_to_dict(response)
        if "response" in data and data["response"]:
            mode = str(data["response"].get("NetworkMode", "00"))
            settings["network_mode"] = self.NETWORK_MODE_TO_CONFIG.get(mode, "auto")
            settings["lte_band"] = str(data["response"].get("LTEBand", "")).upper()
            settings["network_band"] = str(data["response"].get("NetworkBand", "")).upper()

        response = await self._request("GET", "/api/dialup/connection")
        data = xml_to_dict(response)
        if "response" in data and data["response"]:
            conn = data["response"]
            settings["roaming_enabled"] = (
                str(conn.get("RoamAutoConnectEnable", "0")) == "1"
            )
            idle_seconds = self._parse_int(conn.get("MaxIdelTime")) or 0
            settings["max_idle_time"] = idle_seconds
            settings["auto_disconnect_min"] = idle_seconds // 60
            # ConnectMode 0 means the modem dials automatically
            settings["auto_connect"] = str(conn.get("ConnectMode", "0")) == "0"

        response = await self._request("GET", "/api/device/information")
        data = xml_to_dict(response)
        if "response" in data and data["response"]:
            settings["device_name"] = data["response"].get("DeviceName", "")

        return settings

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
    modem = HiLinkModem(host="192.168.8.1", username="admin", password="admin")  # nosec

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

# HiLink Plugin API Documentation

## Overview

The HiLink plugin provides a RESTful API for managing and monitoring Huawei HiLink modems. All API endpoints require authentication using OPNsense's built-in authentication system.

## Authentication

### API Key Authentication
```bash
curl -X GET https://your-opnsense/api/hilink/monitor/status \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Session Authentication
```bash
# Login
curl -X POST https://your-opnsense/api/core/auth/login \
  -d "username=admin&password=yourpassword" \
  -c cookies.txt

# Use session
curl -X GET https://your-opnsense/api/hilink/monitor/status \
  -b cookies.txt
```

## Base URL

```
https://your-opnsense/api/hilink
```

## Response Format

All responses are in JSON format:

```json
{
  "status": "success|error",
  "data": {},
  "message": "Optional message",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

## Endpoints

### Service Management

#### Get Service Status
```http
GET /api/hilink/service/status
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "running": true,
    "pid": 12345,
    "uptime": 3600,
    "version": "1.0.0",
    "modems_connected": 1
  }
}
```

#### Start Service
```http
POST /api/hilink/service/start
```

**Response:**
```json
{
  "status": "success",
  "message": "Service started successfully"
}
```

#### Stop Service
```http
POST /api/hilink/service/stop
```

**Response:**
```json
{
  "status": "success",
  "message": "Service stopped successfully"
}
```

#### Restart Service
```http
POST /api/hilink/service/restart
```

**Response:**
```json
{
  "status": "success",
  "message": "Service restarted successfully"
}
```

### Configuration

#### Get Configuration
```http
GET /api/hilink/settings/get
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "general": {
      "enabled": true,
      "update_interval": 30,
      "data_retention": 30
    },
    "modems": [
      {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Primary Modem",
        "enabled": true,
        "ip_address": "192.168.8.1",
        "username": "admin",
        "auto_connect": true,
        "roaming_enabled": false,
        "network_mode": "auto"
      }
    ],
    "alerts": {
      "low_signal_threshold": -90,
      "data_limit_enabled": false,
      "data_limit_mb": 10240
    }
  }
}
```

#### Update Configuration
```http
POST /api/hilink/settings/set
Content-Type: application/json

{
  "general": {
    "update_interval": 60
  },
  "modems": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "roaming_enabled": true
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration updated successfully"
}
```

#### Validate Configuration
```http
POST /api/hilink/settings/validate
Content-Type: application/json

{
  "modems": [
    {
      "ip_address": "192.168.8.1",
      "username": "admin",
      "password": "password123"
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "valid": true,
    "errors": []
  }
}
```

### Monitoring

#### Get Modem Status
```http
GET /api/hilink/monitor/status
```

**Query Parameters:**
- `modem_uuid` (optional): Specific modem UUID

**Response:**
```json
{
  "status": "success",
  "data": {
    "connection_status": "connected",
    "network_type": "4G",
    "network_operator": "Carrier Name",
    "wan_ip": "10.0.0.1",
    "connection_time": 3600,
    "sim_status": "ready",
    "device_name": "E3372h-320",
    "imei": "123456789012345",
    "iccid": "89000000000000000000"
  }
}
```

#### Get Signal Information
```http
GET /api/hilink/monitor/signal
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "rssi": -65,
    "rsrp": -95,
    "rsrq": -10,
    "sinr": 15,
    "signal_bars": 4,
    "signal_quality": "good",
    "cell_id": 12345,
    "band": "B3",
    "frequency": 1800
  }
}
```

#### Get Data Usage
```http
GET /api/hilink/monitor/data
```

**Query Parameters:**
- `period` (optional): `session`, `day`, `month`, `total`

**Response:**
```json
{
  "status": "success",
  "data": {
    "session": {
      "upload": 1048576,
      "download": 10485760,
      "total": 11534336,
      "duration": 3600
    },
    "today": {
      "upload": 5242880,
      "download": 52428800,
      "total": 57671680
    },
    "month": {
      "upload": 1073741824,
      "download": 10737418240,
      "total": 11811160064
    }
  }
}
```

#### Get Historical Metrics
```http
GET /api/hilink/monitor/metrics
```

**Query Parameters:**
- `start` (optional): Start timestamp (ISO 8601)
- `end` (optional): End timestamp (ISO 8601)
- `resolution` (optional): `5min`, `hour`, `day`
- `metrics` (optional): Comma-separated list of metrics

**Response:**
```json
{
  "status": "success",
  "data": {
    "timestamps": [
      "2024-01-01T12:00:00Z",
      "2024-01-01T12:05:00Z"
    ],
    "metrics": {
      "signal_strength": [-65, -67],
      "data_rx": [1048576, 2097152],
      "data_tx": [524288, 1048576],
      "connection_state": [1, 1]
    }
  }
}
```

### Modem Control

#### Connect Modem
```http
POST /api/hilink/modem/connect
```

**Request Body (optional):**
```json
{
  "modem_uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Modem connected successfully",
  "data": {
    "wan_ip": "10.0.0.1",
    "connection_time": "2024-01-01T12:00:00Z"
  }
}
```

#### Disconnect Modem
```http
POST /api/hilink/modem/disconnect
```

**Response:**
```json
{
  "status": "success",
  "message": "Modem disconnected successfully"
}
```

#### Reboot Modem
```http
POST /api/hilink/modem/reboot
```

**Response:**
```json
{
  "status": "success",
  "message": "Modem reboot initiated"
}
```

#### Switch Network Mode
```http
POST /api/hilink/modem/network_mode
Content-Type: application/json

{
  "mode": "4g_preferred"
}
```

**Valid Modes:**
- `auto`: Automatic selection
- `4g_preferred`: 4G preferred, fallback to 3G/2G
- `3g_preferred`: 3G preferred, fallback to 2G
- `4g_only`: 4G only
- `3g_only`: 3G only

**Response:**
```json
{
  "status": "success",
  "message": "Network mode changed successfully"
}
```

#### Enable/Disable Roaming
```http
POST /api/hilink/modem/roaming
Content-Type: application/json

{
  "enabled": true
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Roaming setting updated"
}
```

### Alerts

#### Get Active Alerts
```http
GET /api/hilink/alerts/active
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "alert_001",
      "type": "low_signal",
      "severity": "warning",
      "message": "Signal strength below threshold: -95 dBm",
      "timestamp": "2024-01-01T12:00:00Z",
      "modem_uuid": "550e8400-e29b-41d4-a716-446655440000"
    }
  ]
}
```

#### Acknowledge Alert
```http
POST /api/hilink/alerts/acknowledge
Content-Type: application/json

{
  "alert_id": "alert_001"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Alert acknowledged"
}
```

#### Get Alert History
```http
GET /api/hilink/alerts/history
```

**Query Parameters:**
- `start` (optional): Start timestamp
- `end` (optional): End timestamp
- `type` (optional): Alert type filter
- `limit` (optional): Maximum results (default: 100)

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "id": "alert_001",
      "type": "connection_lost",
      "severity": "error",
      "message": "Connection lost",
      "timestamp": "2024-01-01T11:00:00Z",
      "resolved_at": "2024-01-01T11:05:00Z",
      "duration": 300
    }
  ]
}
```

## WebSocket API

### Real-time Updates

Connect to WebSocket endpoint for real-time updates:

```javascript
const ws = new WebSocket('wss://your-opnsense/api/hilink/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};

// Subscribe to specific events
ws.send(JSON.stringify({
  action: 'subscribe',
  events: ['status', 'signal', 'data']
}));
```

### Event Types

| Event | Description | Data |
|-------|-------------|------|
| `status` | Connection status change | `{connected: boolean, wan_ip: string}` |
| `signal` | Signal strength update | `{rssi: number, quality: string}` |
| `data` | Data usage update | `{upload: number, download: number}` |
| `alert` | New alert | `{type: string, message: string}` |

## Rate Limiting

API requests are rate-limited:
- **Default**: 60 requests per minute
- **Monitoring endpoints**: 120 requests per minute
- **Control endpoints**: 10 requests per minute

Rate limit headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704110400
```

## Examples

### Python Example

```python
import requests
import json

class HiLinkAPI:
    def __init__(self, host, api_key):
        self.host = host
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def get_status(self):
        response = requests.get(
            f'{self.host}/api/hilink/monitor/status',
            headers=self.headers
        )
        return response.json()
    
    def connect_modem(self):
        response = requests.post(
            f'{self.host}/api/hilink/modem/connect',
            headers=self.headers
        )
        return response.json()

# Usage
api = HiLinkAPI('https://192.168.1.1', 'your-api-key')
status = api.get_status()
print(f"Connection: {status['data']['connection_status']}")
```

### JavaScript Example

```javascript
class HiLinkAPI {
  constructor(host, apiKey) {
    this.host = host;
    this.headers = {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    };
  }
  
  async getStatus() {
    const response = await fetch(`${this.host}/api/hilink/monitor/status`, {
      headers: this.headers
    });
    return response.json();
  }
  
  async connectModem() {
    const response = await fetch(`${this.host}/api/hilink/modem/connect`, {
      method: 'POST',
      headers: this.headers
    });
    return response.json();
  }
}

// Usage
const api = new HiLinkAPI('https://192.168.1.1', 'your-api-key');
api.getStatus().then(status => {
  console.log(`Connection: ${status.data.connection_status}`);
});
```

### cURL Examples

```bash
# Get modem status
curl -X GET https://192.168.1.1/api/hilink/monitor/status \
  -H "Authorization: Bearer YOUR_API_KEY"

# Connect modem
curl -X POST https://192.168.1.1/api/hilink/modem/connect \
  -H "Authorization: Bearer YOUR_API_KEY"

# Update configuration
curl -X POST https://192.168.1.1/api/hilink/settings/set \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"general":{"update_interval":60}}'

# Get data usage for current month
curl -X GET "https://192.168.1.1/api/hilink/monitor/data?period=month" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Troubleshooting

### Common Error Responses

#### Authentication Failed
```json
{
  "status": "error",
  "message": "Invalid API key",
  "code": 401
}
```

#### Modem Not Found
```json
{
  "status": "error",
  "message": "Modem with UUID not found",
  "code": 404
}
```

#### Service Unavailable
```json
{
  "status": "error",
  "message": "HiLink service is not running",
  "code": 503
}
```

#### Invalid Configuration
```json
{
  "status": "error",
  "message": "Invalid configuration",
  "errors": [
    "IP address format invalid",
    "Update interval must be between 10 and 300"
  ],
  "code": 400
}
```

## API Versioning

The API uses URL versioning. Current version: v1

Future versions will be available at:
- `/api/hilink/v2/...`
- `/api/hilink/v3/...`

The unversioned endpoints (`/api/hilink/...`) will always point to v1 for backward compatibility.

## Support

For API support and questions:
- GitHub Issues: [https://github.com/yourusername/opnsense-hilink/issues](https://github.com/yourusername/opnsense-hilink/issues)
- API Documentation: [https://docs.example.com/api](https://docs.example.com/api)
- Email: api-support@example.com
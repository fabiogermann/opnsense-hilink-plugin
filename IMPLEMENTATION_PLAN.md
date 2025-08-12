# OPNsense HiLink Plugin Implementation Plan

## Project Overview
Create a production-ready OPNsense plugin for monitoring and managing Huawei HiLink 4G USB modems with support for E3372s/E3372h series devices.

## Development Phases

### Phase 1: Foundation (Week 1-2)
#### 1.1 Project Setup
- [ ] Initialize Git repository structure
- [ ] Create development environment setup script
- [ ] Set up Python virtual environment
- [ ] Configure OPNsense development VM

#### 1.2 Core Library Development
- [ ] Port HiLink API to plugin structure
- [ ] Add async/await support for non-blocking operations
- [ ] Implement connection pooling
- [ ] Add comprehensive error handling
- [ ] Create modem discovery mechanism

#### 1.3 Basic Service Implementation
- [ ] Create daemon service skeleton
- [ ] Implement configuration loading
- [ ] Add service lifecycle management
- [ ] Set up logging infrastructure

### Phase 2: Backend Services (Week 3-4)
#### 2.1 Monitoring Service
- [ ] Implement data collector daemon
- [ ] Create RRD database schema
- [ ] Add metric collection (signal, data, uptime)
- [ ] Implement data retention policies
- [ ] Create alert system

#### 2.2 Configuration Management
- [ ] Design XML configuration schema
- [ ] Implement configuration validation
- [ ] Create configuration migration system
- [ ] Add configuration backup/restore

#### 2.3 API Development
- [ ] Create REST API endpoints
- [ ] Implement authentication
- [ ] Add rate limiting
- [ ] Create API documentation

### Phase 3: Web Interface (Week 5-6)
#### 3.1 MVC Implementation
- [ ] Create Phalcon controllers
- [ ] Implement models and validation
- [ ] Design Volt templates
- [ ] Add form handling

#### 3.2 Dashboard Development
- [ ] Create main dashboard view
- [ ] Implement real-time updates (WebSocket/SSE)
- [ ] Add signal strength gauge
- [ ] Create data usage charts
- [ ] Implement connection status indicator

#### 3.3 Configuration Interface
- [ ] Create settings forms
- [ ] Add modem configuration panel
- [ ] Implement alert configuration
- [ ] Create advanced settings section

### Phase 4: Advanced Features (Week 7-8)
#### 4.1 Auto-Management
- [ ] Implement auto-connect logic
- [ ] Add schedule-based control
- [ ] Create roaming management
- [ ] Add failover detection

#### 4.2 Data Management
- [ ] Implement data usage tracking
- [ ] Create usage alerts
- [ ] Add data limit enforcement
- [ ] Generate usage reports

#### 4.3 Network Optimization
- [ ] Add network mode switching
- [ ] Implement band selection (if supported)
- [ ] Create signal optimization logic
- [ ] Add connection quality monitoring

### Phase 5: Testing & Documentation (Week 9-10)
#### 5.1 Testing
- [ ] Write unit tests (>80% coverage)
- [ ] Create integration tests
- [ ] Perform load testing
- [ ] Test with multiple modem models
- [ ] Security testing

#### 5.2 Documentation
- [ ] Write user guide
- [ ] Create admin documentation
- [ ] Document API endpoints
- [ ] Add troubleshooting guide
- [ ] Create video tutorials

### Phase 6: CI/CD & Packaging (Week 11-12)
#### 6.1 Build System
- [ ] Create comprehensive Makefile
- [ ] Set up automated builds
- [ ] Implement versioning system
- [ ] Create release scripts

#### 6.2 GitHub Actions
- [ ] Set up test pipeline
- [ ] Create build pipeline
- [ ] Add code quality checks
- [ ] Implement automated releases

#### 6.3 Package Creation
- [ ] Create OPNsense package
- [ ] Add installation scripts
- [ ] Create upgrade mechanism
- [ ] Test package installation

## Technical Specifications

### Backend Components

#### 1. HiLink API Wrapper (`hilink_api.py`)
```python
class HiLinkModem:
    """Enhanced HiLink API wrapper with async support"""
    
    async def connect(self) -> bool
    async def disconnect(self) -> bool
    async def get_status(self) -> ModemStatus
    async def get_signal_info(self) -> SignalInfo
    async def get_data_usage(self) -> DataUsage
    async def set_network_mode(self, mode: NetworkMode) -> bool
    async def enable_roaming(self, enabled: bool) -> bool
```

#### 2. Service Daemon (`hilink_service.py`)
```python
class HiLinkService:
    """Main service daemon"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.monitor = MonitorService()
        self.collector = DataCollector()
        
    async def start(self):
        """Start all services"""
        
    async def stop(self):
        """Graceful shutdown"""
        
    async def reload_config(self):
        """Hot reload configuration"""
```

#### 3. Data Collector (`hilink_collector.py`)
```python
class DataCollector:
    """Collects and stores metrics"""
    
    async def collect_metrics(self):
        """Periodic metric collection"""
        
    def store_to_rrd(self, metrics: Dict):
        """Store metrics in RRD"""
        
    def cleanup_old_data(self):
        """Remove data older than retention period"""
```

### Frontend Components

#### 1. Dashboard Controller
```php
namespace OPNsense\HiLink\Api;

class MonitorController extends ApiControllerBase
{
    public function statusAction()
    {
        // Return current modem status
    }
    
    public function metricsAction()
    {
        // Return historical metrics
    }
    
    public function signalAction()
    {
        // Return signal information
    }
}
```

#### 2. Dashboard View
```javascript
// hilink.js - Dashboard functionality
class HiLinkDashboard {
    constructor() {
        this.updateInterval = 5000;
        this.charts = {};
    }
    
    initializeCharts() {
        // Setup Chart.js graphs
    }
    
    updateStatus() {
        // Fetch and update status
    }
    
    updateMetrics() {
        // Update real-time metrics
    }
}
```

### Configuration Schema

#### Modem Configuration
```xml
<modem>
    <uuid>{{ uuid() }}</uuid>
    <enabled>1</enabled>
    <name>Primary Modem</name>
    <ip_address>192.168.8.1</ip_address>
    <username>admin</username>
    <password>{{ encrypted_password }}</password>
    <settings>
        <auto_connect>1</auto_connect>
        <roaming_enabled>0</roaming_enabled>
        <network_mode>auto</network_mode>
        <max_idle_time>0</max_idle_time>
        <reconnect_interval>60</reconnect_interval>
        <max_reconnect_attempts>3</max_reconnect_attempts>
    </settings>
    <monitoring>
        <collect_interval>30</collect_interval>
        <signal_threshold>-90</signal_threshold>
        <data_limit_enabled>0</data_limit_enabled>
        <data_limit_mb>10240</data_limit_mb>
        <alert_email></alert_email>
    </monitoring>
</modem>
```

### Database Schema

#### RRD Database Structure
```python
RRD_SCHEMA = {
    'signal_strength': {
        'type': 'GAUGE',
        'heartbeat': 120,
        'min': -120,
        'max': -40
    },
    'data_rx': {
        'type': 'COUNTER',
        'heartbeat': 120,
        'min': 0,
        'max': 'U'
    },
    'data_tx': {
        'type': 'COUNTER',
        'heartbeat': 120,
        'min': 0,
        'max': 'U'
    },
    'connection_state': {
        'type': 'GAUGE',
        'heartbeat': 120,
        'min': 0,
        'max': 1
    }
}
```

### API Endpoints

#### REST API Structure
```
GET  /api/hilink/service/status       - Service status
GET  /api/hilink/service/start        - Start service
GET  /api/hilink/service/stop         - Stop service
GET  /api/hilink/service/restart      - Restart service

GET  /api/hilink/settings/get         - Get configuration
POST /api/hilink/settings/set         - Update configuration
GET  /api/hilink/settings/validate    - Validate configuration

GET  /api/hilink/monitor/status       - Current modem status
GET  /api/hilink/monitor/signal       - Signal information
GET  /api/hilink/monitor/data         - Data usage statistics
GET  /api/hilink/monitor/metrics      - Historical metrics

POST /api/hilink/modem/connect        - Connect modem
POST /api/hilink/modem/disconnect     - Disconnect modem
POST /api/hilink/modem/reboot        - Reboot modem
```

## Testing Strategy

### Unit Tests
```python
# test_hilink_api.py
class TestHiLinkAPI:
    def test_connection()
    def test_authentication()
    def test_status_retrieval()
    def test_error_handling()
    def test_retry_logic()

# test_config_manager.py
class TestConfigManager:
    def test_load_config()
    def test_validate_config()
    def test_save_config()
    def test_migration()

# test_data_collector.py
class TestDataCollector:
    def test_metric_collection()
    def test_rrd_storage()
    def test_data_cleanup()
```

### Integration Tests
```python
# test_service.py
class TestService:
    def test_service_lifecycle()
    def test_config_reload()
    def test_modem_discovery()
    def test_failover()

# test_api.py
class TestAPI:
    def test_api_endpoints()
    def test_authentication()
    def test_rate_limiting()
```

## Build Configuration

### Makefile
```makefile
# Main targets
.PHONY: all build test package install clean

VERSION := $(shell git describe --tags --always)
PLUGIN_NAME := os-hilink
BUILD_DIR := build
DIST_DIR := dist

all: clean build test package

build:
	@echo "Building HiLink plugin..."
	python3 -m py_compile src/opnsense/scripts/hilink/*.py
	npm run build --prefix src/opnsense/mvc/www/js/hilink
	
test:
	@echo "Running tests..."
	python3 -m pytest tests/ --cov=src/opnsense/scripts/hilink
	
package:
	@echo "Creating package..."
	mkdir -p $(DIST_DIR)
	tar -czf $(DIST_DIR)/$(PLUGIN_NAME)-$(VERSION).tar.gz \
		--exclude='*.pyc' \
		--exclude='__pycache__' \
		src/ pkg/
	
install:
	@echo "Installing to OPNsense..."
	sudo cp -r src/opnsense/* /usr/local/opnsense/
	sudo service configd restart
	
clean:
	@echo "Cleaning..."
	rm -rf $(BUILD_DIR) $(DIST_DIR)
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
```

## GitHub Actions Workflows

### Test Workflow (`.github/workflows/test.yml`)
```yaml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Run tests
      run: |
        pytest tests/ --cov=src/opnsense/scripts/hilink --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Build Workflow (`.github/workflows/build.yml`)
```yaml
name: Build and Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        sudo apt-get update
        sudo apt-get install -y npm
    
    - name: Build package
      run: make package
    
    - name: Create Release
      uses: softprops/action-gh-release@v1
      with:
        files: dist/*.tar.gz
        generate_release_notes: true
```

## Deployment Instructions

### Installation Steps
1. Download the plugin package
2. Upload to OPNsense via System > Firmware > Plugins
3. Install the plugin
4. Navigate to Services > HiLink
5. Configure modem settings
6. Start the service
7. Verify operation in dashboard

### Configuration Guide
1. **Basic Setup**
   - Enter modem IP address
   - Set authentication credentials
   - Enable service

2. **Advanced Configuration**
   - Configure auto-connect settings
   - Set roaming preferences
   - Configure data limits
   - Set up alerts

3. **Monitoring**
   - View real-time status
   - Check signal strength
   - Monitor data usage
   - Review connection history

## Performance Targets

- **Service startup**: < 5 seconds
- **API response time**: < 100ms
- **Dashboard update**: Every 5 seconds
- **Memory usage**: < 50MB
- **CPU usage**: < 5% idle, < 20% active
- **Data retention**: 30 days default
- **Concurrent modems**: Up to 4 (future)

## Security Measures

1. **Authentication**
   - OPNsense user integration
   - API token support
   - Session management

2. **Data Protection**
   - Encrypted password storage
   - Secure API communication
   - Input sanitization

3. **Network Security**
   - Modem network isolation
   - Firewall rule integration
   - Rate limiting

## Support Matrix

### Supported OPNsense Versions
- OPNsense 23.7+
- OPNsense 24.1+ (recommended)

### Supported Modem Models
- Huawei E3372s-153
- Huawei E3372h-320
- Huawei E3372h-153
- Huawei E8372h-320 (future)

### Browser Support
- Chrome/Chromium 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Success Criteria

1. **Functionality**
   - All core features working
   - < 1% failure rate
   - 99.9% service uptime

2. **Performance**
   - Meets all performance targets
   - Smooth UI experience
   - Efficient resource usage

3. **Quality**
   - > 80% test coverage
   - No critical bugs
   - Clean code (pylint score > 8.0)

4. **Documentation**
   - Complete user guide
   - API documentation
   - Video tutorials

5. **Deployment**
   - One-click installation
   - Automatic updates
   - Easy configuration
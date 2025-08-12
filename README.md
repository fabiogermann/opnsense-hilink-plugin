# OPNsense HiLink Modem Plugin

A comprehensive OPNsense plugin for monitoring and managing Huawei HiLink-based 4G/LTE USB modems.

## Features

### Core Functionality
- ✅ Real-time modem monitoring (signal strength, connection status, data usage)
- ✅ Auto-connect/disconnect management
- ✅ Roaming configuration
- ✅ Network mode selection (4G/3G/2G)
- ✅ Data usage tracking and alerts
- ✅ Historical metrics with configurable retention
- ✅ Web-based dashboard with real-time updates

### Monitoring Capabilities
- **Signal Metrics**: RSSI, RSRP, RSRQ, SINR
- **Connection Info**: Status, uptime, WAN IP, network operator
- **Data Statistics**: Upload/download bytes, session/total usage
- **Network Details**: Type (2G/3G/4G), band, cell ID

### Advanced Features
- Schedule-based connection control
- Data limit enforcement
- Email alerts for events
- Automatic failover (future)
- Multi-modem support (future)

## Supported Devices

### Tested Models
- Huawei E3372s-153
- Huawei E3372h-320
- Huawei E3372h-153

### Planned Support
- Huawei E8372h series
- Huawei E3372s series (all variants)

## Requirements

- OPNsense 23.7 or later (24.1+ recommended)
- Python 3.9+
- Huawei HiLink-compatible USB modem
- Web browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)

## Installation

### From Package

1. Download the latest release from [GitHub Releases](https://github.com/yourusername/opnsense-hilink/releases)
2. Navigate to **System → Firmware → Plugins** in OPNsense
3. Upload the package file
4. Install the plugin
5. Navigate to **Services → HiLink** to configure

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/opnsense-hilink.git
cd opnsense-hilink/opn

# Build the package
make build

# Install locally (requires root)
sudo make install

# Restart services
sudo service configd restart
```

## Configuration

### Basic Setup

1. **Navigate to Services → HiLink**
2. **Add Modem**:
   - Name: Descriptive name for your modem
   - IP Address: Usually `192.168.8.1` (default for most Huawei modems)
   - Username: `admin` (default)
   - Password: Your modem password

3. **Configure Settings**:
   - Auto-connect: Enable for automatic connection management
   - Roaming: Enable if you want to allow roaming
   - Network Mode: Select preferred network type
   - Data Retention: Set how long to keep historical data (default: 30 days)

4. **Save and Apply**

### Advanced Configuration

#### Auto-Connect Settings
```
Auto-connect: Enabled
Reconnect Interval: 60 seconds
Max Reconnect Attempts: 3
```

#### Data Limits
```
Data Limit Enabled: Yes
Monthly Limit: 10240 MB
Alert Threshold: 90%
Action on Limit: Disconnect/Alert
```

#### Monitoring
```
Update Interval: 30 seconds
Signal Threshold: -90 dBm
Alert on Low Signal: Yes
```

## Usage

### Dashboard

The dashboard provides real-time information about your modem:

- **Connection Status**: Visual indicator of connection state
- **Signal Strength**: Gauge showing current signal quality
- **Data Usage**: Current session and total usage
- **Network Info**: Operator, network type, IP address

### Manual Controls

- **Connect/Disconnect**: Manual connection control
- **Reboot Modem**: Restart the modem hardware
- **Refresh**: Force update of all metrics

### API Access

The plugin provides a REST API for integration:

```bash
# Get modem status
curl -X GET https://your-opnsense/api/hilink/monitor/status \
  -H "Authorization: Bearer YOUR_API_KEY"

# Connect modem
curl -X POST https://your-opnsense/api/hilink/modem/connect \
  -H "Authorization: Bearer YOUR_API_KEY"

# Get data usage
curl -X GET https://your-opnsense/api/hilink/monitor/data \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## Development

### Project Structure

```
opn/
├── src/
│   ├── opnsense/
│   │   ├── mvc/          # Web interface (PHP/Phalcon)
│   │   ├── scripts/      # Backend services (Python)
│   │   └── service/      # Service configuration
├── tests/                # Unit and integration tests
├── docs/                 # Documentation
├── pkg/                  # Package metadata
└── Makefile             # Build system
```

### Building from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
make test

# Build package
make package

# Clean build artifacts
make clean
```

### Running Tests

```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests
python -m pytest tests/integration/

# All tests with coverage
python -m pytest tests/ --cov=src/opnsense/scripts/hilink
```

### Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

#### Code Style

- Python: Follow PEP 8, use Black formatter
- PHP: Follow PSR-12
- JavaScript: Use ESLint with provided configuration

## Troubleshooting

### Common Issues

#### Modem Not Detected
- Verify modem IP address (default: 192.168.8.1)
- Check USB connection
- Ensure modem is in HiLink mode (not serial mode)

#### Authentication Failed
- Verify username and password
- Check if modem requires authentication
- Try resetting modem to factory defaults

#### No Data Collection
- Check service status: `service hilink status`
- Review logs: `/var/log/hilink/hilink.log`
- Verify RRD permissions

### Debug Mode

Enable debug logging:
1. Navigate to **Services → HiLink → Advanced**
2. Enable **Debug Logging**
3. Check logs at `/var/log/hilink/debug.log`

### Log Files

- Service logs: `/var/log/hilink/service.log`
- API logs: `/var/log/hilink/api.log`
- Error logs: `/var/log/hilink/error.log`

## Performance

### Resource Usage
- Memory: < 50MB typical, < 100MB peak
- CPU: < 5% idle, < 20% during updates
- Disk: ~10MB for 30 days of data per modem

### Optimization Tips
- Increase update interval for lower resource usage
- Reduce data retention period if disk space is limited
- Disable unused features (e.g., email alerts)

## Security

### Best Practices
- Use strong passwords for modem authentication
- Enable OPNsense firewall rules for modem network
- Regularly update the plugin
- Review access logs periodically

### Network Isolation
The plugin supports network isolation for modem interfaces:
1. Create dedicated interface for modem
2. Apply firewall rules to restrict access
3. Enable NAT if required

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Based on the [HiLink API](https://github.com/chanakalin/hilinkapi) Python library
- OPNsense development team for the plugin framework
- Community contributors and testers

## Support

### Documentation
- [User Guide](docs/USER_GUIDE.md)
- [API Documentation](docs/API.md)
- [Developer Guide](docs/DEVELOPER.md)

### Community
- [GitHub Issues](https://github.com/yourusername/opnsense-hilink/issues)
- [OPNsense Forum](https://forum.opnsense.org)

### Commercial Support
For commercial support and custom development, contact: support@example.com

## Roadmap

### Version 1.0 (Current)
- ✅ Single modem support
- ✅ Basic monitoring
- ✅ Auto-connect/disconnect
- ✅ Web dashboard

### Version 1.1 (Planned)
- [ ] Multi-modem support
- [ ] Advanced failover
- [ ] SMS management
- [ ] Band locking

### Version 2.0 (Future)
- [ ] 5G modem support
- [ ] VPN integration
- [ ] Grafana dashboard
- [ ] REST API v2

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes.

## Authors

- **Your Name** - *Initial work* - [YourGitHub](https://github.com/yourusername)

## Contributors

See the list of [contributors](https://github.com/yourusername/opnsense-hilink/contributors) who participated in this project.
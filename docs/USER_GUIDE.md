# HiLink Plugin User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Initial Setup](#initial-setup)
4. [Dashboard Overview](#dashboard-overview)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Managing Connections](#managing-connections)
8. [Alerts and Notifications](#alerts-and-notifications)
9. [Troubleshooting](#troubleshooting)
10. [FAQ](#faq)

## Introduction

The HiLink plugin for OPNsense provides comprehensive management and monitoring capabilities for Huawei HiLink-based 4G/LTE USB modems. This guide will help you install, configure, and use the plugin effectively.

### Key Features

- **Real-time Monitoring**: Track signal strength, data usage, and connection status
- **Automatic Management**: Auto-connect, disconnect, and roaming control
- **Data Limits**: Set and enforce data usage limits
- **Historical Data**: View trends and patterns over time
- **Alerts**: Get notified about connection issues and data limits

### Supported Devices

- Huawei E3372s series (including E3372s-153)
- Huawei E3372h series (E3372h-320, E3372h-153)
- Huawei E8372h series (planned)

## Installation

### Prerequisites

Before installing the HiLink plugin, ensure:

1. **OPNsense Version**: 23.7 or later (24.1+ recommended)
2. **Modem Setup**: Your Huawei modem is connected via USB
3. **Network Access**: Modem is accessible (default: 192.168.8.1)
4. **Admin Access**: You have administrator privileges in OPNsense

### Installation Steps

#### Method 1: Via Web Interface (Recommended)

1. **Download the Plugin**
   - Visit the [releases page](https://github.com/yourusername/opnsense-hilink/releases)
   - Download the latest `.txz` package

2. **Upload to OPNsense**
   - Navigate to **System → Firmware → Plugins**
   - Click **Upload** button
   - Select the downloaded package
   - Click **Upload**

3. **Install the Plugin**
   - Find "os-hilink" in the plugin list
   - Click the **+** button to install
   - Wait for installation to complete

4. **Verify Installation**
   - Navigate to **Services → HiLink**
   - You should see the plugin interface

#### Method 2: Via Command Line

```bash
# SSH into your OPNsense box
ssh root@your-opnsense

# Download the package
fetch https://github.com/yourusername/opnsense-hilink/releases/download/v1.0.0/os-hilink-1.0.0.txz

# Install the package
pkg add os-hilink-1.0.0.txz

# Restart configd
service configd restart
```

## Initial Setup

### Step 1: Access the Plugin

1. Log into OPNsense web interface
2. Navigate to **Services → HiLink**
3. You'll see the main dashboard (initially empty)

### Step 2: Add Your Modem

1. Click **Settings** tab
2. Click **Add Modem** button
3. Fill in the modem details:

   | Field | Description | Example |
   |-------|-------------|---------|
   | **Name** | Friendly name for your modem | "Primary 4G" |
   | **IP Address** | Modem's IP address | 192.168.8.1 |
   | **Username** | Admin username | admin |
   | **Password** | Admin password | (your password) |
   | **Enabled** | Enable this modem | ✓ |

4. Click **Save**

### Step 3: Configure Basic Settings

1. In the **General Settings** section:
   - **Update Interval**: How often to check modem status (default: 30 seconds)
   - **Data Retention**: How long to keep historical data (default: 30 days)
   - **Enable Service**: Check to start monitoring

2. Click **Apply** to save changes

### Step 4: Start the Service

1. Go to **Services → HiLink → Service Control**
2. Click **Start Service**
3. Verify status shows "Running"

## Dashboard Overview

The dashboard provides real-time information about your modem:

### Connection Status Panel

![Connection Status](images/connection-status.png)

- **Status Indicator**: Green (connected), Red (disconnected), Yellow (connecting)
- **Network Type**: Current network (2G/3G/4G)
- **Operator**: Network operator name
- **WAN IP**: Current IP address from carrier
- **Uptime**: Connection duration

### Signal Strength Gauge

![Signal Gauge](images/signal-gauge.png)

- **RSSI**: Received Signal Strength Indicator (-120 to -40 dBm)
- **Quality**: Excellent/Good/Fair/Poor
- **Bars**: Visual representation (1-5 bars)

**Signal Quality Guide:**
- **Excellent**: -65 dBm or better
- **Good**: -75 to -65 dBm
- **Fair**: -85 to -75 dBm
- **Poor**: -95 to -85 dBm
- **No Signal**: Worse than -95 dBm

### Data Usage Charts

![Data Usage](images/data-usage.png)

- **Current Session**: Data used since last connection
- **Today**: Total data used today
- **This Month**: Monthly data usage
- **Graph**: Historical usage over time

### Quick Actions

- **Connect/Disconnect**: Manual connection control
- **Reboot Modem**: Restart the modem
- **Refresh**: Force update all metrics

## Configuration

### Connection Settings

Navigate to **Settings → Connection**:

#### Auto-Connect
- **Enable**: Automatically connect when disconnected
- **Retry Interval**: Time between connection attempts (seconds)
- **Max Retries**: Maximum connection attempts before giving up

#### Roaming
- **Allow Roaming**: Enable data roaming
- **Roaming Networks**: Whitelist specific networks (optional)

#### Network Mode
Select preferred network type:
- **Automatic**: Let modem choose best network
- **4G Preferred**: Prefer 4G, fallback to 3G/2G
- **3G Preferred**: Prefer 3G, fallback to 2G
- **4G Only**: Force 4G only (no fallback)
- **3G Only**: Force 3G only (no fallback)

### Data Management

Navigate to **Settings → Data Management**:

#### Data Limits
- **Enable Limits**: Activate data limit enforcement
- **Monthly Limit (MB)**: Maximum data per month
- **Daily Limit (MB)**: Maximum data per day (optional)
- **Action on Limit**: 
  - **Alert Only**: Send notification
  - **Disconnect**: Disconnect when limit reached
  - **Throttle**: Reduce speed (if supported)

#### Reset Schedule
- **Monthly Reset Day**: Day of month to reset counter (1-31)
- **Time Zone**: Time zone for reset calculation

### Advanced Settings

Navigate to **Settings → Advanced**:

#### Monitoring
- **Signal Check Interval**: How often to check signal (seconds)
- **Statistics Collection**: Enable detailed statistics
- **Debug Logging**: Enable verbose logging

#### Performance
- **Connection Timeout**: Maximum time for connection attempts
- **API Timeout**: Timeout for modem API calls
- **Max Concurrent Requests**: Limit parallel API calls

#### Network
- **DNS Servers**: Custom DNS servers (optional)
- **MTU Size**: Maximum transmission unit (default: 1500)
- **IPv6**: Enable IPv6 support (if available)

## Monitoring

### Real-Time Monitoring

The dashboard updates automatically based on your configured interval. Key metrics include:

#### Signal Metrics
- **RSSI**: Signal strength in dBm
- **RSRP**: Reference Signal Received Power (LTE)
- **RSRQ**: Reference Signal Received Quality (LTE)
- **SINR**: Signal to Interference plus Noise Ratio (LTE)
- **CQI**: Channel Quality Indicator

#### Network Information
- **Cell ID**: Current cell tower ID
- **Band**: Frequency band (e.g., B3, B7, B20)
- **EARFCN**: Frequency channel number
- **PCI**: Physical Cell ID

### Historical Data

Navigate to **Monitoring → History**:

#### Available Graphs
1. **Signal Strength**: RSSI over time
2. **Data Usage**: Upload/Download trends
3. **Connection Status**: Uptime/downtime periods
4. **Network Type**: 2G/3G/4G transitions

#### Time Ranges
- Last Hour
- Last 24 Hours
- Last 7 Days
- Last 30 Days
- Custom Range

#### Export Options
- **CSV**: Export raw data
- **PDF**: Generate report
- **Image**: Save graphs as PNG

### Statistics

Navigate to **Monitoring → Statistics**:

View aggregated statistics:
- **Total Data Used**: Lifetime data usage
- **Average Signal**: Mean signal strength
- **Uptime Percentage**: Connection reliability
- **Peak Usage**: Highest data rate achieved
- **Session Count**: Number of connections

## Managing Connections

### Manual Control

#### Connect
1. Click **Connect** button on dashboard
2. Wait for connection (typically 5-30 seconds)
3. Verify status shows "Connected"

#### Disconnect
1. Click **Disconnect** button
2. Confirm disconnection if prompted
3. Status changes to "Disconnected"

#### Reboot Modem
1. Click **Reboot** button
2. Confirm reboot action
3. Wait 60-90 seconds for modem to restart
4. Connection will automatically restore if auto-connect is enabled

### Scheduled Actions

Navigate to **Settings → Scheduling**:

#### Connection Schedule
Create rules for automatic connection/disconnection:

```
Example: Business Hours Only
- Monday-Friday: Connect at 08:00, Disconnect at 18:00
- Saturday-Sunday: Stay disconnected
```

#### Maintenance Windows
Schedule regular modem reboots:

```
Example: Weekly Reboot
- Every Sunday at 03:00 AM
```

### Failover Configuration

Navigate to **Settings → Failover**:

#### Primary Connection Check
- **Check Method**: Ping/HTTP/DNS
- **Check Target**: 8.8.8.8 or custom
- **Check Interval**: 60 seconds
- **Failure Threshold**: 3 consecutive failures

#### Failover Actions
- **Switch to Backup**: Use alternative connection
- **Reboot Modem**: Try recovering connection
- **Alert Admin**: Send notification

## Alerts and Notifications

### Alert Types

#### Connection Alerts
- Connection lost
- Connection restored
- Failed to connect
- Roaming detected

#### Signal Alerts
- Low signal strength
- No signal
- Network type changed

#### Data Alerts
- Data limit reached (80%, 90%, 100%)
- Unusual data usage
- Daily limit exceeded

### Notification Methods

#### Email Notifications
1. Navigate to **Settings → Notifications**
2. Enable **Email Alerts**
3. Configure:
   - **SMTP Server**: Your mail server
   - **From Address**: sender@example.com
   - **To Address**: admin@example.com
   - **Alert Types**: Select which alerts to receive

#### Syslog Integration
1. Enable **Syslog Notifications**
2. Configure:
   - **Syslog Server**: IP address
   - **Facility**: LOCAL0-LOCAL7
   - **Severity Mapping**: Map alert types to syslog levels

#### Dashboard Alerts
- Pop-up notifications in web interface
- Alert badge on menu item
- Alert history in dashboard

### Alert Configuration

#### Thresholds
Set custom thresholds for alerts:

| Alert Type | Default | Range |
|------------|---------|-------|
| Low Signal | -90 dBm | -120 to -50 |
| Data Warning | 80% | 50-95% |
| Connection Timeout | 60s | 30-300s |

#### Alert Suppression
Prevent alert flooding:
- **Minimum Interval**: 5 minutes between same alert
- **Daily Maximum**: Max 10 alerts per type per day
- **Quiet Hours**: No alerts during specified hours

## Troubleshooting

### Common Issues

#### Modem Not Detected

**Symptoms:**
- Status shows "No modem found"
- Cannot connect to modem IP

**Solutions:**
1. **Check USB Connection**
   ```bash
   # Check if modem is detected
   usbconfig
   dmesg | grep -i huawei
   ```

2. **Verify IP Address**
   - Default is usually 192.168.8.1
   - Try accessing via browser: http://192.168.8.1

3. **Check Firewall Rules**
   - Ensure traffic to modem IP is allowed
   - Add rule if necessary in **Firewall → Rules**

#### Authentication Failed

**Symptoms:**
- "Invalid credentials" error
- Cannot access modem settings

**Solutions:**
1. Reset modem to factory defaults
2. Default credentials are usually:
   - Username: admin
   - Password: admin or printed on device

3. Try without password (some models)

#### No Internet Connection

**Symptoms:**
- Connected but no internet
- Cannot browse websites

**Solutions:**
1. **Check APN Settings**
   - Verify with your carrier
   - Common APNs:
     - Verizon: vzwinternet
     - AT&T: broadband
     - T-Mobile: fast.t-mobile.com

2. **Check Data Balance**
   - Ensure you have active data plan
   - Check if data limit reached

3. **DNS Issues**
   - Try custom DNS: 8.8.8.8, 1.1.1.1
   - Check **System → Settings → General**

#### Poor Signal Quality

**Symptoms:**
- Frequent disconnections
- Slow speeds
- Signal below -95 dBm

**Solutions:**
1. **Antenna/Position**
   - Move modem near window
   - Use external antenna if supported
   - Avoid metal obstructions

2. **Band Selection**
   - Try manual band selection
   - Some bands have better coverage

3. **Network Mode**
   - Try forcing 3G if 4G is unstable
   - Disable 5G if causing issues

### Debug Mode

Enable debug logging for detailed troubleshooting:

1. Navigate to **Settings → Advanced**
2. Enable **Debug Logging**
3. Reproduce the issue
4. Check logs at:
   - **System → Log Files → HiLink**
   - SSH: `/var/log/hilink/debug.log`

### Log Files

| Log File | Location | Content |
|----------|----------|---------|
| Service Log | `/var/log/hilink/service.log` | Service start/stop/errors |
| API Log | `/var/log/hilink/api.log` | API calls and responses |
| Connection Log | `/var/log/hilink/connection.log` | Connection events |
| Debug Log | `/var/log/hilink/debug.log` | Detailed debug information |

### Getting Help

If you need assistance:

1. **Check Documentation**
   - This user guide
   - [API Documentation](API.md)
   - [FAQ](#faq)

2. **Community Support**
   - [GitHub Issues](https://github.com/yourusername/opnsense-hilink/issues)
   - [OPNsense Forum](https://forum.opnsense.org)

3. **Provide Information**
   When reporting issues, include:
   - OPNsense version
   - Plugin version
   - Modem model
   - Error messages
   - Relevant log entries

## FAQ

### General Questions

**Q: Which Huawei modems are supported?**
A: Currently E3372s and E3372h series. E8372h support is planned.

**Q: Can I use multiple modems?**
A: Single modem is supported in v1.0. Multi-modem support is planned for v1.1.

**Q: Does it work with pfSense?**
A: Currently OPNsense only. pfSense support may be added in future.

**Q: Is 5G supported?**
A: Not yet. 5G support is planned for version 2.0.

### Configuration Questions

**Q: What's the default modem IP?**
A: Usually 192.168.8.1, but can vary. Check your modem's label.

**Q: How do I find my APN settings?**
A: Contact your carrier or check their website. The modem often auto-configures this.

**Q: Can I change the modem's IP address?**
A: Yes, but update the plugin configuration accordingly.

**Q: Should I enable roaming?**
A: Only if you understand the potential costs. Check with your carrier.

### Performance Questions

**Q: How much bandwidth does monitoring use?**
A: Minimal - typically less than 1MB per day for monitoring.

**Q: Will this slow down my connection?**
A: No, monitoring happens independently of data traffic.

**Q: How often should metrics update?**
A: 30-60 seconds is recommended. More frequent updates use more resources.

**Q: How much disk space for historical data?**
A: Approximately 10MB per month per modem.

### Troubleshooting Questions

**Q: Why does my modem keep disconnecting?**
A: Check signal strength, data limits, and carrier issues. Enable debug logging.

**Q: Can I use this with USB tethering?**
A: No, this is specifically for HiLink mode. USB tethering uses different protocols.

**Q: Why is my speed slow?**
A: Check signal quality, network congestion, and carrier throttling.

**Q: How do I reset everything?**
A: Uninstall and reinstall the plugin, or delete `/usr/local/etc/hilink/` directory.

### Security Questions

**Q: Is my modem password stored securely?**
A: Yes, passwords are encrypted using OPNsense's secure storage.

**Q: Can I restrict access to the plugin?**
A: Yes, use OPNsense's user management to control access.

**Q: Is the connection between OPNsense and modem secure?**
A: It uses the modem's built-in authentication. Consider network isolation.

**Q: Should I change default modem credentials?**
A: Yes, always change default passwords for security.

## Appendix

### Glossary

| Term | Description |
|------|-------------|
| **APN** | Access Point Name - gateway between mobile network and internet |
| **RSSI** | Received Signal Strength Indicator |
| **RSRP** | Reference Signal Received Power (LTE) |
| **RSRQ** | Reference Signal Received Quality (LTE) |
| **SINR** | Signal to Interference plus Noise Ratio |
| **EARFCN** | E-UTRA Absolute Radio Frequency Channel Number |
| **PCI** | Physical Cell Identity |
| **CQI** | Channel Quality Indicator |
| **HiLink** | Huawei's web-based modem management interface |

### Signal Strength Reference

| Signal (dBm) | Quality | Typical Speed |
|--------------|---------|---------------|
| -50 to -65 | Excellent | Maximum speeds |
| -65 to -75 | Good | Near maximum |
| -75 to -85 | Fair | Reduced speeds |
| -85 to -95 | Poor | Basic connectivity |
| -95 to -120 | Very Poor | Unreliable |

### Network Bands

| Band | Frequency | Coverage | Speed |
|------|-----------|----------|-------|
| B3 | 1800 MHz | Urban | High |
| B7 | 2600 MHz | Urban | Very High |
| B20 | 800 MHz | Rural | Medium |
| B28 | 700 MHz | Rural | Medium |

### Useful Commands

```bash
# Check modem detection
usbconfig | grep -i huawei

# View service status
service hilink status

# Restart service
service hilink restart

# View logs
tail -f /var/log/hilink/service.log

# Check modem connectivity
ping 192.168.8.1

# Manual API test
curl http://192.168.8.1/api/device/information
```

---

*Last updated: January 2024*
*Version: 1.0.0*
{#
 # HiLink Dashboard View
 # Main dashboard for modem monitoring and management
 #}

<script>
    $( document ).ready(function() {
        var refreshTimer = null;

        function esc(value) {
            // Escape modem/network-sourced strings before HTML substitution
            return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
                return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c];
            });
        }

        function formatBytes(bytes) {
            bytes = parseInt(bytes, 10);
            if (isNaN(bytes) || bytes < 0) {
                return '-';
            }
            var units = ['B', 'KB', 'MB', 'GB', 'TB'];
            var i = 0;
            while (bytes >= 1024 && i < units.length - 1) {
                bytes /= 1024;
                i++;
            }
            return bytes.toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
        }

        function updateServiceStatus() {
            ajaxGet('/api/hilink/service/status', {}, function(data, status) {
                if (status !== 'success') {
                    return;
                }
                var running = data['running'] === true;
                $('#serviceStatus')
                    .text(running ? '{{ lang._('Running') }}' : '{{ lang._('Stopped') }}')
                    .removeClass('label-success label-danger label-default')
                    .addClass(running ? 'label-success' : 'label-danger');
                $('#serviceEnabled')
                    .text(data['enabled'] ? '{{ lang._('Yes') }}' : '{{ lang._('No') }}')
                    .removeClass('label-success label-warning label-default')
                    .addClass(data['enabled'] ? 'label-success' : 'label-warning');
                $('#btnServiceStart').toggle(!running);
                $('#btnServiceStop').toggle(running);
            });
        }

        function renderModemCard(modem, data) {
            var tpl = $('#modemCardTemplate').html();
            var signal = (data && data.signal) ? data.signal : {};
            var usage = (data && data.usage) ? data.usage : {};
            var connected = !!(data && data.connected);
            var bars = parseInt(signal.signal_bars, 10) || 0;
            var usedBytes = parseInt(usage.monthly_total, 10) || 0;
            var limitBytes = modem.data_limit_enabled ? modem.data_limit_mb * 1024 * 1024 : 0;
            var percent = limitBytes > 0 ? Math.min(100, Math.round(usedBytes / limitBytes * 100)) : 0;

            var tokens = {
                'UUID': modem.uuid,
                'NAME': esc(modem.name),
                'STATUS': data === null ? '{{ lang._('Unreachable') }}'
                        : (connected ? '{{ lang._('Connected') }}' : '{{ lang._('Disconnected') }}'),
                'STATUS_CLASS': data === null ? 'default' : (connected ? 'success' : 'danger'),
                'IP_ADDRESS': esc(modem.ip_address),
                'NETWORK_TYPE': esc((data && data.network_type) || '-'),
                'OPERATOR': esc((data && data.network_operator) || '-'),
                'WAN_IP': esc((data && data.wan_ip) || '-'),
                'SIGNAL_DBM': signal.rssi !== undefined ? esc(signal.rssi) : '-',
                'SIGNAL_QUALITY': esc(signal.signal_quality || '-'),
                'DATA_PERCENT': percent,
                'DATA_USED': formatBytes(usedBytes),
                'DATA_LIMIT': limitBytes > 0 ? formatBytes(limitBytes) : '{{ lang._('No limit') }}',
                'CONNECT_DISABLED': connected ? 'disabled' : '',
                'DISCONNECT_DISABLED': connected ? '' : 'disabled'
            };
            for (var i = 1; i <= 5; i++) {
                tokens['BAR' + i] = bars >= i ? '' : 'inactive';
            }
            Object.keys(tokens).forEach(function(key) {
                tpl = tpl.split('%%' + key + '%%').join(String(tokens[key]));
            });
            return tpl;
        }

        function refreshModems() {
            ajaxGet('/api/hilink/monitor/overview', {}, function(data, status) {
                if (status !== 'success' || data['status'] !== 'ok') {
                    return;
                }
                $('#modemCount').text(data['total']);
                $('#noModemsMessage').toggle(data['total'] === 0);
                var container = $('#modemCards');
                container.empty();
                data['modems'].forEach(function(modem) {
                    ajaxGet('/api/hilink/monitor/status', {'modem_uuid': modem.uuid}, function(statusData, reqStatus) {
                        var modemData = (reqStatus === 'success' && statusData['status'] === 'ok')
                            ? statusData['data'] : null;
                        container.append(renderModemCard(modem, modemData));
                    });
                });
                $('#lastUpdate').text(new Date().toLocaleTimeString());
            });
        }

        function refreshAll() {
            updateServiceStatus();
            refreshModems();
        }

        function serviceCommand(command) {
            ajaxCall('/api/hilink/service/' + command, {}, function() {
                setTimeout(refreshAll, 1000);
            });
        }

        $('#btnServiceStart').click(function() { serviceCommand('start'); });
        $('#btnServiceStop').click(function() { serviceCommand('stop'); });
        $('#btnServiceRestart').click(function() { serviceCommand('restart'); });

        $('#modemCards').on('click', '.btn-connect, .btn-disconnect, .btn-reboot', function() {
            var uuid = $(this).data('uuid');
            var command = $(this).hasClass('btn-connect') ? 'connect'
                        : ($(this).hasClass('btn-disconnect') ? 'disconnect' : 'reboot');
            if (command === 'reboot' && !confirm('{{ lang._('Reboot this modem?') }}')) {
                return;
            }
            ajaxCall('/api/hilink/monitor/' + command, {'modem_uuid': uuid}, function() {
                setTimeout(refreshModems, 2000);
            });
        });

        refreshAll();
        refreshTimer = setInterval(refreshAll, 30000);

        // Honour the configured dashboard refresh interval
        // (Settings -> General -> Update interval, 10-300s; default 30s).
        ajaxGet('/api/hilink/settings/get', {}, function(data, status) {
            if (status !== 'success' || !data || !data.hilink || !data.hilink.general) {
                return;
            }
            var secs = parseInt(data.hilink.general.update_interval, 10);
            if (!isNaN(secs) && secs >= 10 && secs <= 300 && secs !== 30) {
                clearInterval(refreshTimer);
                refreshTimer = setInterval(refreshAll, secs * 1000);
            }
        });
        $(window).on('unload', function() { clearInterval(refreshTimer); });
    });
</script>

<div class="content-box">
    <div class="content-box-main">
        <div class="table-responsive">
            <div class="col-md-12">
                <h1>{{ lang._('HiLink Modem Dashboard') }}</h1>
                <hr/>
                
                <!-- Service Status -->
                <div class="row">
                    <div class="col-md-12">
                        <div class="panel panel-default">
                            <div class="panel-heading">
                                <h3 class="panel-title">
                                    <i class="fa fa-server"></i> {{ lang._('Service Status') }}
                                    <div class="pull-right">
                                        <button id="btnServiceStart" class="btn btn-xs btn-success" style="display:none;">
                                            <i class="fa fa-play"></i> {{ lang._('Start') }}
                                        </button>
                                        <button id="btnServiceStop" class="btn btn-xs btn-danger" style="display:none;">
                                            <i class="fa fa-stop"></i> {{ lang._('Stop') }}
                                        </button>
                                        <button id="btnServiceRestart" class="btn btn-xs btn-warning">
                                            <i class="fa fa-refresh"></i> {{ lang._('Restart') }}
                                        </button>
                                    </div>
                                </h3>
                            </div>
                            <div class="panel-body">
                                <div class="row">
                                    <div class="col-sm-3">
                                        <strong>{{ lang._('Status:') }}</strong>
                                        <span id="serviceStatus" class="label label-default">{{ lang._('Unknown') }}</span>
                                    </div>
                                    <div class="col-sm-3">
                                        <strong>{{ lang._('Enabled:') }}</strong>
                                        <span id="serviceEnabled" class="label label-default">{{ lang._('Unknown') }}</span>
                                    </div>
                                    <div class="col-sm-3">
                                        <strong>{{ lang._('Modems:') }}</strong>
                                        <span id="modemCount">0</span>
                                    </div>
                                    <div class="col-sm-3">
                                        <strong>{{ lang._('Last Update:') }}</strong>
                                        <span id="lastUpdate">-</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Modem Status Cards -->
                <div class="row" id="modemCards">
                    <!-- Modem cards will be dynamically inserted here -->
                </div>
                
                <!-- No Modems Message -->
                <div class="row" id="noModemsMessage" style="display:none;">
                    <div class="col-md-12">
                        <div class="alert alert-info">
                            <i class="fa fa-info-circle"></i> {{ lang._('No modems configured. Please add a modem in the settings.') }}
                            <a href="/ui/hilink/index/settings" class="btn btn-sm btn-primary pull-right">
                                <i class="fa fa-cog"></i> {{ lang._('Go to Settings') }}
                            </a>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>
</div>

<!-- Modem Card Template -->
<script type="text/template" id="modemCardTemplate">
    <div class="col-md-6">
        <div class="panel panel-default modem-card" data-uuid="%%UUID%%">
            <div class="panel-heading">
                <h3 class="panel-title">
                    <i class="fa fa-mobile"></i> %%NAME%%
                    <div class="pull-right">
                        <span class="connection-status label label-%%STATUS_CLASS%%">%%STATUS%%</span>
                    </div>
                </h3>
            </div>
            <div class="panel-body">
                <div class="row">
                    <div class="col-sm-6">
                        <div class="modem-info">
                            <strong>{{ lang._('IP Address:') }}</strong> %%IP_ADDRESS%%<br/>
                            <strong>{{ lang._('Network:') }}</strong> %%NETWORK_TYPE%%<br/>
                            <strong>{{ lang._('Operator:') }}</strong> %%OPERATOR%%<br/>
                            <strong>{{ lang._('WAN IP:') }}</strong> %%WAN_IP%%
                        </div>
                    </div>
                    <div class="col-sm-6">
                        <div class="signal-meter">
                            <div class="signal-value">%%SIGNAL_DBM%% dBm</div>
                            <div class="signal-bars">
                                <i class="fa fa-signal signal-bar-1 %%BAR1%%"></i>
                                <i class="fa fa-signal signal-bar-2 %%BAR2%%"></i>
                                <i class="fa fa-signal signal-bar-3 %%BAR3%%"></i>
                                <i class="fa fa-signal signal-bar-4 %%BAR4%%"></i>
                                <i class="fa fa-signal signal-bar-5 %%BAR5%%"></i>
                            </div>
                            <div class="signal-quality">%%SIGNAL_QUALITY%%</div>
                        </div>
                    </div>
                </div>
                <div class="row" style="margin-top: 10px;">
                    <div class="col-sm-12">
                        <div class="data-usage">
                            <strong>{{ lang._('Data Usage:') }}</strong>
                            <div class="progress">
                                <div class="progress-bar" role="progressbar" style="width: %%DATA_PERCENT%%%" 
                                     aria-valuenow="%%DATA_PERCENT%%" aria-valuemin="0" aria-valuemax="100">
                                    %%DATA_USED%% / %%DATA_LIMIT%%
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="row" style="margin-top: 10px;">
                    <div class="col-sm-12">
                        <div class="btn-group btn-group-sm" role="group">
                            <button class="btn btn-success btn-connect" data-uuid="%%UUID%%" %%CONNECT_DISABLED%%>
                                <i class="fa fa-plug"></i> {{ lang._('Connect') }}
                            </button>
                            <button class="btn btn-warning btn-disconnect" data-uuid="%%UUID%%" %%DISCONNECT_DISABLED%%>
                                <i class="fa fa-times"></i> {{ lang._('Disconnect') }}
                            </button>
                            <button class="btn btn-danger btn-reboot" data-uuid="%%UUID%%">
                                <i class="fa fa-power-off"></i> {{ lang._('Reboot') }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</script>

<style>
.modem-card {
    margin-bottom: 20px;
}

.signal-meter {
    text-align: center;
}

.signal-value {
    font-size: 24px;
    font-weight: bold;
    color: #333;
}

.signal-bars {
    margin: 10px 0;
    font-size: 20px;
}

.signal-bar-1 { color: #d9534f; }
.signal-bar-2 { color: #f0ad4e; }
.signal-bar-3 { color: #f0ad4e; }
.signal-bar-4 { color: #5cb85c; }
.signal-bar-5 { color: #5cb85c; }

.signal-bars .inactive {
    color: #ddd;
}

.signal-quality {
    font-size: 14px;
    color: #666;
}

.connection-status {
    font-size: 12px;
}

.data-usage .progress {
    margin-top: 5px;
}
</style>
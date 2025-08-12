{#
 # HiLink Dashboard View
 # Main dashboard for modem monitoring and management
 #}

<script>
    $( document ).ready(function() {
        // Initialize dashboard
        var dashboard = new HiLinkDashboard();
        dashboard.initialize();
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
                            <a href="/ui/hilink/settings" class="btn btn-sm btn-primary pull-right">
                                <i class="fa fa-cog"></i> {{ lang._('Go to Settings') }}
                            </a>
                        </div>
                    </div>
                </div>
                
                <!-- Charts Section -->
                <div class="row" id="chartsSection" style="display:none;">
                    <div class="col-md-6">
                        <div class="panel panel-default">
                            <div class="panel-heading">
                                <h3 class="panel-title">
                                    <i class="fa fa-signal"></i> {{ lang._('Signal Strength History') }}
                                </h3>
                            </div>
                            <div class="panel-body">
                                <canvas id="signalChart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="panel panel-default">
                            <div class="panel-heading">
                                <h3 class="panel-title">
                                    <i class="fa fa-exchange"></i> {{ lang._('Data Usage') }}
                                </h3>
                            </div>
                            <div class="panel-body">
                                <canvas id="dataChart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Alerts Section -->
                <div class="row" id="alertsSection" style="display:none;">
                    <div class="col-md-12">
                        <div class="panel panel-default">
                            <div class="panel-heading">
                                <h3 class="panel-title">
                                    <i class="fa fa-exclamation-triangle"></i> {{ lang._('Active Alerts') }}
                                </h3>
                            </div>
                            <div class="panel-body">
                                <div id="alertsList">
                                    <!-- Alerts will be dynamically inserted here -->
                                </div>
                            </div>
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
                            <button class="btn btn-info btn-details" data-uuid="%%UUID%%">
                                <i class="fa fa-info-circle"></i> {{ lang._('Details') }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</script>

<!-- Include dashboard JavaScript -->
<script type="text/javascript" src="/ui/js/hilink/dashboard.js"></script>

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
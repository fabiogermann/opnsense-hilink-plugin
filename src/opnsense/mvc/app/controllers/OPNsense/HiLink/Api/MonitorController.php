<?php
/**
 * HiLink Monitor Controller
 * Provides real-time monitoring data
 */

namespace OPNsense\HiLink\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;
use OPNsense\HiLink\HiLink;

class MonitorController extends ApiControllerBase
{
    /**
     * Get current modem status
     * @return array
     */
    public function statusAction()
    {
        $backend = new Backend();
        $modemUuid = $this->request->get('modem_uuid', '');
        
        if (empty($modemUuid)) {
            // Get first enabled modem
            $model = new HiLink();
            foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
                if ((string)$modem->enabled === '1') {
                    $modemUuid = $uuid;
                    break;
                }
            }
        }
        
        if (empty($modemUuid)) {
            return ['error' => 'No modem configured or enabled'];
        }
        
        $response = $backend->configdRun("hilink getstatus {$modemUuid}");
        $data = json_decode($response, true);
        
        if ($data === null) {
            return [
                'error' => 'Failed to get modem status',
                'raw_response' => $response
            ];
        }
        
        return [
            'status' => 'ok',
            'data' => $data
        ];
    }

    /**
     * Get signal information
     * @return array
     */
    public function signalAction()
    {
        $modemUuid = $this->request->get('modem_uuid', '');
        
        // Mock data for now - will be replaced with actual backend call
        return [
            'status' => 'ok',
            'data' => [
                'rssi' => -65,
                'rsrp' => -95,
                'rsrq' => -10,
                'sinr' => 15,
                'signal_bars' => 4,
                'signal_quality' => 'good',
                'cell_id' => 12345,
                'band' => 'B3',
                'frequency' => 1800
            ]
        ];
    }

    /**
     * Get data usage statistics
     * @return array
     */
    public function dataAction()
    {
        $modemUuid = $this->request->get('modem_uuid', '');
        $period = $this->request->get('period', 'session');
        
        // Mock data for now
        return [
            'status' => 'ok',
            'data' => [
                'session' => [
                    'upload' => 1048576,
                    'download' => 10485760,
                    'total' => 11534336,
                    'duration' => 3600
                ],
                'today' => [
                    'upload' => 5242880,
                    'download' => 52428800,
                    'total' => 57671680
                ],
                'month' => [
                    'upload' => 1073741824,
                    'download' => 10737418240,
                    'total' => 11811160064
                ]
            ]
        ];
    }

    /**
     * Get historical metrics
     * @return array
     */
    public function metricsAction()
    {
        $modemUuid = $this->request->get('modem_uuid', '');
        $start = $this->request->get('start', time() - 3600);
        $end = $this->request->get('end', time());
        $resolution = $this->request->get('resolution', '5min');
        
        $backend = new Backend();
        $response = $backend->configdRun("hilink getmetrics {$modemUuid}");
        $data = json_decode($response, true);
        
        if ($data === null) {
            // Return mock data for demonstration
            $timestamps = [];
            $signal_strength = [];
            $data_rx = [];
            $data_tx = [];
            
            $current = $start;
            while ($current <= $end) {
                $timestamps[] = date('c', $current);
                $signal_strength[] = -65 + rand(-10, 10);
                $data_rx[] = rand(1000000, 10000000);
                $data_tx[] = rand(500000, 5000000);
                $current += 300; // 5 minute intervals
            }
            
            return [
                'status' => 'ok',
                'data' => [
                    'timestamps' => $timestamps,
                    'metrics' => [
                        'signal_strength' => $signal_strength,
                        'data_rx' => $data_rx,
                        'data_tx' => $data_tx,
                        'connection_state' => array_fill(0, count($timestamps), 1)
                    ]
                ]
            ];
        }
        
        return [
            'status' => 'ok',
            'data' => $data
        ];
    }

    /**
     * Get all modems overview
     * @return array
     */
    public function overviewAction()
    {
        $model = new HiLink();
        $modems = [];
        
        foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
            if ((string)$modem->enabled === '1') {
                $modems[] = [
                    'uuid' => $uuid,
                    'name' => (string)$modem->name,
                    'ip_address' => (string)$modem->ip_address,
                    'enabled' => true,
                    'status' => $this->getModemQuickStatus($uuid)
                ];
            }
        }
        
        return [
            'status' => 'ok',
            'modems' => $modems,
            'total' => count($modems)
        ];
    }

    /**
     * Get alerts
     * @return array
     */
    public function alertsAction()
    {
        $active = $this->request->get('active', 'true') === 'true';
        
        // Mock alerts for demonstration
        $alerts = [];
        
        if ($active) {
            // Check for any active alerts
            $model = new HiLink();
            $lowSignalThreshold = (int)$model->alerts->low_signal_threshold;
            
            // This would normally check actual signal levels
            // For now, return empty or mock alert
            $alerts = [];
        }
        
        return [
            'status' => 'ok',
            'alerts' => $alerts,
            'count' => count($alerts)
        ];
    }

    /**
     * Get quick status for a modem
     * @param string $uuid
     * @return array
     */
    private function getModemQuickStatus($uuid)
    {
        // This would normally query the backend
        // For now, return mock status
        return [
            'connected' => true,
            'signal' => -65,
            'network_type' => '4G',
            'operator' => 'Carrier Name'
        ];
    }

    /**
     * Connect modem
     * @return array
     */
    public function connectAction()
    {
        if ($this->request->isPost()) {
            $modemUuid = $this->request->get('modem_uuid', '');
            
            if (empty($modemUuid)) {
                return ['status' => 'error', 'message' => 'Modem UUID required'];
            }
            
            $backend = new Backend();
            $response = $backend->configdRun("hilink connect {$modemUuid}");
            
            return [
                'status' => 'ok',
                'message' => 'Connect command sent',
                'response' => $response
            ];
        }
        
        return ['status' => 'error', 'message' => 'Invalid request method'];
    }

    /**
     * Disconnect modem
     * @return array
     */
    public function disconnectAction()
    {
        if ($this->request->isPost()) {
            $modemUuid = $this->request->get('modem_uuid', '');
            
            if (empty($modemUuid)) {
                return ['status' => 'error', 'message' => 'Modem UUID required'];
            }
            
            $backend = new Backend();
            $response = $backend->configdRun("hilink disconnect {$modemUuid}");
            
            return [
                'status' => 'ok',
                'message' => 'Disconnect command sent',
                'response' => $response
            ];
        }
        
        return ['status' => 'error', 'message' => 'Invalid request method'];
    }

    /**
     * Reboot modem
     * @return array
     */
    public function rebootAction()
    {
        if ($this->request->isPost()) {
            $modemUuid = $this->request->get('modem_uuid', '');
            
            if (empty($modemUuid)) {
                return ['status' => 'error', 'message' => 'Modem UUID required'];
            }
            
            $backend = new Backend();
            $response = $backend->configdRun("hilink reboot {$modemUuid}");
            
            return [
                'status' => 'ok',
                'message' => 'Reboot command sent',
                'response' => $response
            ];
        }
        
        return ['status' => 'error', 'message' => 'Invalid request method'];
    }
}
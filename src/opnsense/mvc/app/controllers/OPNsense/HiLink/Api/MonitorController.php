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
     * Validate that a request supplied uuid belongs to a configured modem.
     * Prevents arbitrary strings from being passed to configd.
     * @param string $uuid
     * @return bool
     */
    private function isKnownModem($uuid)
    {
        if (!preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i', $uuid)) {
            return false;
        }
        $model = new HiLink();
        return $model->getNodeByReference('modems.modem.' . $uuid) !== null;
    }

    /**
     * Fetch requested modem uuid, falling back to the first enabled modem
     * @return string
     */
    private function resolveModemUuid()
    {
        $modemUuid = (string)$this->request->get('modem_uuid', null, '');

        if (empty($modemUuid)) {
            $model = new HiLink();
            foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
                if ((string)$modem->enabled === '1') {
                    $modemUuid = $uuid;
                    break;
                }
            }
        }

        return $modemUuid;
    }

    /**
     * Get current modem status (connection, signal and usage)
     * @return array
     */
    public function statusAction()
    {
        $modemUuid = $this->resolveModemUuid();

        if (empty($modemUuid)) {
            return ['error' => 'No modem configured or enabled'];
        }
        if (!$this->isKnownModem($modemUuid)) {
            return ['error' => 'Unknown modem'];
        }

        $backend = new Backend();
        $response = $backend->configdpRun('hilink getstatus', [$modemUuid]);
        $data = json_decode((string)$response, true);

        if ($data === null) {
            return ['error' => 'Failed to get modem status'];
        }

        return ['status' => 'ok', 'data' => $data];
    }

    /**
     * Get signal information
     * @return array
     */
    public function signalAction()
    {
        $result = $this->statusAction();
        if (!empty($result['error'])) {
            return $result;
        }

        return ['status' => 'ok', 'data' => $result['data']['signal'] ?? []];
    }

    /**
     * Get data usage statistics
     * @return array
     */
    public function dataAction()
    {
        $result = $this->statusAction();
        if (!empty($result['error'])) {
            return $result;
        }

        return ['status' => 'ok', 'data' => $result['data']['usage'] ?? []];
    }

    /**
     * Get historical metrics
     * @return array
     */
    public function metricsAction()
    {
        $modemUuid = $this->resolveModemUuid();

        if (empty($modemUuid) || !$this->isKnownModem($modemUuid)) {
            return ['error' => 'Unknown modem'];
        }

        $backend = new Backend();
        $response = $backend->configdpRun('hilink getmetrics', [$modemUuid]);
        $data = json_decode((string)$response, true);

        if ($data === null) {
            return ['error' => 'No metrics available'];
        }

        return ['status' => 'ok', 'data' => $data];
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
                    'data_limit_enabled' => (string)$modem->data_limit_enabled === '1',
                    'data_limit_mb' => (int)((string)$modem->data_limit_mb),
                    'enabled' => true,
                ];
            }
        }

        return [
            'status' => 'ok',
            'modems' => $modems,
            'total' => count($modems),
        ];
    }

    /**
     * Get alerts
     * @return array
     */
    public function alertsAction()
    {
        // Alerting is evaluated by the backend service; nothing queued via the API yet.
        return ['status' => 'ok', 'alerts' => [], 'count' => 0];
    }

    /**
     * List the modem's APN profiles and the active one
     * @return array
     */
    public function profilesAction()
    {
        $modemUuid = $this->resolveModemUuid();
        if (empty($modemUuid)) {
            return ['status' => 'error', 'message' => 'No modem configured or enabled'];
        }
        if (!$this->isKnownModem($modemUuid)) {
            return ['status' => 'error', 'message' => 'Unknown modem'];
        }

        $backend = new Backend();
        $response = $backend->configdpRun('hilink getprofiles', [$modemUuid]);
        $data = json_decode((string)$response, true);
        if (!is_array($data)) {
            return ['status' => 'error', 'message' => 'No response from modem'];
        }
        return $data;
    }

    /**
     * Run a modem control command via configd
     * @param string $command connect|disconnect|reboot
     * @return array
     */
    private function modemCommand($command)
    {
        if (!$this->request->isPost()) {
            return ['status' => 'error', 'message' => 'Invalid request method'];
        }

        $modemUuid = (string)$this->request->get('modem_uuid', null, '');
        if (empty($modemUuid)) {
            $modemUuid = (string)$this->request->getPost('modem_uuid', null, '');
        }

        if (empty($modemUuid)) {
            return ['status' => 'error', 'message' => 'Modem UUID required'];
        }
        if (!$this->isKnownModem($modemUuid)) {
            return ['status' => 'error', 'message' => 'Unknown modem'];
        }

        $backend = new Backend();
        $response = (string)$backend->configdpRun('hilink ' . $command, [$modemUuid]);

        // hilink_control.py reports {"status": "ok|error", ...}; propagate the
        // real outcome instead of claiming success unconditionally.
        $data = json_decode($response, true);
        $ok = is_array($data) && ($data['status'] ?? '') === 'ok';

        return [
            'status' => $ok ? 'ok' : 'error',
            'message' => $ok
                ? ucfirst($command) . ' command sent'
                : ($data['message'] ?? ucfirst($command) . ' command failed'),
            'response' => $response,
        ];
    }

    /**
     * Connect modem
     * @return array
     */
    public function connectAction()
    {
        return $this->modemCommand('connect');
    }

    /**
     * Disconnect modem
     * @return array
     */
    public function disconnectAction()
    {
        return $this->modemCommand('disconnect');
    }

    /**
     * Reboot modem
     * @return array
     */
    public function rebootAction()
    {
        return $this->modemCommand('reboot');
    }
}

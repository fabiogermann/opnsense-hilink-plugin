<?php

/**
 * HiLink Service Controller
 * Manages service lifecycle and status
 */

namespace OPNsense\HiLink\Api;

use OPNsense\Base\ApiMutableServiceControllerBase;
use OPNsense\Core\Backend;

class ServiceController extends ApiMutableServiceControllerBase
{
    protected static $internalServiceClass = '\OPNsense\HiLink\HiLink';
    protected static $internalServiceEnabled = 'general.enabled';
    protected static $internalServiceName = 'hilink';

    /**
     * Start HiLink service
     * @return array
     */
    public function startAction()
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $response = $backend->configdRun('hilink start');
            return ['response' => $response, 'status' => 'ok'];
        }
        return ['response' => 'error', 'status' => 'failed'];
    }

    /**
     * Stop HiLink service
     * @return array
     */
    public function stopAction()
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $response = $backend->configdRun('hilink stop');
            return ['response' => $response, 'status' => 'ok'];
        }
        return ['response' => 'error', 'status' => 'failed'];
    }

    /**
     * Restart HiLink service
     * @return array
     */
    public function restartAction()
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $response = $backend->configdRun('hilink restart');
            return ['response' => $response, 'status' => 'ok'];
        }
        return ['response' => 'error', 'status' => 'failed'];
    }

    /**
     * Get service status
     * @return array
     */
    public function statusAction()
    {
        $backend = new Backend();
        $response = trim((string)$backend->configdRun('hilink status'));

        return [
            'status' => $response,
            'running' => ($response === 'running'),
            'enabled' => $this->serviceEnabled(),
        ];
    }

    /**
     * Test configuration
     * @return array
     */
    public function testAction()
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $response = (string)$backend->configdRun('hilink test');
            $success = strpos($response, 'success') !== false;

            return [
                'status' => $success ? 'ok' : 'error',
                'message' => $response,
            ];
        }
        return ['status' => 'error', 'message' => 'Invalid request'];
    }

    /**
     * Read the current settings from a configured modem without changing it.
     * Used by the first-use wizard to import existing modem settings.
     * @param string|null $uuid modem uuid
     * @return array
     */
    public function probeAction($uuid = null)
    {
        if (!$this->request->isPost() || empty($uuid)) {
            return ['status' => 'error', 'message' => 'Invalid request'];
        }
        if (!preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i', $uuid)) {
            return ['status' => 'error', 'message' => 'Invalid modem UUID'];
        }

        $backend = new Backend();
        $response = trim((string)$backend->configdpRun('hilink probe', [$uuid]));
        $data = json_decode($response, true);
        if (!is_array($data)) {
            return ['status' => 'error', 'message' => 'No response from modem probe'];
        }
        return $data;
    }

    /**
     * Check if service is enabled
     * @return bool
     */
    protected function serviceEnabled()
    {
        $model = $this->getModel();
        return (string)$model->general->enabled === '1';
    }

    /**
     * Reconfigure service: the daemon reads its settings from config.xml,
     * so a restart (or stop when disabled) is all that is needed.
     * @return array
     */
    public function reconfigureAction()
    {
        $status = 'failed';

        if ($this->request->isPost()) {
            $status = 'ok';

            $backend = new Backend();
            if ($this->serviceEnabled()) {
                $backend->configdRun('hilink restart');
            } else {
                $backend->configdRun('hilink stop');
            }
        }

        return ['status' => $status];
    }
}

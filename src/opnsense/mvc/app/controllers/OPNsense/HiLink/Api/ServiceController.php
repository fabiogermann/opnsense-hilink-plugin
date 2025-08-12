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
    protected static $internalServiceTemplate = 'OPNsense/HiLink';
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
        $response = trim($backend->configdRun('hilink status'));
        
        $result = [
            'status' => $response,
            'running' => ($response === 'running'),
            'enabled' => $this->isEnabled()
        ];
        
        // Get additional service info if running
        if ($result['running']) {
            try {
                $metrics = json_decode($backend->configdRun('hilink getmetrics'), true);
                if ($metrics) {
                    $result['metrics'] = $metrics;
                }
            } catch (\Exception $e) {
                // Ignore metrics errors
            }
        }
        
        return $result;
    }

    /**
     * Test configuration
     * @return array
     */
    public function testAction()
    {
        if ($this->request->isPost()) {
            $backend = new Backend();
            $response = $backend->configdRun('hilink test');
            $success = strpos($response, 'success') !== false;
            
            return [
                'status' => $success ? 'ok' : 'error',
                'message' => $response
            ];
        }
        return ['status' => 'error', 'message' => 'Invalid request'];
    }

    /**
     * Check if service is enabled
     * @return bool
     */
    private function isEnabled()
    {
        $model = $this->getModel();
        return (string)$model->general->enabled === '1';
    }

    /**
     * Reconfigure service
     * @return array
     */
    public function reconfigureAction()
    {
        $status = 'failed';
        
        if ($this->request->isPost()) {
            $status = 'ok';
            $this->sessionClose();
            
            $backend = new Backend();
            $backend->configdRun('template reload OPNsense/HiLink');
            
            if ($this->isEnabled()) {
                $backend->configdRun('hilink restart');
            } else {
                $backend->configdRun('hilink stop');
            }
        }
        
        return ['status' => $status];
    }
}
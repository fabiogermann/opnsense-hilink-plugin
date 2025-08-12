<?php
/**
 * HiLink Settings Controller
 * Manages plugin configuration
 */

namespace OPNsense\HiLink\Api;

use OPNsense\Base\ApiMutableModelControllerBase;
use OPNsense\Base\UIModelGrid;
use OPNsense\Core\Config;
use OPNsense\HiLink\HiLink;

class SettingsController extends ApiMutableModelControllerBase
{
    protected static $internalModelClass = '\OPNsense\HiLink\HiLink';
    protected static $internalModelName = 'hilink';

    /**
     * Get configuration
     * @return array
     */
    public function getAction()
    {
        $result = [];
        if ($this->request->isGet()) {
            $model = $this->getModel();
            
            // Get general settings
            $result['general'] = [
                'enabled' => (string)$model->general->enabled,
                'update_interval' => (string)$model->general->update_interval,
                'data_retention' => (string)$model->general->data_retention,
                'debug_logging' => (string)$model->general->debug_logging
            ];
            
            // Get modems
            $result['modems'] = [];
            foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
                $result['modems'][] = [
                    'uuid' => $uuid,
                    'name' => (string)$modem->name,
                    'enabled' => (string)$modem->enabled,
                    'ip_address' => (string)$modem->ip_address,
                    'username' => (string)$modem->username,
                    'auto_connect' => (string)$modem->auto_connect,
                    'roaming_enabled' => (string)$modem->roaming_enabled,
                    'network_mode' => (string)$modem->network_mode,
                    'data_limit_enabled' => (string)$modem->data_limit_enabled,
                    'data_limit_mb' => (string)$modem->data_limit_mb
                ];
            }
            
            // Get alerts
            $result['alerts'] = [
                'low_signal_threshold' => (string)$model->alerts->low_signal_threshold,
                'data_limit_enabled' => (string)$model->alerts->data_limit_enabled,
                'data_limit_mb' => (string)$model->alerts->data_limit_mb,
                'email_alerts' => (string)$model->alerts->email_alerts,
                'email_to' => (string)$model->alerts->email_to,
                'smtp_server' => (string)$model->alerts->smtp_server
            ];
        }
        
        return $result;
    }

    /**
     * Update configuration
     * @return array
     */
    public function setAction()
    {
        $result = ['result' => 'failed'];
        
        if ($this->request->isPost()) {
            $model = $this->getModel();
            $data = $this->request->getPost();
            
            // Update general settings
            if (isset($data['general'])) {
                foreach ($data['general'] as $key => $value) {
                    if ($model->general->$key !== null) {
                        $model->general->$key = $value;
                    }
                }
            }
            
            // Update alerts
            if (isset($data['alerts'])) {
                foreach ($data['alerts'] as $key => $value) {
                    if ($model->alerts->$key !== null) {
                        $model->alerts->$key = $value;
                    }
                }
            }
            
            // Validate and save
            $validation = $this->validateAndSave($model);
            if ($validation['result'] === 'saved') {
                $result = ['result' => 'saved'];
            } else {
                $result = ['result' => 'failed', 'validations' => $validation['validations']];
            }
        }
        
        return $result;
    }

    /**
     * Get modem list for grid
     * @return array
     */
    public function searchModemAction()
    {
        $this->sessionClose();
        $model = $this->getModel();
        $grid = new UIModelGrid($model->modems->modem);
        
        return $grid->fetchBindRequest(
            $this->request,
            ['enabled', 'name', 'ip_address', 'network_mode', 'auto_connect']
        );
    }

    /**
     * Get single modem configuration
     * @param string $uuid
     * @return array
     */
    public function getModemAction($uuid = null)
    {
        $model = $this->getModel();
        
        if ($uuid != null) {
            $node = $model->getNodeByReference('modems.modem.' . $uuid);
            if ($node != null) {
                return ['modem' => $node->getNodes()];
            }
        }
        
        // Return template for new modem
        $node = $model->modems->modem->add();
        return ['modem' => $node->getNodes()];
    }

    /**
     * Add or update modem
     * @param string $uuid
     * @return array
     */
    public function setModemAction($uuid = null)
    {
        $result = ['result' => 'failed'];
        
        if ($this->request->isPost()) {
            $model = $this->getModel();
            
            if ($uuid != null) {
                $node = $model->getNodeByReference('modems.modem.' . $uuid);
            } else {
                $node = $model->modems->modem->add();
                $uuid = $node->generateUUID();
                $node->uuid = $uuid;
            }
            
            if ($node != null) {
                $node->setNodes($this->request->getPost('modem'));
                $validation = $this->validateAndSave($model);
                
                if ($validation['result'] === 'saved') {
                    $result = ['result' => 'saved', 'uuid' => $uuid];
                } else {
                    $result = ['result' => 'failed', 'validations' => $validation['validations']];
                }
            }
        }
        
        return $result;
    }

    /**
     * Delete modem
     * @param string $uuid
     * @return array
     */
    public function delModemAction($uuid)
    {
        $result = ['result' => 'failed'];
        
        if ($this->request->isPost()) {
            $model = $this->getModel();
            
            if ($uuid != null) {
                if ($model->modems->modem->del($uuid)) {
                    $validation = $this->validateAndSave($model);
                    if ($validation['result'] === 'saved') {
                        $result = ['result' => 'deleted'];
                    }
                }
            }
        }
        
        return $result;
    }

    /**
     * Toggle modem enabled status
     * @param string $uuid
     * @return array
     */
    public function toggleModemAction($uuid)
    {
        $result = ['result' => 'failed'];
        
        if ($this->request->isPost() && $uuid != null) {
            $model = $this->getModel();
            $node = $model->getNodeByReference('modems.modem.' . $uuid);
            
            if ($node != null) {
                $node->enabled = (string)$node->enabled === '1' ? '0' : '1';
                $validation = $this->validateAndSave($model);
                
                if ($validation['result'] === 'saved') {
                    $result = [
                        'result' => 'saved',
                        'enabled' => (string)$node->enabled === '1'
                    ];
                }
            }
        }
        
        return $result;
    }

    /**
     * Validate configuration
     * @return array
     */
    public function validateAction()
    {
        $result = ['valid' => false, 'errors' => []];
        
        if ($this->request->isPost()) {
            $model = $this->getModel();
            $model->setNodes($this->request->getPost());
            
            $messages = $model->performValidation();
            
            if (count($messages) == 0) {
                $result['valid'] = true;
            } else {
                foreach ($messages as $field => $message) {
                    $result['errors'][] = [
                        'field' => $message->getField(),
                        'message' => $message->getMessage()
                    ];
                }
            }
        }
        
        return $result;
    }

    /**
     * Export configuration
     * @return array
     */
    public function exportAction()
    {
        $model = $this->getModel();
        $config = [];
        
        // Export general settings
        $config['general'] = $model->general->getNodes();
        
        // Export modems
        $config['modems'] = [];
        foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
            $modemData = $modem->getNodes();
            $modemData['uuid'] = $uuid;
            $config['modems'][] = $modemData;
        }
        
        // Export alerts
        $config['alerts'] = $model->alerts->getNodes();
        
        // Set headers for download
        $this->response->setHeader('Content-Type', 'application/json');
        $this->response->setHeader(
            'Content-Disposition',
            'attachment; filename="hilink-config-' . date('Y-m-d') . '.json"'
        );
        
        return json_encode($config, JSON_PRETTY_PRINT);
    }

    /**
     * Import configuration
     * @return array
     */
    public function importAction()
    {
        $result = ['result' => 'failed'];
        
        if ($this->request->isPost()) {
            $data = $this->request->getPost('config');
            
            if (!empty($data)) {
                try {
                    $config = json_decode($data, true);
                    
                    if ($config !== null) {
                        $model = $this->getModel();
                        
                        // Import general settings
                        if (isset($config['general'])) {
                            $model->general->setNodes($config['general']);
                        }
                        
                        // Import alerts
                        if (isset($config['alerts'])) {
                            $model->alerts->setNodes($config['alerts']);
                        }
                        
                        // Import modems (clear existing first)
                        if (isset($config['modems'])) {
                            // Remove existing modems
                            foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
                                $model->modems->modem->del($uuid);
                            }
                            
                            // Add imported modems
                            foreach ($config['modems'] as $modemConfig) {
                                $node = $model->modems->modem->add();
                                unset($modemConfig['uuid']); // Let system generate new UUID
                                $node->setNodes($modemConfig);
                            }
                        }
                        
                        $validation = $this->validateAndSave($model);
                        if ($validation['result'] === 'saved') {
                            $result = ['result' => 'imported'];
                        } else {
                            $result = ['result' => 'failed', 'validations' => $validation['validations']];
                        }
                    } else {
                        $result = ['result' => 'failed', 'message' => 'Invalid JSON format'];
                    }
                } catch (\Exception $e) {
                    $result = ['result' => 'failed', 'message' => $e->getMessage()];
                }
            }
        }
        
        return $result;
    }
}
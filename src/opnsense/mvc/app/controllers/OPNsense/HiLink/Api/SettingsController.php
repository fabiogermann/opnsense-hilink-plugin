<?php

/**
 * HiLink Settings Controller
 * Manages plugin configuration
 */

namespace OPNsense\HiLink\Api;

use OPNsense\Base\ApiMutableModelControllerBase;

/**
 * getAction()/setAction() are inherited from ApiMutableModelControllerBase and
 * expose the full model under the "hilink" key for standard form binding.
 */
class SettingsController extends ApiMutableModelControllerBase
{
    protected static $internalModelClass = '\OPNsense\HiLink\HiLink';
    protected static $internalModelName = 'hilink';

    /**
     * Search modems for the bootgrid
     * @return array
     */
    public function searchModemAction()
    {
        return $this->searchBase(
            'modems.modem',
            ['enabled', 'name', 'ip_address', 'network_mode', 'auto_connect']
        );
    }

    /**
     * Get single modem configuration (or an empty template when no uuid given)
     * @param string|null $uuid
     * @return array
     */
    public function getModemAction($uuid = null)
    {
        return $this->getBase('modem', 'modems.modem', $uuid);
    }

    /**
     * Add new modem
     * @return array
     */
    public function addModemAction()
    {
        return $this->addBase('modem', 'modems.modem');
    }

    /**
     * Update modem
     * @param string $uuid
     * @return array
     */
    public function setModemAction($uuid)
    {
        return $this->setBase('modem', 'modems.modem', $uuid);
    }

    /**
     * Delete modem
     * @param string $uuid
     * @return array
     */
    public function delModemAction($uuid)
    {
        return $this->delBase('modems.modem', $uuid);
    }

    /**
     * Toggle modem enabled status
     * @param string $uuid
     * @param string|null $enabled
     * @return array
     */
    public function toggleModemAction($uuid, $enabled = null)
    {
        return $this->toggleBase('modems.modem', $uuid, $enabled);
    }

    /**
     * Export configuration as JSON payload
     * @return array
     */
    public function exportAction()
    {
        $model = $this->getModel();
        $config = [
            'general' => $model->general->getNodes(),
            'alerts' => $model->alerts->getNodes(),
            'modems' => [],
        ];

        foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
            $modemData = $modem->getNodes();
            $modemData['uuid'] = $uuid;
            $config['modems'][] = $modemData;
        }

        return ['status' => 'ok', 'config' => $config];
    }

    /**
     * Import configuration
     * @return array
     */
    public function importAction()
    {
        $result = ['result' => 'failed'];

        if (!$this->request->isPost()) {
            return $result;
        }

        $data = $this->request->getPost('config');
        if (empty($data)) {
            return $result;
        }

        $config = is_array($data) ? $data : json_decode((string)$data, true);
        if ($config === null) {
            return ['result' => 'failed', 'message' => 'Invalid JSON format'];
        }

        $model = $this->getModel();

        if (isset($config['general'])) {
            $model->general->setNodes($config['general']);
        }
        if (isset($config['alerts'])) {
            $model->alerts->setNodes($config['alerts']);
        }
        if (isset($config['modems'])) {
            // replace existing modems with the imported set
            foreach ($model->modems->modem->iterateItems() as $uuid => $modem) {
                $model->modems->modem->del($uuid);
            }
            foreach ($config['modems'] as $modemConfig) {
                unset($modemConfig['uuid']); // let the system generate a new UUID
                $node = $model->modems->modem->add();
                $node->setNodes($modemConfig);
            }
        }

        $saved = $this->save();
        if (!empty($saved['result']) && $saved['result'] === 'saved') {
            return ['result' => 'imported'];
        }

        return ['result' => 'failed', 'validations' => $saved['validations'] ?? []];
    }
}

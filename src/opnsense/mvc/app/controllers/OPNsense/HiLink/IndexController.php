<?php
/**
 * HiLink Index Controller
 * Main controller for web interface
 */

namespace OPNsense\HiLink;

use OPNsense\Base\IndexController as BaseIndexController;
use OPNsense\Core\Config;

class IndexController extends BaseIndexController
{
    /**
     * Main index/dashboard page
     */
    public function indexAction()
    {
        // Set page title
        $this->view->title = "HiLink Modem Management";
        
        // Include required JavaScript and CSS
        $this->view->pick('OPNsense/HiLink/index');
        
        // Pass initial data to view
        $this->view->formDialogModem = $this->getForm("dialogModem");
        $this->view->formDialogSettings = $this->getForm("dialogSettings");
    }
    
    /**
     * Settings page
     */
    public function settingsAction()
    {
        $this->view->title = "HiLink Settings";
        $this->view->pick('OPNsense/HiLink/settings');
        
        // Load forms
        $this->view->formGeneralSettings = $this->getForm("generalSettings");
        $this->view->formAlertSettings = $this->getForm("alertSettings");
    }
    
    /**
     * Monitoring page
     */
    public function monitorAction()
    {
        $this->view->title = "HiLink Monitoring";
        $this->view->pick('OPNsense/HiLink/monitor');
    }
}
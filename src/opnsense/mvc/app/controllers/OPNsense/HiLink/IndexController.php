<?php

/**
 * HiLink Index Controller
 * Main controller for web interface
 */

namespace OPNsense\HiLink;

use OPNsense\Base\IndexController as BaseIndexController;

class IndexController extends BaseIndexController
{
    /**
     * Main index/dashboard page
     */
    public function indexAction()
    {
        $this->view->title = gettext('HiLink Modem Management');
        $this->view->pick('OPNsense/HiLink/index');
    }

    /**
     * Settings page
     */
    public function settingsAction()
    {
        $this->view->title = gettext('HiLink Settings');
        $this->view->generalForm = $this->getForm('generalSettings');
        $this->view->alertForm = $this->getForm('alertSettings');
        $this->view->formDialogModem = $this->getForm('dialogModem');
        $this->view->pick('OPNsense/HiLink/settings');
    }
}

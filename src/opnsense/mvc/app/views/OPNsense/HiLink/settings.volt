{#
 # HiLink Settings View
 # General settings, modem list and alert configuration
 #}

<script>
    $( document ).ready(function() {
        var data_get_map = {
            'frm_GeneralSettings': "/api/hilink/settings/get",
            'frm_AlertSettings': "/api/hilink/settings/get"
        };
        mapDataToFormUI(data_get_map).done(function(data) {
            formatTokenizersUI();
            $('.selectpicker').selectpicker('refresh');
        });

        $("#grid-modems").UIBootgrid({
            search: '/api/hilink/settings/searchModem',
            get: '/api/hilink/settings/getModem/',
            set: '/api/hilink/settings/setModem/',
            add: '/api/hilink/settings/addModem/',
            del: '/api/hilink/settings/delModem/',
            toggle: '/api/hilink/settings/toggleModem/'
        });

        // Populate the "Active APN profile" dropdown live from the modem
        $('#DialogModem').on('shown.bs.modal', function() {
            if (!editModemUuid) {
                return; // adding a new modem — no live profile list yet
            }
            // Replace the text input with a select for better UX, then
            // populate it live from the modem's profile list.
            var $input = $('#modem\\.active_profile');
            var currentVal = $input.val() || '';
            if ($input.is('input')) {
                var $sel = $('<select/>').attr('id', 'modem.active_profile').attr('name', 'modem.active_profile').addClass('form-control');
                $sel.append($('<option/>').val('').text('(keep current)'));
                $input.replaceWith($sel);
            }
            var $sel = $('#modem\\.active_profile');
            $sel.find('option').not(':first').remove();
            ajaxGet('/api/hilink/monitor/profiles', {'modem_uuid': editModemUuid}, function(data, status) {
                if (status !== 'success' || !data || data['status'] !== 'ok') {
                    return;
                }
                var active = data['active'] || currentVal;
                (data['profiles'] || []).forEach(function(p) {
                    var label = p['Name'] || ('Profile ' + p['Index']);
                    if (p['Apn']) { label += ' (' + p['Apn'] + ')'; }
                    var $opt = $('<option/>').val(p['Index']).text(label);
                    if (p['Index'] === active) { $opt.prop('selected', true); }
                    $sel.append($opt);
                });
            });
        });

        /**
         * Import a modem from a nvram.bak backup file
         */
        function importSetStatus(message, level) {
            $("#import_status")
                .removeClass("alert-info alert-warning alert-danger")
                .addClass("alert-" + (level || "info"))
                .text(message)
                .show();
        }

        $(document).on('click', '#btnImportBackup', function() {
            $("#import_status").hide();
            $("#ImportBackup").modal('show');
        });

        $("#import_finish").click(function() {
            var nvramFile = $("#import_nvram_file")[0].files[0];
            if (nvramFile === undefined) {
                importSetStatus("{{ lang._('Please select a nvram.bak file first.') }}", 'warning');
                return;
            }
            var modem = {
                'name': $("#import_name").val(),
                'ip_address': $("#import_ip").val(),
                'username': $("#import_username").val(),
                'password': $("#import_password").val(),
                'enabled': '0'
            };
            ajaxCall("/api/hilink/settings/addModem/", {'modem': modem}, function(data) {
                if (!data || data.result !== 'saved') {
                    var messages = [];
                    if (data && data.validations) {
                        Object.keys(data.validations).forEach(function(key) {
                            messages.push(data.validations[key]);
                        });
                    }
                    importSetStatus(messages.join('; ') || "{{ lang._('Could not save the modem.') }}", 'danger');
                    return;
                }
                var uuid = data.uuid;
                var reader = new FileReader();
                reader.onload = function(ev) {
                    var fields = parseNvramBackup(ev.target.result);
                    if (Object.keys(fields).length === 0) {
                        importSetStatus("{{ lang._('No usable settings found in the backup file; modem added with plugin defaults.') }}", 'warning');
                    }
                    fields.enabled = '1';
                    ajaxCall("/api/hilink/settings/setModem/" + uuid, {'modem': fields}, function() {
                        // Full page reload — most reliable way to refresh the grid
                        // and rebind all edit handlers after adding a modem
                        window.location.reload();
                    });
                };
                reader.readAsText(nvramFile);
            });
        });

        /**
         * First-use wizard
         * Shown once when the wizard has never been completed and no modems
         * are configured. Lets the user import the modem's current settings
         * (live via API or from a nvram.bak backup) instead of overwriting
         * them with plugin defaults.
         */
        function wizardMarkDone(callback) {
            ajaxCall("/api/hilink/settings/set", {'hilink': {'general': {'wizard_completed': '1'}}}, function() {
                if (callback !== undefined) {
                    callback();
                }
            });
        }

        function wizardSetStatus(message, level) {
            $("#wizard_status")
                .removeClass("alert-info alert-warning alert-danger")
                .addClass("alert-" + (level || "info"))
                .text(message)
                .show();
        }

        /**
         * Parse a HiLink nvram.bak backup: every line is base64 encoded,
         * the decoded stream contains NV items and embedded XML config
         * files. Only the dialup settings the plugin manages are extracted.
         */
        function parseNvramBackup(text) {
            var fields = {};
            text.split(/\r?\n/).forEach(function(line) {
                line = line.trim();
                if (line === '') {
                    return;
                }
                var decoded;
                try {
                    decoded = atob(line);
                } catch (e) {
                    return; // not base64, skip
                }
                var match;
                if ((match = decoded.match(/<roam_connect>([01])<\/roam_connect>/))) {
                    fields.roaming_enabled = match[1];
                }
                if ((match = decoded.match(/<max_idle_time>(\d+)<\/max_idle_time>/))) {
                    fields.max_idle_time = match[1];
                }
                if ((match = decoded.match(/<dataswitch>([01])<\/dataswitch>/))) {
                    fields.auto_connect = match[1];
                }
                if ((match = decoded.match(/<current_profile>(\d+)<\/current_profile>/))) {
                    fields.active_profile = match[1];
                }
            });
            return fields;
        }

        function wizardFinalize(uuid, fields, keepOpen) {
            fields.enabled = '1';
            ajaxCall("/api/hilink/settings/setModem/" + uuid, {'modem': fields}, function() {
                wizardMarkDone(function() {
                    ajaxCall("/api/hilink/service/reconfigure", {}, function() {
                        $("#grid-modems").bootgrid('reload');
                        updateServiceControlUI('hilink');
                        if (keepOpen) {
                            // leave the modal open so the warning stays readable
                            $("#wizard_finish").prop('disabled', true);
                            $("#wizard_skip").text("{{ lang._('Close') }}");
                        } else {
                            $("#HiLinkWizard").modal('hide');
                        }
                    });
                });
            });
        }

        $("input[name=wizard_mode]").change(function() {
            $("#wizard_nvram_group").toggle($("input[name=wizard_mode]:checked").val() === 'nvram');
        });

        $("#wizard_skip").click(function() {
            wizardMarkDone(function() {
                $("#HiLinkWizard").modal('hide');
            });
        });

        $("#wizard_finish").click(function() {
            var mode = $("input[name=wizard_mode]:checked").val();
            var nvramFile = $("#wizard_nvram_file")[0].files[0];
            if (mode === 'nvram' && nvramFile === undefined) {
                wizardSetStatus("{{ lang._('Please select a nvram.bak file first.') }}", 'warning');
                return;
            }
            // keep the modem disabled until its settings are final so the
            // service never pushes defaults onto the device
            var modem = {
                'name': $("#wizard_name").val(),
                'ip_address': $("#wizard_ip").val(),
                'username': $("#wizard_username").val(),
                'password': $("#wizard_password").val(),
                'enabled': '0'
            };
            ajaxCall("/api/hilink/settings/addModem/", {'modem': modem}, function(data) {
                if (!data || data.result !== 'saved') {
                    var messages = [];
                    if (data && data.validations) {
                        Object.keys(data.validations).forEach(function(key) {
                            messages.push(data.validations[key]);
                        });
                    }
                    wizardSetStatus(messages.join('; ') || "{{ lang._('Could not save the modem.') }}", 'danger');
                    return;
                }
                var uuid = data.uuid;
                if (mode === 'import') {
                    wizardSetStatus("{{ lang._('Reading current settings from the modem...') }}");
                    ajaxCall("/api/hilink/service/probe/" + uuid, {}, function(pdata) {
                        var fields = {};
                        if (pdata && pdata.status === 'ok' && pdata.settings) {
                            var s = pdata.settings;
                            if (s.network_mode !== undefined) {
                                fields.network_mode = s.network_mode;
                            }
                            if (s.roaming_enabled !== undefined) {
                                fields.roaming_enabled = s.roaming_enabled ? '1' : '0';
                            }
                            if (s.max_idle_time !== undefined) {
                                fields.max_idle_time = String(s.max_idle_time);
                            }
                            if (s.auto_connect !== undefined) {
                                fields.auto_connect = s.auto_connect ? '1' : '0';
                            }
                        } else {
                            var message = (pdata && pdata.message) ? pdata.message : "{{ lang._('modem not reachable') }}";
                            wizardSetStatus("{{ lang._('Import failed') }}" + " (" + message + "). " +
                                "{{ lang._('The modem was added with plugin defaults; its settings will be overwritten once it becomes reachable.') }}", 'warning');
                            wizardFinalize(uuid, fields, true);
                            return;
                        }
                        wizardFinalize(uuid, fields);
                    });
                } else if (mode === 'nvram') {
                    var reader = new FileReader();
                    reader.onload = function(ev) {
                        var fields = parseNvramBackup(ev.target.result);
                        if (Object.keys(fields).length === 0) {
                            wizardSetStatus("{{ lang._('No usable settings found in the backup file; continuing with plugin defaults.') }}", 'warning');
                            wizardFinalize(uuid, fields, true);
                            return;
                        }
                        wizardFinalize(uuid, fields);
                    };
                    reader.readAsText(nvramFile);
                } else {
                    wizardFinalize(uuid, {});
                }
            });
        });

        ajaxGet("/api/hilink/settings/get", {}, function(data, status) {
            if (status !== 'success' || data.hilink === undefined) {
                return;
            }
            if (data.hilink.general.wizard_completed === '1') {
                return;
            }
            var modems = data.hilink.modems && data.hilink.modems.modem ? data.hilink.modems.modem : {};
            if (Object.keys(modems).length > 0) {
                // existing installation: never show the wizard, just mark it done
                wizardMarkDone();
                return;
            }
            $("#HiLinkWizard").modal('show');
        });

        $("#saveAct").click(function() {
            $("#saveAct_progress").addClass("fa fa-spinner fa-pulse");
            saveFormToEndpoint("/api/hilink/settings/set", 'frm_GeneralSettings', function() {
                saveFormToEndpoint("/api/hilink/settings/set", 'frm_AlertSettings', function() {
                    ajaxCall("/api/hilink/service/reconfigure", {}, function(data, status) {
                        $("#saveAct_progress").removeClass("fa fa-spinner fa-pulse");
                        updateServiceControlUI('hilink');
                    });
                });
            });
        });

        updateServiceControlUI('hilink');
    });
</script>

<ul class="nav nav-tabs" data-tabs="tabs" id="maintabs">
    <li class="active"><a data-toggle="tab" href="#general">{{ lang._('General') }}</a></li>
    <li><a data-toggle="tab" href="#modems">{{ lang._('Modems') }}</a></li>
    <li><a data-toggle="tab" href="#alerts">{{ lang._('Alerts') }}</a></li>
</ul>

<div class="tab-content content-box">
    <div id="general" class="tab-pane fade in active">
        {{ partial("layout_partials/base_form",['fields':generalForm,'id':'frm_GeneralSettings']) }}
    </div>
    <div id="modems" class="tab-pane fade">
        <table id="grid-modems" class="table table-condensed table-hover table-striped table-responsive" data-editDialog="DialogModem" data-editAlert="ModemChangeMessage">
            <thead>
                <tr>
                    <th data-column-id="uuid" data-type="string" data-identifier="true" data-visible="false">{{ lang._('ID') }}</th>
                    <th data-column-id="enabled" data-width="6em" data-type="string" data-formatter="rowtoggle">{{ lang._('Enabled') }}</th>
                    <th data-column-id="name" data-type="string">{{ lang._('Name') }}</th>
                    <th data-column-id="ip_address" data-type="string">{{ lang._('IP Address') }}</th>
                    <th data-column-id="network_mode" data-type="string">{{ lang._('Network Mode') }}</th>
                    <th data-column-id="auto_connect" data-type="string" data-formatter="boolean">{{ lang._('Auto Connect') }}</th>
                    <th data-column-id="commands" data-width="7em" data-formatter="commands" data-sortable="false">{{ lang._('Commands') }}</th>
                </tr>
            </thead>
            <tbody></tbody>
            <tfoot>
                <tr>
                    <td></td>
                    <td>
                        <button data-action="add" type="button" class="btn btn-xs btn-primary"><span class="fa fa-plus"></span></button>
                        <button data-action="deleteSelected" type="button" class="btn btn-xs btn-default"><span class="fa fa-trash-o"></span></button>
                        <button type="button" id="btnImportBackup" class="btn btn-xs btn-default" title="{{ lang._('Import a modem from a nvram.bak backup file') }}"><span class="fa fa-upload"></span></button>
                    </td>
                </tr>
            </tfoot>
        </table>
        <div id="ModemChangeMessage" class="alert alert-info" style="display: none" role="alert">
            {{ lang._('After changing settings, please remember to apply them with the button below') }}
        </div>
    </div>
    <div id="alerts" class="tab-pane fade">
        {{ partial("layout_partials/base_form",['fields':alertForm,'id':'frm_AlertSettings']) }}
    </div>
</div>

<div class="content-box">
    <div class="col-md-12">
        <hr/>
        <button class="btn btn-primary" id="saveAct" type="button">
            <b>{{ lang._('Save & Apply') }}</b> <i id="saveAct_progress"></i>
        </button>
        <br/><br/>
    </div>
</div>

{{ partial("layout_partials/base_dialog",['fields':formDialogModem,'id':'DialogModem','label':lang._('Edit modem')]) }}

{# First-use wizard: import existing modem settings or start with defaults #}
<style>
#HiLinkWizard .modal-header { padding: 12px 20px; }
#HiLinkWizard .modal-body { padding: 20px; }
#HiLinkWizard .modal-footer { padding: 12px 20px; }
</style>
<div class="modal fade" id="HiLinkWizard" tabindex="-1" role="dialog" data-backdrop="static" data-keyboard="false" aria-labelledby="HiLinkWizardTitle">
    <div class="modal-dialog" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h4 class="modal-title" id="HiLinkWizardTitle">{{ lang._('Welcome to HiLink — first use setup') }}</h4>
            </div>
            <div class="modal-body">
                <p>{{ lang._('No modem is configured yet. Enter how to reach your HiLink modem and choose how to set it up.') }}</p>
                <div class="form-group">
                    <label for="wizard_name">{{ lang._('Name') }}</label>
                    <input type="text" class="form-control" id="wizard_name" value="HiLinkModem">
                </div>
                <div class="form-group">
                    <label for="wizard_ip">{{ lang._('IP address') }}</label>
                    <input type="text" class="form-control" id="wizard_ip" value="192.168.8.1">
                </div>
                <div class="form-group">
                    <label for="wizard_username">{{ lang._('Username') }}</label>
                    <input type="text" class="form-control" id="wizard_username" value="admin">
                </div>
                <div class="form-group">
                    <label for="wizard_password">{{ lang._('Password') }}</label>
                    <input type="password" class="form-control" id="wizard_password" value="" autocomplete="new-password">
                </div>
                <hr/>
                <div class="radio">
                    <label>
                        <input type="radio" name="wizard_mode" value="import" checked>
                        <b>{{ lang._('Import current settings from the modem') }}</b> ({{ lang._('recommended') }})<br/>
                        <small>{{ lang._('Reads network mode, roaming, idle timeout and auto-connect from the modem so nothing is overwritten.') }}</small>
                    </label>
                </div>
                <div class="radio">
                    <label>
                        <input type="radio" name="wizard_mode" value="nvram">
                        <b>{{ lang._('Import from a nvram.bak backup file') }}</b><br/>
                        <small>{{ lang._('Use a backup downloaded from the modem (http://modem-ip/nvram.bak) when the modem is currently not reachable.') }}</small>
                    </label>
                </div>
                <div class="form-group" id="wizard_nvram_group" style="display:none; margin-left: 20px;">
                    <input type="file" id="wizard_nvram_file">
                </div>
                <div class="radio">
                    <label>
                        <input type="radio" name="wizard_mode" value="defaults">
                        <b>{{ lang._('Start with plugin defaults') }}</b><br/>
                        <small>{{ lang._('The plugin defaults (roaming off, automatic network mode) will be applied to the modem.') }}</small>
                    </label>
                </div>
                <div id="wizard_status" class="alert alert-info" style="display:none" role="alert"></div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-default" id="wizard_skip">{{ lang._('Skip') }}</button>
                <button type="button" class="btn btn-primary" id="wizard_finish">{{ lang._('Set up modem') }}</button>
            </div>
        </div>
    </div>
</div>

{# Import-from-backup dialog: add a modem from a nvram.bak file #}
<style>
#ImportBackup .modal-header { padding: 12px 20px; }
#ImportBackup .modal-body { padding: 20px; }
#ImportBackup .modal-footer { padding: 12px 20px; }
</style>
<div class="modal fade" id="ImportBackup" tabindex="-1" role="dialog" aria-labelledby="ImportBackupTitle">
    <div class="modal-dialog" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <h4 class="modal-title" id="ImportBackupTitle">{{ lang._('Import modem from backup') }}</h4>
            </div>
            <div class="modal-body">
                <p>{{ lang._('Enter the modem connection details and select a nvram.bak backup file. The modem will be created with the settings read from the backup.') }}</p>
                <div class="form-group">
                    <label for="import_name">{{ lang._('Name') }}</label>
                    <input type="text" class="form-control" id="import_name" value="HiLinkModem">
                </div>
                <div class="form-group">
                    <label for="import_ip">{{ lang._('IP address') }}</label>
                    <input type="text" class="form-control" id="import_ip" value="192.168.8.1">
                </div>
                <div class="form-group">
                    <label for="import_username">{{ lang._('Username') }}</label>
                    <input type="text" class="form-control" id="import_username" value="admin">
                </div>
                <div class="form-group">
                    <label for="import_password">{{ lang._('Password') }}</label>
                    <input type="password" class="form-control" id="import_password" value="" autocomplete="new-password">
                </div>
                <div class="form-group">
                    <label for="import_nvram_file">{{ lang._('nvram.bak backup file') }}</label>
                    <input type="file" id="import_nvram_file">
                </div>
                <div id="import_status" class="alert alert-info" style="display:none" role="alert"></div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-default" data-dismiss="modal">{{ lang._('Cancel') }}</button>
                <button type="button" class="btn btn-primary" id="import_finish">{{ lang._('Import') }}</button>
            </div>
        </div>
    </div>
</div>

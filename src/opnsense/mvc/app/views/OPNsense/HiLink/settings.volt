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

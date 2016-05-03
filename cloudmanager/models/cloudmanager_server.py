# -*- coding: utf-8 -*-
from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
import requests
from string import Template
import json
import time
from cloudmanager.models.constants import constants


class CloudmanagerServer(models.Model):
    _name = 'cloudmanager.server'
    _description = 'The server instance'

    name = fields.Char(
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="Provider name of the instance/droplet or VM server",
    )
    server_fqdn = fields.Char(
        string="Server FQDN",
        required=True,
        help="FQDN DNS name of the instance/droplet or VM server",
    )
    disk_size = fields.Char(
        required=True,
        help="Disk size, usually related to fcMachineType, also may include "
        "disk type like SSD. For informational purposes only.",
    )
    ram_size = fields.Char(
        required=True,
        help="Ram size, usually related to machine_type_id for informational "
        "purposes only.",
    )
    time_zone = fields.Char(
        required=True,
        help="Linux time zone name",
        default='EST5EDT',
    )
    notes = fields.Text(
        required=True,
        help="Freeform details regarding this server",
    )
    provider_id = fields.Many2one(
        'cloudmanager.provider',
        required=True,
        string="Provider",
        help="The provider this server is using",
        default=constants.GOOGLE_COMPUTE_ENGINE
    )
    machine_type_id = fields.Many2one(
        'cloudmanager.machinetype',
        required=True,
        string="Machine Type",
        help="The machine type this server is using",
    )
    image_id = fields.Many2one(
        'cloudmanager.image',
        required=True,
        string="Image",
        help="The OS image this server is using",
    )
    zone_id = fields.Many2one(
        'cloudmanager.zone',
        required=True,
        string="Zone",
        help="The zone or geographical region this server is assigned to",
    )
    server_status_id = fields.Many2one(
        'cloudmanager.serverstatus',
        required=True,
        string="Server Status",
        help="The status of the server",
        default=constants.INITIAL_SETUP
    )
    providerID = fields.Char(
        string="ProviderID",
        readonly=True,
        help="ID assigned on VM creation/deploy by some public cloud providers",
    )
    ipv4 = fields.Char(
        string="IPv4",
        readonly=True,
        help="Cloud provider assigned public ipv4 number",
    )
    ssh_public_key = fields.Char(
        readonly=True,
        help="Optional public ssh key for use in create template",
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('deployedActive', 'Deployed Active'),
        ('deployedStopped', 'Deployed Stopped'),
    ],
        string='State',
        required=True,
        default='draft',
    )
    _sql_constraints = [
        ('server_fqdn_unique', 'UNIQUE(server_fqdn)',
            'Server FQDN must be unique'),
        ('name', 'UNIQUE(name)', 'name must be unique'),
    ]


    ##
    # check_machine_type
    #   force refresh for UX UI check assignment
    @api.one
    @api.constrains('machine_type_id', 'provider_id')
    def check_machine_type(self):
        if self.machine_type_id.provider_id != self.provider_id:
            raise ValidationError(_(
                'Machine Type Provider must be of selected server provider'))
        if self.image_id.provider_id != self.provider_id:
            raise ValidationError(_(
                'Image Provider must be of selected server provider'))
        if self.zone_id.provider_id != self.provider_id:
            raise ValidationError(_(
                'Image Provider must be of selected server provider'))


    ##
    # onchange_provider
    #   force refresh for UX UI
    @api.onchange('provider_id')
    def onchange_provider(self):
        self.machine_type_id = False
        self.image_id = False
        self.zone_id = False


    ##
    # to_draft
    #   change to draft as long as server is not deployed
    @api.multi
    def to_draft(self):
        if self.server_status_id.id != constants.INITIAL_SETUP:
            raise ValidationError(_('VM must be at Initial Setup VM state'))
        self.write({'state': 'draft'})


    ##
    # validate_server_fields
    #   common basic field sanity checks
    @api.multi
    def validate_server_fields(self):
        """
        validate_server_fields
            basic server field validation
        """
        if not self.name:
            raise ValidationError(_('VM must have a name'))
        if not self.notes:
            raise ValidationError(_('VM must have notes'))
        if not self.provider_id:
            raise ValidationError(_('VM must have provider'))
        if not self.machine_type_id:
            raise ValidationError(_('VM must have machine type'))
        if not self.image_id:
            raise ValidationError(_('VM must have an OS image '))
        if not self.zone_id:
            raise ValidationError(_('VM must have a provider zone'))
        return True


    ##
    # to_ready
    #   checks and if possible changes state to ready
    @api.multi
    def to_ready(self):

        self.validate_server_fields()

        if self.state != 'draft':
            raise ValidationError(_(
                'Can not change to ready VMs that are not in the workflow '
                'draft state'))
        if not self.provider_id.api_password:
            raise ValidationError(_(
                'VM provider must have api_password defined'))
        if not self.provider_id.create_template:
            raise ValidationError(_(
                'VM provider must have create_template defined'))
        if not self.provider_id.api_url:
            raise ValidationError(_(
                'VM provider must have an API URL defined'))
        if self.server_status_id.id != constants.INITIAL_SETUP:
            raise ValidationError(_('VM must be at Initial Setup VM state'))
        self.write({'state': 'ready'})
        return True


    ##
    # GoogleComputeEngine_deployvm
    #   Uses GCE v1 API to deploy a VM
    @api.multi
    def GoogleComputeEngine_deployvm(self):
        return True


    ##
    # DigitalOcean_deployvm
    #   Uses Digitial Ocean v2 API to deploy a VM
    @api.multi
    def DigitalOcean_deployvm(self):
        Authorization = "Bearer " + str(self.provider_id.api_password)
        h = {
            "Content-Type": "application/json", "Authorization": Authorization
        }
        t = Template(self.provider_id.create_template)
        d = t.safe_substitute(
            name=self.server_fqdn,
            size=self.machine_type_id.slug,
            image=self.image_id.slug,
            zone=self.zone_id.slug,
        )
        r = requests.post(self.provider_id.api_url, headers=h, data=d)
        if r.status_code != 202 and r.status_code != 200:
            raise ValidationError(_("Error: " + str(r.status_code) + '\n' +
                    r.text + '\n' + str(h) + '\n' + str(d) +
                     '\n' + self.provider_id.api_url))
        theJSON = json.loads(r.text)
        vmid = False
        if "id" in theJSON["droplet"]:
            vmid = theJSON["droplet"]["id"]
        if not vmid:
            raise ValidationError(_("Error: No droplet ID returned"))

        # if valid ID we can place server in waiting for deploy server status
        self.write({
            'state': 'deployedActive',
            'server_status_id': constants.WAITING_FOR_DEPLOYMENT,
            'providerID': vmid
        })
        # end request VM creation
        ##

        # THIS WILL BE CHANGED to use the Odoo automation scheduling table
        # We will create another method updateWaitingForDeploy()
        # It will be called via this cron like jobqueue table.
        # On success it will remove itself.
        time.sleep(20)
        vmidURL = self.provider_id.api_url+ str('/') + str(vmid)
        r = requests.get(vmidURL, headers=h)
        if r.status_code != 200:
            raise ValidationError(_(
                "Error getting VM data: %s%s") % (r.status_code, r.text))
        theJSON = json.loads(r.text)
        if (
                "networks" in theJSON["droplet"] and
                "v4" in theJSON["droplet"]["networks"]):
            for i in theJSON["droplet"]["networks"]["v4"]:
                cipv4 = i["ip_address"]
                break
        if not cipv4:
            raise ValidationError(_("Error no ipv4: %s") % theJSON["droplet"]["networks"])
        self.write({
            'server_status_id': constants.ACTIVE,
            'ipv4': cipv4})
        return True


    ##
    # deployvm
    #   front end for future plugin architecture for deploy VM for 
    #   any cloud provider API
    @api.multi
    def deployvm(self):
        ##
        # Start Validate
        self.validate_server_fields()

        if self.state != 'ready':
            raise ValidationError(_(
                'Can not deploy VMs that are not in workflow ready state'))
        if not self.provider_id.api_password:
            raise ValidationError(_(
                'VM provider must have api_passwd defined'))
        if not self.provider_id.create_template:
            raise ValidationError(_(
                'VM provider must have create_template defined'))
        if not self.provider_id.api_url:
            raise ValidationError(_(
                'VM provider must have an API URL defined'))
        if self.server_status_id.id != constants.INITIAL_SETUP:
            raise ValidationError(_('VM must be at Initial Setup VM status'))
        # end Validate
        ##

        ##
        # request VM creation
        # notes

        if self.provider_id.id == constants.GOOGLE_COMPUTE_ENGINE:
            self.GoogleComputeEngine_deployvm()
        elif self.provider_id.id == constants.DIGITAL_OCEAN:
            self.DigitalOcean_deployvm()

        ##
        # start DNS API
        # post DNS A zone creation request
        # end DNS API
        ##
        return True


    ##
    # GoogleComputeEngine_destroyvm
    #   uses GCE v1 API to remove/delete/destroy a VM
    @api.multi
    def GoogleComputeEngine_destroyvm(self):
        return True


    ##
    # DigitalOcean_destroyvm
    #   uses Digital Ocean v2 API to remove/delete/destroy a VM
    @api.multi
    def DigitalOcean_destroyvm(self):
        Authorization = "Bearer " + str(self.provider_id.api_password)
        h = {"Content-Type": "application/json","Authorization": Authorization}
        vmidURL=self.provider_id.api_url+str('/')+self.providerID
        r = requests.get(vmidURL,headers=h)
        if r.status_code != 200:
            raise ValidationError("Error getting VM data: "+str(r.status_code)+r.text)
        theJSON=json.loads(r.text)
        if "status" in theJSON["droplet"]:
            if theJSON["droplet"]["status"] != "active" and theJSON["droplet"]["status"] != "off":
                raise ValidationError("Error unexpected provider server status: "+theJSON["droplet"]["status"])
        r = requests.delete(vmidURL,headers=h)
        if r.status_code != 204:
            raise ValidationError("Error destroyvm: "+str(r.status_code)+r.text)
        # initial setup server status. ready state. remove IP and ID.
        self.write({'server_status_id':constants.INITIAL_SETUP, 'providerID': '', 'IPv4': '', 'state': 'ready'})
        return True


    ##
    # GoogleComputeEngine_stopvm
    #   uses GCE v1 API to stop a VM
    @api.multi
    def GoogleComputeEngine_stopvm(self):
        return True


    ##
    # DigitalOcean_stopvm
    #   uses Digital Ocean v2 API to stop a VM
    @api.multi
    def DigitalOcean_stopvm(self):
        Authorization = "Bearer " + str(self.provider_id.api_password)
        h = {"Content-Type": "application/json","Authorization": Authorization}
        vmidURL=self.provider_id.api_url+str('/')+self.providerID
        r = requests.get(vmidURL,headers=h)
        if r.status_code != 200:
            raise ValidationError("Error getting VM data: "+str(r.status_code)+r.text)
        theJSON=json.loads(r.text)
        if "status" in theJSON["droplet"]:
            if theJSON["droplet"]["status"] != "active":
                if theJSON["droplet"]["status"] == "off":
                    self.write({'server_status_id':constants.STOPPED, 'state': 'deployedStopped'})
                    return True
                else:
                    raise ValidationError("Error unexpected provider server status: "+theJSON["droplet"]["status"])
        vmidURL=self.provider_id.api_url+str('/')+self.providerID+str('/actions')
        r = requests.post(vmidURL,headers=h,data=self.provider_id.stop_template)
        if r.status_code != 201:
            raise ValidationError("Error stopvm: "+str(r.status_code)+r.text)
        # waiting for stop server status. deplyed stopped state.
        self.write({'server_status_id':constants.WAITING_FOR_STOP, 'state': 'deployedStopped'})
        # wait and check for status change, this is only for development testing
        time.sleep(30)
        vmidURL=self.provider_id.api_url+str('/')+self.providerID
        r = requests.get(vmidURL,headers=h)
        if r.status_code != 200:
            raise ValidationError("Error getting VM data: "+str(r.status_code)+r.text)
        theJSON=json.loads(r.text)
        if "status" in theJSON["droplet"]:
            if theJSON["droplet"]["status"] != "off":
                raise ValidationError("Error unexpected provider server status: "+theJSON["droplet"]["status"])
        # stopped
        self.write({'server_status_id':constants.STOPPED})
        return True


    @api.multi
    def GoogleComputeEngine_startvm(self):
        return True


    ##
    # DigitalOcean_startvm
    #   uses Digital Ocean 2.0 API to start a VM
    @api.multi
    def DigitalOcean_startvm(self):
        Authorization = "Bearer " + str(self.provider_id.api_password)
        h = {"Content-Type": "application/json","Authorization": Authorization}
        vmidURL=self.provider_id.api_url+str('/')+self.providerID
        r = requests.get(vmidURL,headers=h)
        if r.status_code != 200:
            raise ValidationError("Error getting VM data: "+str(r.status_code)+r.text)
        theJSON=json.loads(r.text)
        if "status" in theJSON["droplet"]:
            if theJSON["droplet"]["status"] != "off":
                raise ValidationError("Error unexpected provider server status: "+theJSON["droplet"]["status"])
        vmidURL=self.provider_id.api_url+str('/')+self.providerID+str('/actions')
        r = requests.post(vmidURL,headers=h,data=self.provider_id.start_template)
        if r.status_code != 201:
            raise ValidationError("Error startvm: "+str(r.status_code)+r.text)
        # waiting for start server/reboot status. deployed active state.
        self.write({'server_status_id':constants.WAITING_FOR_START, 'state': 'deployedActive'})
        # wait and check for status change, this is only for development testing
        time.sleep(30)
        vmidURL=self.provider_id.api_url+str('/')+self.providerID
        r = requests.get(vmidURL,headers=h)
        if r.status_code != 200:
            raise ValidationError("Error getting VM data: "+str(r.status_code)+r.text)
        theJSON=json.loads(r.text)
        if "status" in theJSON["droplet"]:
            if theJSON["droplet"]["status"] != "active":
                raise ValidationError("Error unexpected provider server status: "+theJSON["droplet"]["status"])
        # active
        self.write({'server_status_id': '2'})
        return True


    ##
    # destroyvm
    #   uses cloud provider API to destroy a VM
    @api.multi
    def destroyvm(self):
        ##
        # Start Validate
        if self.state != 'deployedActive' and self.state != 'deployedStopped':
            raise ValidationError('Can not destroy VMs that are not in  a workflow deployed state')
        if not self.provider_id.api_password:
            raise ValidationError('VM provider must have api_password defined')
        if not self.provider_id.api_url:
            raise ValidationError('VM provider must have a valid API URL defined')
        if self.server_status_id.id == constants.INITIAL_SETUP:
            raise ValidationError('VM must not be at Initial Setup VM status')
        # end Validate
        ##

        ##
        # request VM destroy
        if self.provider_id.id == constants.GOOGLE_COMPUTE_ENGINE:
            self.GoogleComputeEngine_destroyvm()
        elif self.provider_id.id == constants.DIGITAL_OCEAN:
            self.DigitalOcean_destroyvm()
        return True

    ##
    # stopvm
    #   uses cloud provider API to stop a VM
    @api.multi
    def stopvm(self):
        ##
        # Start Validate
        if self.state != 'deployedActive':
            raise ValidationError('Can not stop VMs that are not in a workflow active deployed state')
        if not self.provider_id.api_password:
            raise ValidationError('VM provider must have api_password defined')
        if not self.provider_id.stop_template:
            raise ValidationError('VM provider must have valid stop_template')
        if not self.provider_id.api_url:
            raise ValidationError('VM provider must have a valid API URL defined')
        if self.server_status_id.id == constants.INITIAL_SETUP:
            raise ValidationError('VM must not be at Initial Setup VM status')
        # end Validate
        ##

        ##
        # request VM stop
        if self.provider_id.id == constants.GOOGLE_COMPUTE_ENGINE:
            self.GoogleComputeEngine_stopvm()
        elif self.provider_id.id == constants.DIGITAL_OCEAN:
            self.DigitalOcean_stopvm()
        return True


    ##
    # startvm
    #   uses cloud provider API to start a VM
    @api.multi
    def startvm(self):
        ##
        # Start Validate
        if self.state != 'deployedStopped':
            raise ValidationError('Can not start VMs that are not in a workflow stopped deployed state')
        if not self.provider_id.api_password:
            raise ValidationError('VM provider must have api_password defined')
        if not self.provider_id.start_template:
            raise ValidationError('VM provider must have valid start_template')
        if not self.provider_id.api_url:
            raise ValidationError('VM provider must have a valid API URL defined')
        if self.server_status_id.id == constants.INITIAL_SETUP:
            raise ValidationError('VM must not be at Initial Setup VM status')
        # end Validate
        ##

        ##
        # request VM start
        if self.provider_id.id == constants.GOOGLE_COMPUTE_ENGINE:
            self.GoogleComputeEngine_startvm()
        elif self.provider_id.id == constants.DIGITAL_OCEAN:
            self.DigitalOcean_startvm()
        return True

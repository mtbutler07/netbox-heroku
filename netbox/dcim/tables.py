import django_tables2 as tables
from django_tables2.utils import Accessor

from tenancy.tables import COL_TENANT
from utilities.tables import BaseTable, BooleanColumn, ColorColumn, ToggleColumn
from .models import (
    Cable, ConsolePort, ConsolePortTemplate, ConsoleServerPort, ConsoleServerPortTemplate, Device, DeviceBay,
    DeviceBayTemplate, DeviceRole, DeviceType, FrontPort, FrontPortTemplate, Interface, InterfaceTemplate,
    InventoryItem, Manufacturer, Platform, PowerFeed, PowerOutlet, PowerOutletTemplate, PowerPanel, PowerPort,
    PowerPortTemplate, Rack, RackGroup, RackReservation, RackRole, RearPort, RearPortTemplate, Region, Site,
    VirtualChassis,
)

REGION_LINK = """
{% if record.get_children %}
    <span style="padding-left: {{ record.get_ancestors|length }}0px "><i class="fa fa-caret-right"></i>
{% else %}
    <span style="padding-left: {{ record.get_ancestors|length }}9px">
{% endif %}
    <a href="{% url 'dcim:site_list' %}?region={{ record.slug }}">{{ record.name }}</a>
</span>
"""

SITE_REGION_LINK = """
{% if record.region %}
    <a href="{% url 'dcim:site_list' %}?region={{ record.region.slug }}">{{ record.region }}</a>
{% else %}
    &mdash;
{% endif %}
"""

COLOR_LABEL = """
{% load helpers %}
<label class="label" style="color: {{ record.color|fgcolor }}; background-color: #{{ record.color }}">{{ record }}</label>
"""

DEVICE_LINK = """
<a href="{% url 'dcim:device' pk=record.pk %}">
    {{ record.name|default:'<span class="label label-info">Unnamed device</span>' }}
</a>
"""

REGION_ACTIONS = """
<a href="{% url 'dcim:region_changelog' pk=record.pk %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
{% if perms.dcim.change_region %}
    <a href="{% url 'dcim:region_edit' pk=record.pk %}?return_url={{ request.path }}" class="btn btn-xs btn-warning"><i class="glyphicon glyphicon-pencil" aria-hidden="true"></i></a>
{% endif %}
"""

RACKGROUP_ACTIONS = """
<a href="{% url 'dcim:rackgroup_changelog' pk=record.pk %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
<a href="{% url 'dcim:rack_elevation_list' %}?site={{ record.site.slug }}&group_id={{ record.pk }}" class="btn btn-xs btn-primary" title="View elevations">
    <i class="fa fa-eye"></i>
</a>
{% if perms.dcim.change_rackgroup %}
    <a href="{% url 'dcim:rackgroup_edit' pk=record.pk %}?return_url={{ request.path }}" class="btn btn-xs btn-warning" title="Edit">
        <i class="glyphicon glyphicon-pencil"></i>
    </a>
{% endif %}
"""

RACKROLE_ACTIONS = """
<a href="{% url 'dcim:rackrole_changelog' pk=record.pk %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
{% if perms.dcim.change_rackrole %}
    <a href="{% url 'dcim:rackrole_edit' pk=record.pk %}?return_url={{ request.path }}" class="btn btn-xs btn-warning"><i class="glyphicon glyphicon-pencil" aria-hidden="true"></i></a>
{% endif %}
"""

RACK_ROLE = """
{% if record.role %}
    <label class="label" style="background-color: #{{ record.role.color }}">{{ value }}</label>
{% else %}
    &mdash;
{% endif %}
"""

RACK_DEVICE_COUNT = """
<a href="{% url 'dcim:device_list' %}?rack_id={{ record.pk }}">{{ value }}</a>
"""

RACKRESERVATION_ACTIONS = """
<a href="{% url 'dcim:rackreservation_changelog' pk=record.pk %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
{% if perms.dcim.change_rackreservation %}
    <a href="{% url 'dcim:rackreservation_edit' pk=record.pk %}?return_url={{ request.path }}" class="btn btn-xs btn-warning"><i class="glyphicon glyphicon-pencil" aria-hidden="true"></i></a>
{% endif %}
"""

MANUFACTURER_ACTIONS = """
<a href="{% url 'dcim:manufacturer_changelog' slug=record.slug %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
{% if perms.dcim.change_manufacturer %}
    <a href="{% url 'dcim:manufacturer_edit' slug=record.slug %}?return_url={{ request.path }}" class="btn btn-xs btn-warning"><i class="glyphicon glyphicon-pencil" aria-hidden="true"></i></a>
{% endif %}
"""

DEVICEROLE_ACTIONS = """
<a href="{% url 'dcim:devicerole_changelog' slug=record.slug %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
{% if perms.dcim.change_devicerole %}
    <a href="{% url 'dcim:devicerole_edit' slug=record.slug %}?return_url={{ request.path }}" class="btn btn-xs btn-warning"><i class="glyphicon glyphicon-pencil" aria-hidden="true"></i></a>
{% endif %}
"""

DEVICEROLE_DEVICE_COUNT = """
<a href="{% url 'dcim:device_list' %}?role={{ record.slug }}">{{ value }}</a>
"""

DEVICEROLE_VM_COUNT = """
<a href="{% url 'virtualization:virtualmachine_list' %}?role={{ record.slug }}">{{ value }}</a>
"""

PLATFORM_DEVICE_COUNT = """
<a href="{% url 'dcim:device_list' %}?platform={{ record.slug }}">{{ value }}</a>
"""

PLATFORM_VM_COUNT = """
<a href="{% url 'virtualization:virtualmachine_list' %}?platform={{ record.slug }}">{{ value }}</a>
"""

PLATFORM_ACTIONS = """
<a href="{% url 'dcim:platform_changelog' slug=record.slug %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
{% if perms.dcim.change_platform %}
    <a href="{% url 'dcim:platform_edit' slug=record.slug %}?return_url={{ request.path }}" class="btn btn-xs btn-warning"><i class="glyphicon glyphicon-pencil" aria-hidden="true"></i></a>
{% endif %}
"""

DEVICE_ROLE = """
{% load helpers %}
<label class="label" style="color: {{ record.device_role.color|fgcolor }}; background-color: #{{ record.device_role.color }}">{{ value }}</label>
"""

STATUS_LABEL = """
<span class="label label-{{ record.get_status_class }}">{{ record.get_status_display }}</span>
"""

TYPE_LABEL = """
<span class="label label-{{ record.get_type_class }}">{{ record.get_type_display }}</span>
"""

DEVICE_PRIMARY_IP = """
{{ record.primary_ip6.address.ip|default:"" }}
{% if record.primary_ip6 and record.primary_ip4 %}<br />{% endif %}
{{ record.primary_ip4.address.ip|default:"" }}
"""

SUBDEVICE_ROLE_TEMPLATE = """
{% if record.subdevice_role == True %}Parent{% elif record.subdevice_role == False %}Child{% else %}&mdash;{% endif %}
"""

DEVICETYPE_INSTANCES_TEMPLATE = """
<a href="{% url 'dcim:device_list' %}?manufacturer_id={{ record.manufacturer_id }}&device_type_id={{ record.pk }}">{{ record.instance_count }}</a>
"""

UTILIZATION_GRAPH = """
{% load helpers %}
{% utilization_graph value %}
"""

VIRTUALCHASSIS_ACTIONS = """
<a href="{% url 'dcim:virtualchassis_changelog' pk=record.pk %}" class="btn btn-default btn-xs" title="Changelog">
    <i class="fa fa-history"></i>
</a>
{% if perms.dcim.change_virtualchassis %}
    <a href="{% url 'dcim:virtualchassis_edit' pk=record.pk %}?return_url={{ request.path }}" class="btn btn-xs btn-warning"><i class="glyphicon glyphicon-pencil" aria-hidden="true"></i></a>
{% endif %}
"""

CABLE_TERMINATION_PARENT = """
{% if value.device %}
    <a href="{{ value.device.get_absolute_url }}">{{ value.device }}</a>
{% else %}
    <a href="{{ value.circuit.get_absolute_url }}">{{ value.circuit }}</a>
{% endif %}
"""

CABLE_LENGTH = """
{% if record.length %}{{ record.length }} {{ record.get_length_unit_display }}{% else %}&mdash;{% endif %}
"""

POWERPANEL_POWERFEED_COUNT = """
<a href="{% url 'dcim:powerfeed_list' %}?power_panel_id={{ record.pk }}">{{ value }}</a>
"""


#
# Regions
#

class RegionTable(BaseTable):
    pk = ToggleColumn()
    name = tables.TemplateColumn(template_code=REGION_LINK, orderable=False)
    site_count = tables.Column(verbose_name='Sites')
    slug = tables.Column(verbose_name='Slug')
    actions = tables.TemplateColumn(
        template_code=REGION_ACTIONS,
        attrs={'td': {'class': 'text-right noprint'}},
        verbose_name=''
    )

    class Meta(BaseTable.Meta):
        model = Region
        fields = ('pk', 'name', 'site_count', 'slug', 'actions')


#
# Sites
#

class SiteTable(BaseTable):
    pk = ToggleColumn()
    name = tables.LinkColumn(order_by=('_nat1', '_nat2', '_nat3'))
    status = tables.TemplateColumn(template_code=STATUS_LABEL, verbose_name='Status')
    region = tables.TemplateColumn(template_code=SITE_REGION_LINK)
    tenant = tables.TemplateColumn(template_code=COL_TENANT)

    class Meta(BaseTable.Meta):
        model = Site
        fields = ('pk', 'name', 'status', 'facility', 'region', 'tenant', 'asn', 'description')


#
# Rack groups
#

class RackGroupTable(BaseTable):
    pk = ToggleColumn()
    name = tables.LinkColumn()
    site = tables.LinkColumn(
        viewname='dcim:site',
        args=[Accessor('site.slug')],
        verbose_name='Site'
    )
    rack_count = tables.Column(
        verbose_name='Racks'
    )
    slug = tables.Column()
    actions = tables.TemplateColumn(
        template_code=RACKGROUP_ACTIONS,
        attrs={'td': {'class': 'text-right noprint'}},
        verbose_name=''
    )

    class Meta(BaseTable.Meta):
        model = RackGroup
        fields = ('pk', 'name', 'site', 'rack_count', 'slug', 'actions')


#
# Rack roles
#

class RackRoleTable(BaseTable):
    pk = ToggleColumn()
    name = tables.LinkColumn(verbose_name='Name')
    rack_count = tables.Column(verbose_name='Racks')
    color = tables.TemplateColumn(COLOR_LABEL, verbose_name='Color')
    slug = tables.Column(verbose_name='Slug')
    actions = tables.TemplateColumn(template_code=RACKROLE_ACTIONS, attrs={'td': {'class': 'text-right noprint'}},
                                    verbose_name='')

    class Meta(BaseTable.Meta):
        model = RackRole
        fields = ('pk', 'name', 'rack_count', 'color', 'slug', 'actions')


#
# Racks
#

class RackTable(BaseTable):
    pk = ToggleColumn()
    name = tables.LinkColumn(order_by=('_nat1', '_nat2', '_nat3'))
    site = tables.LinkColumn('dcim:site', args=[Accessor('site.slug')])
    group = tables.Column(accessor=Accessor('group.name'), verbose_name='Group')
    tenant = tables.TemplateColumn(template_code=COL_TENANT)
    status = tables.TemplateColumn(STATUS_LABEL)
    role = tables.TemplateColumn(RACK_ROLE)
    u_height = tables.TemplateColumn("{{ record.u_height }}U", verbose_name='Height')

    class Meta(BaseTable.Meta):
        model = Rack
        fields = ('pk', 'name', 'site', 'group', 'status', 'facility_id', 'tenant', 'role', 'u_height')


class RackDetailTable(RackTable):
    device_count = tables.TemplateColumn(
        template_code=RACK_DEVICE_COUNT,
        verbose_name='Devices'
    )
    get_utilization = tables.TemplateColumn(
        template_code=UTILIZATION_GRAPH,
        orderable=False,
        verbose_name='Space'
    )
    get_power_utilization = tables.TemplateColumn(
        template_code=UTILIZATION_GRAPH,
        orderable=False,
        verbose_name='Power'
    )

    class Meta(RackTable.Meta):
        fields = (
            'pk', 'name', 'site', 'group', 'status', 'facility_id', 'tenant', 'role', 'u_height', 'device_count',
            'get_utilization', 'get_power_utilization',
        )


#
# Rack reservations
#

class RackReservationTable(BaseTable):
    pk = ToggleColumn()
    site = tables.LinkColumn(
        viewname='dcim:site',
        accessor=Accessor('rack.site'),
        args=[Accessor('rack.site.slug')],
    )
    tenant = tables.TemplateColumn(template_code=COL_TENANT)
    rack = tables.LinkColumn('dcim:rack', args=[Accessor('rack.pk')])
    unit_list = tables.Column(orderable=False, verbose_name='Units')
    actions = tables.TemplateColumn(
        template_code=RACKRESERVATION_ACTIONS, attrs={'td': {'class': 'text-right noprint'}}, verbose_name=''
    )

    class Meta(BaseTable.Meta):
        model = RackReservation
        fields = ('pk', 'site', 'rack', 'unit_list', 'user', 'created', 'tenant', 'description', 'actions')


#
# Manufacturers
#

class ManufacturerTable(BaseTable):
    pk = ToggleColumn()
    name = tables.LinkColumn()
    devicetype_count = tables.Column(
        verbose_name='Device Types'
    )
    inventoryitem_count = tables.Column(
        verbose_name='Inventory Items'
    )
    platform_count = tables.Column(
        verbose_name='Platforms'
    )
    slug = tables.Column()
    actions = tables.TemplateColumn(
        template_code=MANUFACTURER_ACTIONS,
        attrs={'td': {'class': 'text-right noprint'}},
        verbose_name=''
    )

    class Meta(BaseTable.Meta):
        model = Manufacturer
        fields = ('pk', 'name', 'devicetype_count', 'inventoryitem_count', 'platform_count', 'slug', 'actions')


#
# Device types
#

class DeviceTypeTable(BaseTable):
    pk = ToggleColumn()
    model = tables.LinkColumn(
        viewname='dcim:devicetype',
        args=[Accessor('pk')],
        verbose_name='Device Type'
    )
    is_full_depth = BooleanColumn(verbose_name='Full Depth')
    subdevice_role = tables.TemplateColumn(
        template_code=SUBDEVICE_ROLE_TEMPLATE,
        verbose_name='Subdevice Role'
    )
    instance_count = tables.TemplateColumn(
        template_code=DEVICETYPE_INSTANCES_TEMPLATE,
        verbose_name='Instances'
    )

    class Meta(BaseTable.Meta):
        model = DeviceType
        fields = (
            'pk', 'model', 'manufacturer', 'part_number', 'u_height', 'is_full_depth', 'subdevice_role',
            'instance_count',
        )


#
# Device type components
#

class ConsolePortTemplateTable(BaseTable):
    pk = ToggleColumn()

    class Meta(BaseTable.Meta):
        model = ConsolePortTemplate
        fields = ('pk', 'name')
        empty_text = "None"


class ConsoleServerPortTemplateTable(BaseTable):
    pk = ToggleColumn()

    class Meta(BaseTable.Meta):
        model = ConsoleServerPortTemplate
        fields = ('pk', 'name')
        empty_text = "None"


class PowerPortTemplateTable(BaseTable):
    pk = ToggleColumn()

    class Meta(BaseTable.Meta):
        model = PowerPortTemplate
        fields = ('pk', 'name', 'maximum_draw', 'allocated_draw')
        empty_text = "None"


class PowerOutletTemplateTable(BaseTable):
    pk = ToggleColumn()

    class Meta(BaseTable.Meta):
        model = PowerOutletTemplate
        fields = ('pk', 'name', 'power_port', 'feed_leg')
        empty_text = "None"


class InterfaceTemplateTable(BaseTable):
    pk = ToggleColumn()
    mgmt_only = tables.TemplateColumn("{% if value %}OOB Management{% endif %}")

    class Meta(BaseTable.Meta):
        model = InterfaceTemplate
        fields = ('pk', 'name', 'mgmt_only', 'type')
        empty_text = "None"


class FrontPortTemplateTable(BaseTable):
    pk = ToggleColumn()

    class Meta(BaseTable.Meta):
        model = FrontPortTemplate
        fields = ('pk', 'name', 'type', 'rear_port', 'rear_port_position')
        empty_text = "None"


class RearPortTemplateTable(BaseTable):
    pk = ToggleColumn()

    class Meta(BaseTable.Meta):
        model = RearPortTemplate
        fields = ('pk', 'name', 'type', 'positions')
        empty_text = "None"


class DeviceBayTemplateTable(BaseTable):
    pk = ToggleColumn()

    class Meta(BaseTable.Meta):
        model = DeviceBayTemplate
        fields = ('pk', 'name')
        empty_text = "None"


#
# Device roles
#

class DeviceRoleTable(BaseTable):
    pk = ToggleColumn()
    device_count = tables.TemplateColumn(
        template_code=DEVICEROLE_DEVICE_COUNT,
        accessor=Accessor('devices.count'),
        orderable=False,
        verbose_name='Devices'
    )
    vm_count = tables.TemplateColumn(
        template_code=DEVICEROLE_VM_COUNT,
        accessor=Accessor('virtual_machines.count'),
        orderable=False,
        verbose_name='VMs'
    )
    color = tables.TemplateColumn(COLOR_LABEL, verbose_name='Label')
    slug = tables.Column(verbose_name='Slug')
    actions = tables.TemplateColumn(
        template_code=DEVICEROLE_ACTIONS,
        attrs={'td': {'class': 'text-right noprint'}},
        verbose_name=''
    )

    class Meta(BaseTable.Meta):
        model = DeviceRole
        fields = ('pk', 'name', 'device_count', 'vm_count', 'color', 'vm_role', 'slug', 'actions')


#
# Platforms
#

class PlatformTable(BaseTable):
    pk = ToggleColumn()
    device_count = tables.TemplateColumn(
        template_code=PLATFORM_DEVICE_COUNT,
        accessor=Accessor('devices.count'),
        orderable=False,
        verbose_name='Devices'
    )
    vm_count = tables.TemplateColumn(
        template_code=PLATFORM_VM_COUNT,
        accessor=Accessor('virtual_machines.count'),
        orderable=False,
        verbose_name='VMs'
    )
    actions = tables.TemplateColumn(
        template_code=PLATFORM_ACTIONS,
        attrs={'td': {'class': 'text-right noprint'}},
        verbose_name=''
    )

    class Meta(BaseTable.Meta):
        model = Platform
        fields = ('pk', 'name', 'manufacturer', 'device_count', 'vm_count', 'slug', 'napalm_driver', 'actions')


#
# Devices
#

class DeviceTable(BaseTable):
    pk = ToggleColumn()
    name = tables.TemplateColumn(
        order_by=('_nat1', '_nat2', '_nat3'),
        template_code=DEVICE_LINK
    )
    status = tables.TemplateColumn(template_code=STATUS_LABEL, verbose_name='Status')
    tenant = tables.TemplateColumn(template_code=COL_TENANT)
    site = tables.LinkColumn('dcim:site', args=[Accessor('site.slug')])
    rack = tables.LinkColumn('dcim:rack', args=[Accessor('rack.pk')])
    device_role = tables.TemplateColumn(DEVICE_ROLE, verbose_name='Role')
    device_type = tables.LinkColumn(
        'dcim:devicetype', args=[Accessor('device_type.pk')], verbose_name='Type',
        text=lambda record: record.device_type.display_name
    )

    class Meta(BaseTable.Meta):
        model = Device
        fields = ('pk', 'name', 'status', 'tenant', 'site', 'rack', 'device_role', 'device_type')


class DeviceDetailTable(DeviceTable):
    primary_ip = tables.TemplateColumn(
        orderable=False, verbose_name='IP Address', template_code=DEVICE_PRIMARY_IP
    )

    class Meta(DeviceTable.Meta):
        model = Device
        fields = ('pk', 'name', 'status', 'tenant', 'site', 'rack', 'device_role', 'device_type', 'primary_ip')


class DeviceImportTable(BaseTable):
    name = tables.TemplateColumn(template_code=DEVICE_LINK, verbose_name='Name')
    status = tables.TemplateColumn(template_code=STATUS_LABEL, verbose_name='Status')
    tenant = tables.TemplateColumn(template_code=COL_TENANT)
    site = tables.LinkColumn('dcim:site', args=[Accessor('site.slug')], verbose_name='Site')
    rack = tables.LinkColumn('dcim:rack', args=[Accessor('rack.pk')], verbose_name='Rack')
    position = tables.Column(verbose_name='Position')
    device_role = tables.Column(verbose_name='Role')
    device_type = tables.Column(verbose_name='Type')

    class Meta(BaseTable.Meta):
        model = Device
        fields = ('name', 'status', 'tenant', 'site', 'rack', 'position', 'device_role', 'device_type')
        empty_text = False


#
# Device components
#

class ConsolePortTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = ConsolePort
        fields = ('name',)


class ConsoleServerPortTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = ConsoleServerPort
        fields = ('name', 'description')


class PowerPortTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = PowerPort
        fields = ('name',)


class PowerOutletTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = PowerOutlet
        fields = ('name', 'description')


class InterfaceTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = Interface
        fields = ('name', 'type', 'lag', 'enabled', 'mgmt_only', 'description')


class FrontPortTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = FrontPort
        fields = ('name', 'type', 'rear_port', 'rear_port_position', 'description')
        empty_text = "None"


class RearPortTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = RearPort
        fields = ('name', 'type', 'positions', 'description')
        empty_text = "None"


class DeviceBayTable(BaseTable):

    class Meta(BaseTable.Meta):
        model = DeviceBay
        fields = ('name',)


#
# Cables
#

class CableTable(BaseTable):
    pk = ToggleColumn()
    id = tables.LinkColumn(
        viewname='dcim:cable',
        args=[Accessor('pk')],
        verbose_name='ID'
    )
    termination_a_parent = tables.TemplateColumn(
        template_code=CABLE_TERMINATION_PARENT,
        accessor=Accessor('termination_a'),
        orderable=False,
        verbose_name='Termination A'
    )
    termination_a = tables.Column(
        accessor=Accessor('termination_a'),
        orderable=False,
        verbose_name=''
    )
    termination_b_parent = tables.TemplateColumn(
        template_code=CABLE_TERMINATION_PARENT,
        accessor=Accessor('termination_b'),
        orderable=False,
        verbose_name='Termination B'
    )
    termination_b = tables.Column(
        accessor=Accessor('termination_b'),
        orderable=False,
        verbose_name=''
    )
    status = tables.TemplateColumn(
        template_code=STATUS_LABEL
    )
    length = tables.TemplateColumn(
        template_code=CABLE_LENGTH,
        order_by='_abs_length'
    )
    color = ColorColumn()

    class Meta(BaseTable.Meta):
        model = Cable
        fields = (
            'pk', 'id', 'label', 'termination_a_parent', 'termination_a', 'termination_b_parent', 'termination_b',
            'status', 'type', 'color', 'length',
        )


#
# Device connections
#

class ConsoleConnectionTable(BaseTable):
    console_server = tables.LinkColumn(
        viewname='dcim:device',
        accessor=Accessor('connected_endpoint.device'),
        args=[Accessor('connected_endpoint.device.pk')],
        verbose_name='Console Server'
    )
    connected_endpoint = tables.Column(
        verbose_name='Port'
    )
    device = tables.LinkColumn(
        viewname='dcim:device',
        args=[Accessor('device.pk')]
    )
    name = tables.Column(
        verbose_name='Console Port'
    )

    class Meta(BaseTable.Meta):
        model = ConsolePort
        fields = ('console_server', 'connected_endpoint', 'device', 'name', 'connection_status')


class PowerConnectionTable(BaseTable):
    pdu = tables.LinkColumn(
        viewname='dcim:device',
        accessor=Accessor('connected_endpoint.device'),
        args=[Accessor('connected_endpoint.device.pk')],
        verbose_name='PDU'
    )
    outlet = tables.Column(
        accessor=Accessor('_connected_poweroutlet'),
        verbose_name='Outlet'
    )
    device = tables.LinkColumn(
        viewname='dcim:device',
        args=[Accessor('device.pk')]
    )
    name = tables.Column(
        verbose_name='Power Port'
    )

    class Meta(BaseTable.Meta):
        model = PowerPort
        fields = ('pdu', 'outlet', 'device', 'name', 'connection_status')


class InterfaceConnectionTable(BaseTable):
    device_a = tables.LinkColumn(
        viewname='dcim:device',
        accessor=Accessor('device'),
        args=[Accessor('device.pk')],
        verbose_name='Device A'
    )
    interface_a = tables.LinkColumn(
        viewname='dcim:interface',
        accessor=Accessor('name'),
        args=[Accessor('pk')],
        verbose_name='Interface A'
    )
    description_a = tables.Column(
        accessor=Accessor('description'),
        verbose_name='Description'
    )
    device_b = tables.LinkColumn(
        viewname='dcim:device',
        accessor=Accessor('_connected_interface.device'),
        args=[Accessor('_connected_interface.device.pk')],
        verbose_name='Device B'
    )
    interface_b = tables.LinkColumn(
        viewname='dcim:interface',
        accessor=Accessor('_connected_interface'),
        args=[Accessor('_connected_interface.pk')],
        verbose_name='Interface B'
    )
    description_b = tables.Column(
        accessor=Accessor('_connected_interface.description'),
        verbose_name='Description'
    )

    class Meta(BaseTable.Meta):
        model = Interface
        fields = (
            'device_a', 'interface_a', 'description_a', 'device_b', 'interface_b', 'description_b', 'connection_status',
        )


#
# InventoryItems
#

class InventoryItemTable(BaseTable):
    pk = ToggleColumn()
    device = tables.LinkColumn('dcim:device_inventory', args=[Accessor('device.pk')])
    manufacturer = tables.Column(accessor=Accessor('manufacturer.name'), verbose_name='Manufacturer')

    class Meta(BaseTable.Meta):
        model = InventoryItem
        fields = ('pk', 'device', 'name', 'manufacturer', 'part_id', 'serial', 'asset_tag', 'description')


#
# Virtual chassis
#

class VirtualChassisTable(BaseTable):
    pk = ToggleColumn()
    master = tables.LinkColumn()
    member_count = tables.Column(verbose_name='Members')
    actions = tables.TemplateColumn(
        template_code=VIRTUALCHASSIS_ACTIONS,
        attrs={'td': {'class': 'text-right noprint'}},
        verbose_name=''
    )

    class Meta(BaseTable.Meta):
        model = VirtualChassis
        fields = ('pk', 'master', 'domain', 'member_count', 'actions')


#
# Power panels
#

class PowerPanelTable(BaseTable):
    pk = ToggleColumn()
    name = tables.LinkColumn()
    site = tables.LinkColumn(
        viewname='dcim:site',
        args=[Accessor('site.slug')]
    )
    powerfeed_count = tables.TemplateColumn(
        template_code=POWERPANEL_POWERFEED_COUNT,
        verbose_name='Feeds'
    )

    class Meta(BaseTable.Meta):
        model = PowerPanel
        fields = ('pk', 'name', 'site', 'rack_group', 'powerfeed_count')


#
# Power feeds
#

class PowerFeedTable(BaseTable):
    pk = ToggleColumn()
    name = tables.LinkColumn()
    power_panel = tables.LinkColumn(
        viewname='dcim:powerpanel',
        args=[Accessor('power_panel.pk')],
    )
    rack = tables.LinkColumn(
        viewname='dcim:rack',
        args=[Accessor('rack.pk')]
    )
    status = tables.TemplateColumn(
        template_code=STATUS_LABEL
    )
    type = tables.TemplateColumn(
        template_code=TYPE_LABEL
    )

    class Meta(BaseTable.Meta):
        model = PowerFeed
        fields = ('pk', 'name', 'power_panel', 'rack', 'status', 'type', 'supply', 'voltage', 'amperage', 'phase')

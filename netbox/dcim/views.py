import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Count, F
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import escape
from django.utils.http import is_safe_url
from django.utils.safestring import mark_safe
from django.views.generic import View

from circuits.models import Circuit
from extras.models import Graph, TopologyMap, GRAPH_TYPE_INTERFACE, GRAPH_TYPE_SITE
from extras.views import ObjectConfigContextView
from ipam.models import Prefix, VLAN
from ipam.tables import InterfaceIPAddressTable, InterfaceVLANTable
from utilities.forms import ConfirmationForm
from utilities.paginator import EnhancedPaginator
from utilities.utils import csv_format
from utilities.views import (
    BulkComponentCreateView, BulkDeleteView, BulkEditView, BulkImportView, ComponentCreateView, GetReturnURLMixin,
    ObjectDeleteView, ObjectEditView, ObjectListView,
)
from virtualization.models import VirtualMachine
from . import filters, forms, tables
from .models import (
    Cable, ConsolePort, ConsolePortTemplate, ConsoleServerPort, ConsoleServerPortTemplate, Device, DeviceBay,
    DeviceBayTemplate, DeviceRole, DeviceType, FrontPort, FrontPortTemplate, Interface, InterfaceTemplate,
    InventoryItem, Manufacturer, Platform, PowerFeed, PowerOutlet, PowerOutletTemplate, PowerPanel, PowerPort,
    PowerPortTemplate, Rack, RackGroup, RackReservation, RackRole, RearPort, RearPortTemplate, Region, Site,
    VirtualChassis,
)


class BulkRenameView(GetReturnURLMixin, View):
    """
    An extendable view for renaming device components in bulk.
    """
    queryset = None
    form = None
    template_name = 'dcim/bulk_rename.html'

    def post(self, request):

        model = self.queryset.model

        if '_preview' in request.POST or '_apply' in request.POST:
            form = self.form(request.POST, initial={'pk': request.POST.getlist('pk')})
            selected_objects = self.queryset.filter(pk__in=form.initial['pk'])

            if form.is_valid():
                for obj in selected_objects:
                    find = form.cleaned_data['find']
                    replace = form.cleaned_data['replace']
                    if form.cleaned_data['use_regex']:
                        try:
                            obj.new_name = re.sub(find, replace, obj.name)
                        # Catch regex group reference errors
                        except re.error:
                            obj.new_name = obj.name
                    else:
                        obj.new_name = obj.name.replace(find, replace)

                if '_apply' in request.POST:
                    for obj in selected_objects:
                        obj.name = obj.new_name
                        obj.save()
                    messages.success(request, "Renamed {} {}".format(
                        len(selected_objects),
                        model._meta.verbose_name_plural
                    ))
                    return redirect(self.get_return_url(request))

        else:
            form = self.form(initial={'pk': request.POST.getlist('pk')})
            selected_objects = self.queryset.filter(pk__in=form.initial['pk'])

        return render(request, self.template_name, {
            'form': form,
            'obj_type_plural': model._meta.verbose_name_plural,
            'selected_objects': selected_objects,
            'return_url': self.get_return_url(request),
        })


class BulkDisconnectView(GetReturnURLMixin, View):
    """
    An extendable view for disconnection console/power/interface components in bulk.
    """
    model = None
    form = None
    template_name = 'dcim/bulk_disconnect.html'

    def post(self, request):

        selected_objects = []
        return_url = self.get_return_url(request)

        if '_confirm' in request.POST:
            form = self.form(request.POST)

            if form.is_valid():

                with transaction.atomic():

                    count = 0
                    for obj in self.model.objects.filter(pk__in=form.cleaned_data['pk']):
                        if obj.cable is None:
                            continue
                        obj.cable.delete()
                        count += 1

                messages.success(request, "Disconnected {} {}".format(
                    count, self.model._meta.verbose_name_plural
                ))

                return redirect(return_url)

        else:
            form = self.form(initial={'pk': request.POST.getlist('pk')})
            selected_objects = self.model.objects.filter(pk__in=form.initial['pk'])

        return render(request, self.template_name, {
            'form': form,
            'obj_type_plural': self.model._meta.verbose_name_plural,
            'selected_objects': selected_objects,
            'return_url': return_url,
        })


#
# Regions
#

class RegionListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_region'
    queryset = Region.objects.add_related_count(
        Region.objects.all(),
        Site,
        'region',
        'site_count',
        cumulative=True
    )
    filter = filters.RegionFilter
    filter_form = forms.RegionFilterForm
    table = tables.RegionTable
    template_name = 'dcim/region_list.html'


class RegionCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_region'
    model = Region
    model_form = forms.RegionForm
    default_return_url = 'dcim:region_list'


class RegionEditView(RegionCreateView):
    permission_required = 'dcim.change_region'


class RegionBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_region'
    model_form = forms.RegionCSVForm
    table = tables.RegionTable
    default_return_url = 'dcim:region_list'


class RegionBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_region'
    queryset = Region.objects.all()
    filter = filters.RegionFilter
    table = tables.RegionTable
    default_return_url = 'dcim:region_list'


#
# Sites
#

class SiteListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_site'
    queryset = Site.objects.select_related('region', 'tenant')
    filter = filters.SiteFilter
    filter_form = forms.SiteFilterForm
    table = tables.SiteTable
    template_name = 'dcim/site_list.html'


class SiteView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_site'

    def get(self, request, slug):

        site = get_object_or_404(Site.objects.select_related('region', 'tenant__group'), slug=slug)
        stats = {
            'rack_count': Rack.objects.filter(site=site).count(),
            'device_count': Device.objects.filter(site=site).count(),
            'prefix_count': Prefix.objects.filter(site=site).count(),
            'vlan_count': VLAN.objects.filter(site=site).count(),
            'circuit_count': Circuit.objects.filter(terminations__site=site).count(),
            'vm_count': VirtualMachine.objects.filter(cluster__site=site).count(),
        }
        rack_groups = RackGroup.objects.filter(site=site).annotate(rack_count=Count('racks'))
        topology_maps = TopologyMap.objects.filter(site=site)
        show_graphs = Graph.objects.filter(type=GRAPH_TYPE_SITE).exists()

        return render(request, 'dcim/site.html', {
            'site': site,
            'stats': stats,
            'rack_groups': rack_groups,
            'topology_maps': topology_maps,
            'show_graphs': show_graphs,
        })


class SiteCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_site'
    model = Site
    model_form = forms.SiteForm
    template_name = 'dcim/site_edit.html'
    default_return_url = 'dcim:site_list'


class SiteEditView(SiteCreateView):
    permission_required = 'dcim.change_site'


class SiteDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_site'
    model = Site
    default_return_url = 'dcim:site_list'


class SiteBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_site'
    model_form = forms.SiteCSVForm
    table = tables.SiteTable
    default_return_url = 'dcim:site_list'


class SiteBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_site'
    queryset = Site.objects.select_related('region', 'tenant')
    filter = filters.SiteFilter
    table = tables.SiteTable
    form = forms.SiteBulkEditForm
    default_return_url = 'dcim:site_list'


class SiteBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_site'
    queryset = Site.objects.select_related('region', 'tenant')
    filter = filters.SiteFilter
    table = tables.SiteTable
    default_return_url = 'dcim:site_list'


#
# Rack groups
#

class RackGroupListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_rackgroup'
    queryset = RackGroup.objects.select_related('site').annotate(rack_count=Count('racks'))
    filter = filters.RackGroupFilter
    filter_form = forms.RackGroupFilterForm
    table = tables.RackGroupTable
    template_name = 'dcim/rackgroup_list.html'


class RackGroupCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_rackgroup'
    model = RackGroup
    model_form = forms.RackGroupForm
    default_return_url = 'dcim:rackgroup_list'


class RackGroupEditView(RackGroupCreateView):
    permission_required = 'dcim.change_rackgroup'


class RackGroupBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_rackgroup'
    model_form = forms.RackGroupCSVForm
    table = tables.RackGroupTable
    default_return_url = 'dcim:rackgroup_list'


class RackGroupBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_rackgroup'
    queryset = RackGroup.objects.select_related('site').annotate(rack_count=Count('racks'))
    filter = filters.RackGroupFilter
    table = tables.RackGroupTable
    default_return_url = 'dcim:rackgroup_list'


#
# Rack roles
#

class RackRoleListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_rackrole'
    queryset = RackRole.objects.annotate(rack_count=Count('racks'))
    table = tables.RackRoleTable
    template_name = 'dcim/rackrole_list.html'


class RackRoleCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_rackrole'
    model = RackRole
    model_form = forms.RackRoleForm
    default_return_url = 'dcim:rackrole_list'


class RackRoleEditView(RackRoleCreateView):
    permission_required = 'dcim.change_rackrole'


class RackRoleBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_rackrole'
    model_form = forms.RackRoleCSVForm
    table = tables.RackRoleTable
    default_return_url = 'dcim:rackrole_list'


class RackRoleBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_rackrole'
    queryset = RackRole.objects.annotate(rack_count=Count('racks'))
    table = tables.RackRoleTable
    default_return_url = 'dcim:rackrole_list'


#
# Racks
#

class RackListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_rack'
    queryset = Rack.objects.select_related(
        'site', 'group', 'tenant', 'role'
    ).prefetch_related(
        'devices__device_type'
    ).annotate(
        device_count=Count('devices')
    )
    filter = filters.RackFilter
    filter_form = forms.RackFilterForm
    table = tables.RackDetailTable
    template_name = 'dcim/rack_list.html'


class RackElevationListView(PermissionRequiredMixin, View):
    """
    Display a set of rack elevations side-by-side.
    """
    permission_required = 'dcim.view_rack'

    def get(self, request):

        racks = Rack.objects.select_related(
            'site', 'group', 'tenant', 'role'
        ).prefetch_related(
            'devices__device_type'
        )
        racks = filters.RackFilter(request.GET, racks).qs
        total_count = racks.count()

        # Pagination
        per_page = request.GET.get('per_page', settings.PAGINATE_COUNT)
        page_number = request.GET.get('page', 1)
        paginator = EnhancedPaginator(racks, per_page)
        try:
            page = paginator.page(page_number)
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        # Determine rack face
        if request.GET.get('face') == '1':
            face_id = 1
        else:
            face_id = 0

        return render(request, 'dcim/rack_elevation_list.html', {
            'paginator': paginator,
            'page': page,
            'total_count': total_count,
            'face_id': face_id,
            'filter_form': forms.RackFilterForm(request.GET),
        })


class RackView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_rack'

    def get(self, request, pk):

        rack = get_object_or_404(Rack.objects.select_related('site__region', 'tenant__group', 'group', 'role'), pk=pk)

        nonracked_devices = Device.objects.filter(rack=rack, position__isnull=True, parent_bay__isnull=True) \
            .select_related('device_type__manufacturer')
        next_rack = Rack.objects.filter(site=rack.site, name__gt=rack.name).order_by('name').first()
        prev_rack = Rack.objects.filter(site=rack.site, name__lt=rack.name).order_by('-name').first()

        reservations = RackReservation.objects.filter(rack=rack)
        power_feeds = PowerFeed.objects.filter(rack=rack).select_related('power_panel')

        return render(request, 'dcim/rack.html', {
            'rack': rack,
            'reservations': reservations,
            'power_feeds': power_feeds,
            'nonracked_devices': nonracked_devices,
            'next_rack': next_rack,
            'prev_rack': prev_rack,
            'front_elevation': rack.get_front_elevation(),
            'rear_elevation': rack.get_rear_elevation(),
        })


class RackCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_rack'
    model = Rack
    model_form = forms.RackForm
    template_name = 'dcim/rack_edit.html'
    default_return_url = 'dcim:rack_list'


class RackEditView(RackCreateView):
    permission_required = 'dcim.change_rack'


class RackDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_rack'
    model = Rack
    default_return_url = 'dcim:rack_list'


class RackBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_rack'
    model_form = forms.RackCSVForm
    table = tables.RackTable
    default_return_url = 'dcim:rack_list'


class RackBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_rack'
    queryset = Rack.objects.select_related('site', 'group', 'tenant', 'role')
    filter = filters.RackFilter
    table = tables.RackTable
    form = forms.RackBulkEditForm
    default_return_url = 'dcim:rack_list'


class RackBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_rack'
    queryset = Rack.objects.select_related('site', 'group', 'tenant', 'role')
    filter = filters.RackFilter
    table = tables.RackTable
    default_return_url = 'dcim:rack_list'


#
# Rack reservations
#

class RackReservationListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_rackreservation'
    queryset = RackReservation.objects.select_related('rack__site')
    filter = filters.RackReservationFilter
    filter_form = forms.RackReservationFilterForm
    table = tables.RackReservationTable
    template_name = 'dcim/rackreservation_list.html'


class RackReservationCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_rackreservation'
    model = RackReservation
    model_form = forms.RackReservationForm

    def alter_obj(self, obj, request, args, kwargs):
        if not obj.pk:
            obj.rack = get_object_or_404(Rack, pk=kwargs['rack'])
            obj.user = request.user
        return obj

    def get_return_url(self, request, obj):
        return obj.rack.get_absolute_url()


class RackReservationEditView(RackReservationCreateView):
    permission_required = 'dcim.change_rackreservation'


class RackReservationDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_rackreservation'
    model = RackReservation

    def get_return_url(self, request, obj):
        return obj.rack.get_absolute_url()


class RackReservationBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_rackreservation'
    queryset = RackReservation.objects.select_related('rack', 'user')
    filter = filters.RackReservationFilter
    table = tables.RackReservationTable
    form = forms.RackReservationBulkEditForm
    default_return_url = 'dcim:rackreservation_list'


class RackReservationBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_rackreservation'
    queryset = RackReservation.objects.select_related('rack', 'user')
    filter = filters.RackReservationFilter
    table = tables.RackReservationTable
    default_return_url = 'dcim:rackreservation_list'


#
# Manufacturers
#

class ManufacturerListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_manufacturer'
    queryset = Manufacturer.objects.annotate(
        devicetype_count=Count('device_types', distinct=True),
        inventoryitem_count=Count('inventory_items', distinct=True),
        platform_count=Count('platforms', distinct=True),
    )
    table = tables.ManufacturerTable
    template_name = 'dcim/manufacturer_list.html'


class ManufacturerCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_manufacturer'
    model = Manufacturer
    model_form = forms.ManufacturerForm
    default_return_url = 'dcim:manufacturer_list'


class ManufacturerEditView(ManufacturerCreateView):
    permission_required = 'dcim.change_manufacturer'


class ManufacturerBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_manufacturer'
    model_form = forms.ManufacturerCSVForm
    table = tables.ManufacturerTable
    default_return_url = 'dcim:manufacturer_list'


class ManufacturerBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_manufacturer'
    queryset = Manufacturer.objects.annotate(devicetype_count=Count('device_types'))
    table = tables.ManufacturerTable
    default_return_url = 'dcim:manufacturer_list'


#
# Device types
#

class DeviceTypeListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_devicetype'
    queryset = DeviceType.objects.select_related('manufacturer').annotate(instance_count=Count('instances'))
    filter = filters.DeviceTypeFilter
    filter_form = forms.DeviceTypeFilterForm
    table = tables.DeviceTypeTable
    template_name = 'dcim/devicetype_list.html'


class DeviceTypeView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_devicetype'

    def get(self, request, pk):

        devicetype = get_object_or_404(DeviceType, pk=pk)

        # Component tables
        consoleport_table = tables.ConsolePortTemplateTable(
            ConsolePortTemplate.objects.filter(device_type=devicetype),
            orderable=False
        )
        consoleserverport_table = tables.ConsoleServerPortTemplateTable(
            ConsoleServerPortTemplate.objects.filter(device_type=devicetype),
            orderable=False
        )
        powerport_table = tables.PowerPortTemplateTable(
            PowerPortTemplate.objects.filter(device_type=devicetype),
            orderable=False
        )
        poweroutlet_table = tables.PowerOutletTemplateTable(
            PowerOutletTemplate.objects.filter(device_type=devicetype),
            orderable=False
        )
        interface_table = tables.InterfaceTemplateTable(
            list(InterfaceTemplate.objects.filter(device_type=devicetype)),
            orderable=False
        )
        front_port_table = tables.FrontPortTemplateTable(
            FrontPortTemplate.objects.filter(device_type=devicetype),
            orderable=False
        )
        rear_port_table = tables.RearPortTemplateTable(
            RearPortTemplate.objects.filter(device_type=devicetype),
            orderable=False
        )
        devicebay_table = tables.DeviceBayTemplateTable(
            DeviceBayTemplate.objects.filter(device_type=devicetype),
            orderable=False
        )
        if request.user.has_perm('dcim.change_devicetype'):
            consoleport_table.columns.show('pk')
            consoleserverport_table.columns.show('pk')
            powerport_table.columns.show('pk')
            poweroutlet_table.columns.show('pk')
            interface_table.columns.show('pk')
            front_port_table.columns.show('pk')
            rear_port_table.columns.show('pk')
            devicebay_table.columns.show('pk')

        return render(request, 'dcim/devicetype.html', {
            'devicetype': devicetype,
            'consoleport_table': consoleport_table,
            'consoleserverport_table': consoleserverport_table,
            'powerport_table': powerport_table,
            'poweroutlet_table': poweroutlet_table,
            'interface_table': interface_table,
            'front_port_table': front_port_table,
            'rear_port_table': rear_port_table,
            'devicebay_table': devicebay_table,
        })


class DeviceTypeCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_devicetype'
    model = DeviceType
    model_form = forms.DeviceTypeForm
    template_name = 'dcim/devicetype_edit.html'
    default_return_url = 'dcim:devicetype_list'


class DeviceTypeEditView(DeviceTypeCreateView):
    permission_required = 'dcim.change_devicetype'


class DeviceTypeDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_devicetype'
    model = DeviceType
    default_return_url = 'dcim:devicetype_list'


class DeviceTypeBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_devicetype'
    model_form = forms.DeviceTypeCSVForm
    table = tables.DeviceTypeTable
    default_return_url = 'dcim:devicetype_list'


class DeviceTypeBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_devicetype'
    queryset = DeviceType.objects.select_related('manufacturer').annotate(instance_count=Count('instances'))
    filter = filters.DeviceTypeFilter
    table = tables.DeviceTypeTable
    form = forms.DeviceTypeBulkEditForm
    default_return_url = 'dcim:devicetype_list'


class DeviceTypeBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_devicetype'
    queryset = DeviceType.objects.select_related('manufacturer').annotate(instance_count=Count('instances'))
    filter = filters.DeviceTypeFilter
    table = tables.DeviceTypeTable
    default_return_url = 'dcim:devicetype_list'


#
# Device type components
#

class ConsolePortTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_consoleporttemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = ConsolePortTemplate
    form = forms.ConsolePortTemplateCreateForm
    model_form = forms.ConsolePortTemplateForm
    template_name = 'dcim/device_component_add.html'


class ConsolePortTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_consoleporttemplate'
    queryset = ConsolePortTemplate.objects.all()
    parent_model = DeviceType
    table = tables.ConsolePortTemplateTable


class ConsoleServerPortTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_consoleserverporttemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = ConsoleServerPortTemplate
    form = forms.ConsoleServerPortTemplateCreateForm
    model_form = forms.ConsoleServerPortTemplateForm
    template_name = 'dcim/device_component_add.html'


class ConsoleServerPortTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_consoleserverporttemplate'
    queryset = ConsoleServerPortTemplate.objects.all()
    parent_model = DeviceType
    table = tables.ConsoleServerPortTemplateTable


class PowerPortTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_powerporttemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = PowerPortTemplate
    form = forms.PowerPortTemplateCreateForm
    model_form = forms.PowerPortTemplateForm
    template_name = 'dcim/device_component_add.html'


class PowerPortTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_powerporttemplate'
    queryset = PowerPortTemplate.objects.all()
    parent_model = DeviceType
    table = tables.PowerPortTemplateTable


class PowerOutletTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_poweroutlettemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = PowerOutletTemplate
    form = forms.PowerOutletTemplateCreateForm
    model_form = forms.PowerOutletTemplateForm
    template_name = 'dcim/device_component_add.html'


class PowerOutletTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_poweroutlettemplate'
    queryset = PowerOutletTemplate.objects.all()
    parent_model = DeviceType
    table = tables.PowerOutletTemplateTable


class InterfaceTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_interfacetemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = InterfaceTemplate
    form = forms.InterfaceTemplateCreateForm
    model_form = forms.InterfaceTemplateForm
    template_name = 'dcim/device_component_add.html'


class InterfaceTemplateBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_interfacetemplate'
    queryset = InterfaceTemplate.objects.all()
    parent_model = DeviceType
    table = tables.InterfaceTemplateTable
    form = forms.InterfaceTemplateBulkEditForm


class InterfaceTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_interfacetemplate'
    queryset = InterfaceTemplate.objects.all()
    parent_model = DeviceType
    table = tables.InterfaceTemplateTable


class FrontPortTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_frontporttemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = FrontPortTemplate
    form = forms.FrontPortTemplateCreateForm
    model_form = forms.FrontPortTemplateForm
    template_name = 'dcim/device_component_add.html'


class FrontPortTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_frontporttemplate'
    queryset = FrontPortTemplate.objects.all()
    parent_model = DeviceType
    table = tables.FrontPortTemplateTable


class RearPortTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_rearporttemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = RearPortTemplate
    form = forms.RearPortTemplateCreateForm
    model_form = forms.RearPortTemplateForm
    template_name = 'dcim/device_component_add.html'


class RearPortTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_rearporttemplate'
    queryset = RearPortTemplate.objects.all()
    parent_model = DeviceType
    table = tables.RearPortTemplateTable


class DeviceBayTemplateCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_devicebaytemplate'
    parent_model = DeviceType
    parent_field = 'device_type'
    model = DeviceBayTemplate
    form = forms.DeviceBayTemplateCreateForm
    model_form = forms.DeviceBayTemplateForm
    template_name = 'dcim/device_component_add.html'


class DeviceBayTemplateBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_devicebaytemplate'
    queryset = DeviceBayTemplate.objects.all()
    parent_model = DeviceType
    table = tables.DeviceBayTemplateTable


#
# Device roles
#

class DeviceRoleListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_devicerole'
    queryset = DeviceRole.objects.all()
    table = tables.DeviceRoleTable
    template_name = 'dcim/devicerole_list.html'


class DeviceRoleCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_devicerole'
    model = DeviceRole
    model_form = forms.DeviceRoleForm
    default_return_url = 'dcim:devicerole_list'


class DeviceRoleEditView(DeviceRoleCreateView):
    permission_required = 'dcim.change_devicerole'


class DeviceRoleBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_devicerole'
    model_form = forms.DeviceRoleCSVForm
    table = tables.DeviceRoleTable
    default_return_url = 'dcim:devicerole_list'


class DeviceRoleBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_devicerole'
    queryset = DeviceRole.objects.all()
    table = tables.DeviceRoleTable
    default_return_url = 'dcim:devicerole_list'


#
# Platforms
#

class PlatformListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_platform'
    queryset = Platform.objects.all()
    table = tables.PlatformTable
    template_name = 'dcim/platform_list.html'


class PlatformCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_platform'
    model = Platform
    model_form = forms.PlatformForm
    default_return_url = 'dcim:platform_list'


class PlatformEditView(PlatformCreateView):
    permission_required = 'dcim.change_platform'


class PlatformBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_platform'
    model_form = forms.PlatformCSVForm
    table = tables.PlatformTable
    default_return_url = 'dcim:platform_list'


class PlatformBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_platform'
    queryset = Platform.objects.all()
    table = tables.PlatformTable
    default_return_url = 'dcim:platform_list'


#
# Devices
#

class DeviceListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_device'
    queryset = Device.objects.select_related(
        'device_type__manufacturer', 'device_role', 'tenant', 'site', 'rack', 'primary_ip4', 'primary_ip6'
    )
    filter = filters.DeviceFilter
    filter_form = forms.DeviceFilterForm
    table = tables.DeviceDetailTable
    template_name = 'dcim/device_list.html'


class DeviceView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_device'

    def get(self, request, pk):

        device = get_object_or_404(Device.objects.select_related(
            'site__region', 'rack__group', 'tenant__group', 'device_role', 'platform'
        ), pk=pk)

        # VirtualChassis members
        if device.virtual_chassis is not None:
            vc_members = Device.objects.filter(
                virtual_chassis=device.virtual_chassis
            ).order_by('vc_position')
        else:
            vc_members = []

        # Console ports
        console_ports = device.consoleports.select_related('connected_endpoint__device', 'cable')

        # Console server ports
        consoleserverports = device.consoleserverports.select_related('connected_endpoint__device', 'cable')

        # Power ports
        power_ports = device.powerports.select_related('_connected_poweroutlet__device', 'cable')

        # Power outlets
        poweroutlets = device.poweroutlets.select_related('connected_endpoint__device', 'cable', 'power_port')

        # Interfaces
        interfaces = device.vc_interfaces.select_related(
            'lag', '_connected_interface__device', '_connected_circuittermination__circuit', 'cable'
        ).prefetch_related(
            'cable__termination_a', 'cable__termination_b', 'ip_addresses', 'tags'
        )

        # Front ports
        front_ports = device.frontports.select_related('rear_port', 'cable')

        # Rear ports
        rear_ports = device.rearports.select_related('cable')

        # Device bays
        device_bays = device.device_bays.select_related('installed_device__device_type__manufacturer')

        # Services
        services = device.services.all()

        # Secrets
        secrets = device.secrets.all()

        # Find up to ten devices in the same site with the same functional role for quick reference.
        related_devices = Device.objects.filter(
            site=device.site, device_role=device.device_role
        ).exclude(
            pk=device.pk
        ).select_related(
            'rack', 'device_type__manufacturer'
        )[:10]

        # Show graph button on interfaces only if at least one graph has been created.
        show_graphs = Graph.objects.filter(type=GRAPH_TYPE_INTERFACE).exists()

        return render(request, 'dcim/device.html', {
            'device': device,
            'console_ports': console_ports,
            'consoleserverports': consoleserverports,
            'power_ports': power_ports,
            'poweroutlets': poweroutlets,
            'interfaces': interfaces,
            'device_bays': device_bays,
            'front_ports': front_ports,
            'rear_ports': rear_ports,
            'services': services,
            'secrets': secrets,
            'vc_members': vc_members,
            'related_devices': related_devices,
            'show_graphs': show_graphs,
        })


class DeviceInventoryView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_device'

    def get(self, request, pk):

        device = get_object_or_404(Device, pk=pk)
        inventory_items = InventoryItem.objects.filter(
            device=device, parent=None
        ).select_related(
            'manufacturer'
        ).prefetch_related(
            'child_items'
        )

        return render(request, 'dcim/device_inventory.html', {
            'device': device,
            'inventory_items': inventory_items,
            'active_tab': 'inventory',
        })


class DeviceStatusView(PermissionRequiredMixin, View):
    permission_required = ('dcim.view_device', 'dcim.napalm_read')

    def get(self, request, pk):

        device = get_object_or_404(Device, pk=pk)

        return render(request, 'dcim/device_status.html', {
            'device': device,
            'active_tab': 'status',
        })


class DeviceLLDPNeighborsView(PermissionRequiredMixin, View):
    permission_required = ('dcim.view_device', 'dcim.napalm_read')

    def get(self, request, pk):

        device = get_object_or_404(Device, pk=pk)
        interfaces = device.vc_interfaces.connectable().select_related(
            '_connected_interface__device'
        )

        return render(request, 'dcim/device_lldp_neighbors.html', {
            'device': device,
            'interfaces': interfaces,
            'active_tab': 'lldp-neighbors',
        })


class DeviceConfigView(PermissionRequiredMixin, View):
    permission_required = ('dcim.view_device', 'dcim.napalm_read')

    def get(self, request, pk):

        device = get_object_or_404(Device, pk=pk)

        return render(request, 'dcim/device_config.html', {
            'device': device,
            'active_tab': 'config',
        })


class DeviceConfigContextView(PermissionRequiredMixin, ObjectConfigContextView):
    permission_required = 'dcim.view_device'
    object_class = Device
    base_template = 'dcim/device.html'


class DeviceCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_device'
    model = Device
    model_form = forms.DeviceForm
    template_name = 'dcim/device_edit.html'
    default_return_url = 'dcim:device_list'


class DeviceEditView(DeviceCreateView):
    permission_required = 'dcim.change_device'


class DeviceDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_device'
    model = Device
    default_return_url = 'dcim:device_list'


class DeviceBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_device'
    model_form = forms.DeviceCSVForm
    table = tables.DeviceImportTable
    template_name = 'dcim/device_import.html'
    default_return_url = 'dcim:device_list'


class ChildDeviceBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_device'
    model_form = forms.ChildDeviceCSVForm
    table = tables.DeviceImportTable
    template_name = 'dcim/device_import_child.html'
    default_return_url = 'dcim:device_list'

    def _save_obj(self, obj_form):

        obj = obj_form.save()

        # Save the reverse relation to the parent device bay
        device_bay = obj.parent_bay
        device_bay.installed_device = obj
        device_bay.save()

        return obj


class DeviceBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_device'
    queryset = Device.objects.select_related('tenant', 'site', 'rack', 'device_role', 'device_type__manufacturer')
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    form = forms.DeviceBulkEditForm
    default_return_url = 'dcim:device_list'


class DeviceBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_device'
    queryset = Device.objects.select_related('tenant', 'site', 'rack', 'device_role', 'device_type__manufacturer')
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    default_return_url = 'dcim:device_list'


#
# Console ports
#

class ConsolePortCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_consoleport'
    parent_model = Device
    parent_field = 'device'
    model = ConsolePort
    form = forms.ConsolePortCreateForm
    model_form = forms.ConsolePortForm
    template_name = 'dcim/device_component_add.html'


class ConsolePortEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_consoleport'
    model = ConsolePort
    model_form = forms.ConsolePortForm


class ConsolePortDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_consoleport'
    model = ConsolePort


class ConsolePortBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_consoleport'
    queryset = ConsolePort.objects.all()
    parent_model = Device
    table = tables.ConsolePortTable


#
# Console server ports
#

class ConsoleServerPortCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_consoleserverport'
    parent_model = Device
    parent_field = 'device'
    model = ConsoleServerPort
    form = forms.ConsoleServerPortCreateForm
    model_form = forms.ConsoleServerPortForm
    template_name = 'dcim/device_component_add.html'


class ConsoleServerPortEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_consoleserverport'
    model = ConsoleServerPort
    model_form = forms.ConsoleServerPortForm


class ConsoleServerPortDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_consoleserverport'
    model = ConsoleServerPort


class ConsoleServerPortBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_consoleserverport'
    queryset = ConsoleServerPort.objects.all()
    parent_model = Device
    table = tables.ConsoleServerPortTable
    form = forms.ConsoleServerPortBulkEditForm


class ConsoleServerPortBulkRenameView(PermissionRequiredMixin, BulkRenameView):
    permission_required = 'dcim.change_consoleserverport'
    queryset = ConsoleServerPort.objects.all()
    form = forms.ConsoleServerPortBulkRenameForm


class ConsoleServerPortBulkDisconnectView(PermissionRequiredMixin, BulkDisconnectView):
    permission_required = 'dcim.change_consoleserverport'
    model = ConsoleServerPort
    form = forms.ConsoleServerPortBulkDisconnectForm


class ConsoleServerPortBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_consoleserverport'
    queryset = ConsoleServerPort.objects.all()
    parent_model = Device
    table = tables.ConsoleServerPortTable


#
# Power ports
#

class PowerPortCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_powerport'
    parent_model = Device
    parent_field = 'device'
    model = PowerPort
    form = forms.PowerPortCreateForm
    model_form = forms.PowerPortForm
    template_name = 'dcim/device_component_add.html'


class PowerPortEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_powerport'
    model = PowerPort
    model_form = forms.PowerPortForm


class PowerPortDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_powerport'
    model = PowerPort


class PowerPortBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_powerport'
    queryset = PowerPort.objects.all()
    parent_model = Device
    table = tables.PowerPortTable


#
# Power outlets
#

class PowerOutletCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_poweroutlet'
    parent_model = Device
    parent_field = 'device'
    model = PowerOutlet
    form = forms.PowerOutletCreateForm
    model_form = forms.PowerOutletForm
    template_name = 'dcim/device_component_add.html'


class PowerOutletEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_poweroutlet'
    model = PowerOutlet
    model_form = forms.PowerOutletForm


class PowerOutletDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_poweroutlet'
    model = PowerOutlet


class PowerOutletBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_poweroutlet'
    queryset = PowerOutlet.objects.all()
    parent_model = Device
    table = tables.PowerOutletTable
    form = forms.PowerOutletBulkEditForm


class PowerOutletBulkRenameView(PermissionRequiredMixin, BulkRenameView):
    permission_required = 'dcim.change_poweroutlet'
    queryset = PowerOutlet.objects.all()
    form = forms.PowerOutletBulkRenameForm


class PowerOutletBulkDisconnectView(PermissionRequiredMixin, BulkDisconnectView):
    permission_required = 'dcim.change_poweroutlet'
    model = PowerOutlet
    form = forms.PowerOutletBulkDisconnectForm


class PowerOutletBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_poweroutlet'
    queryset = PowerOutlet.objects.all()
    parent_model = Device
    table = tables.PowerOutletTable


#
# Interfaces
#

class InterfaceView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_interface'

    def get(self, request, pk):

        interface = get_object_or_404(Interface, pk=pk)

        # Get assigned IP addresses
        ipaddress_table = InterfaceIPAddressTable(
            data=interface.ip_addresses.select_related('vrf', 'tenant'),
            orderable=False
        )

        # Get assigned VLANs and annotate whether each is tagged or untagged
        vlans = []
        if interface.untagged_vlan is not None:
            vlans.append(interface.untagged_vlan)
            vlans[0].tagged = False
        for vlan in interface.tagged_vlans.select_related('site', 'group', 'tenant', 'role'):
            vlan.tagged = True
            vlans.append(vlan)
        vlan_table = InterfaceVLANTable(
            interface=interface,
            data=vlans,
            orderable=False
        )

        return render(request, 'dcim/interface.html', {
            'interface': interface,
            'connected_interface': interface._connected_interface,
            'connected_circuittermination': interface._connected_circuittermination,
            'ipaddress_table': ipaddress_table,
            'vlan_table': vlan_table,
        })


class InterfaceCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_interface'
    parent_model = Device
    parent_field = 'device'
    model = Interface
    form = forms.InterfaceCreateForm
    model_form = forms.InterfaceForm
    template_name = 'dcim/device_component_add.html'


class InterfaceEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_interface'
    model = Interface
    model_form = forms.InterfaceForm
    template_name = 'dcim/interface_edit.html'


class InterfaceAssignVLANsView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_interface'
    model = Interface
    model_form = forms.InterfaceAssignVLANsForm


class InterfaceDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_interface'
    model = Interface


class InterfaceBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_interface'
    queryset = Interface.objects.all()
    parent_model = Device
    table = tables.InterfaceTable
    form = forms.InterfaceBulkEditForm


class InterfaceBulkRenameView(PermissionRequiredMixin, BulkRenameView):
    permission_required = 'dcim.change_interface'
    queryset = Interface.objects.all()
    form = forms.InterfaceBulkRenameForm


class InterfaceBulkDisconnectView(PermissionRequiredMixin, BulkDisconnectView):
    permission_required = 'dcim.change_interface'
    model = Interface
    form = forms.InterfaceBulkDisconnectForm


class InterfaceBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_interface'
    queryset = Interface.objects.all()
    parent_model = Device
    table = tables.InterfaceTable


#
# Front ports
#

class FrontPortCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_frontport'
    parent_model = Device
    parent_field = 'device'
    model = FrontPort
    form = forms.FrontPortCreateForm
    model_form = forms.FrontPortForm
    template_name = 'dcim/device_component_add.html'


class FrontPortEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_frontport'
    model = FrontPort
    model_form = forms.FrontPortForm


class FrontPortDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_frontport'
    model = FrontPort


class FrontPortBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_frontport'
    queryset = FrontPort.objects.all()
    parent_model = Device
    table = tables.FrontPortTable
    form = forms.FrontPortBulkEditForm


class FrontPortBulkRenameView(PermissionRequiredMixin, BulkRenameView):
    permission_required = 'dcim.change_frontport'
    queryset = FrontPort.objects.all()
    form = forms.FrontPortBulkRenameForm


class FrontPortBulkDisconnectView(PermissionRequiredMixin, BulkDisconnectView):
    permission_required = 'dcim.change_frontport'
    model = FrontPort
    form = forms.FrontPortBulkDisconnectForm


class FrontPortBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_frontport'
    queryset = FrontPort.objects.all()
    parent_model = Device
    table = tables.FrontPortTable


#
# Rear ports
#

class RearPortCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_rearport'
    parent_model = Device
    parent_field = 'device'
    model = RearPort
    form = forms.RearPortCreateForm
    model_form = forms.RearPortForm
    template_name = 'dcim/device_component_add.html'


class RearPortEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_rearport'
    model = RearPort
    model_form = forms.RearPortForm


class RearPortDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_rearport'
    model = RearPort


class RearPortBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_rearport'
    queryset = RearPort.objects.all()
    parent_model = Device
    table = tables.RearPortTable
    form = forms.RearPortBulkEditForm


class RearPortBulkRenameView(PermissionRequiredMixin, BulkRenameView):
    permission_required = 'dcim.change_rearport'
    queryset = RearPort.objects.all()
    form = forms.RearPortBulkRenameForm


class RearPortBulkDisconnectView(PermissionRequiredMixin, BulkDisconnectView):
    permission_required = 'dcim.change_rearport'
    model = RearPort
    form = forms.RearPortBulkDisconnectForm


class RearPortBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_rearport'
    queryset = RearPort.objects.all()
    parent_model = Device
    table = tables.RearPortTable


#
# Device bays
#

class DeviceBayCreateView(PermissionRequiredMixin, ComponentCreateView):
    permission_required = 'dcim.add_devicebay'
    parent_model = Device
    parent_field = 'device'
    model = DeviceBay
    form = forms.DeviceBayCreateForm
    model_form = forms.DeviceBayForm
    template_name = 'dcim/device_component_add.html'


class DeviceBayEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_devicebay'
    model = DeviceBay
    model_form = forms.DeviceBayForm


class DeviceBayDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_devicebay'
    model = DeviceBay


class DeviceBayPopulateView(PermissionRequiredMixin, View):
    permission_required = 'dcim.change_devicebay'

    def get(self, request, pk):

        device_bay = get_object_or_404(DeviceBay, pk=pk)
        form = forms.PopulateDeviceBayForm(device_bay)

        return render(request, 'dcim/devicebay_populate.html', {
            'device_bay': device_bay,
            'form': form,
            'return_url': reverse('dcim:device', kwargs={'pk': device_bay.device.pk}),
        })

    def post(self, request, pk):

        device_bay = get_object_or_404(DeviceBay, pk=pk)
        form = forms.PopulateDeviceBayForm(device_bay, request.POST)

        if form.is_valid():

            device_bay.installed_device = form.cleaned_data['installed_device']
            device_bay.save()
            messages.success(request, "Added {} to {}.".format(device_bay.installed_device, device_bay))

            return redirect('dcim:device', pk=device_bay.device.pk)

        return render(request, 'dcim/devicebay_populate.html', {
            'device_bay': device_bay,
            'form': form,
            'return_url': reverse('dcim:device', kwargs={'pk': device_bay.device.pk}),
        })


class DeviceBayDepopulateView(PermissionRequiredMixin, View):
    permission_required = 'dcim.change_devicebay'

    def get(self, request, pk):

        device_bay = get_object_or_404(DeviceBay, pk=pk)
        form = ConfirmationForm()

        return render(request, 'dcim/devicebay_depopulate.html', {
            'device_bay': device_bay,
            'form': form,
            'return_url': reverse('dcim:device', kwargs={'pk': device_bay.device.pk}),
        })

    def post(self, request, pk):

        device_bay = get_object_or_404(DeviceBay, pk=pk)
        form = ConfirmationForm(request.POST)

        if form.is_valid():

            removed_device = device_bay.installed_device
            device_bay.installed_device = None
            device_bay.save()
            messages.success(request, "{} has been removed from {}.".format(removed_device, device_bay))

            return redirect('dcim:device', pk=device_bay.device.pk)

        return render(request, 'dcim/devicebay_depopulate.html', {
            'device_bay': device_bay,
            'form': form,
            'return_url': reverse('dcim:device', kwargs={'pk': device_bay.device.pk}),
        })


class DeviceBayBulkRenameView(PermissionRequiredMixin, BulkRenameView):
    permission_required = 'dcim.change_devicebay'
    queryset = DeviceBay.objects.all()
    form = forms.DeviceBayBulkRenameForm


class DeviceBayBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_devicebay'
    queryset = DeviceBay.objects.all()
    parent_model = Device
    table = tables.DeviceBayTable


#
# Bulk Device component creation
#

class DeviceBulkAddConsolePortView(PermissionRequiredMixin, BulkComponentCreateView):
    permission_required = 'dcim.add_consoleport'
    parent_model = Device
    parent_field = 'device'
    form = forms.DeviceBulkAddComponentForm
    model = ConsolePort
    model_form = forms.ConsolePortForm
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    default_return_url = 'dcim:device_list'


class DeviceBulkAddConsoleServerPortView(PermissionRequiredMixin, BulkComponentCreateView):
    permission_required = 'dcim.add_consoleserverport'
    parent_model = Device
    parent_field = 'device'
    form = forms.DeviceBulkAddComponentForm
    model = ConsoleServerPort
    model_form = forms.ConsoleServerPortForm
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    default_return_url = 'dcim:device_list'


class DeviceBulkAddPowerPortView(PermissionRequiredMixin, BulkComponentCreateView):
    permission_required = 'dcim.add_powerport'
    parent_model = Device
    parent_field = 'device'
    form = forms.DeviceBulkAddComponentForm
    model = PowerPort
    model_form = forms.PowerPortForm
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    default_return_url = 'dcim:device_list'


class DeviceBulkAddPowerOutletView(PermissionRequiredMixin, BulkComponentCreateView):
    permission_required = 'dcim.add_poweroutlet'
    parent_model = Device
    parent_field = 'device'
    form = forms.DeviceBulkAddComponentForm
    model = PowerOutlet
    model_form = forms.PowerOutletForm
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    default_return_url = 'dcim:device_list'


class DeviceBulkAddInterfaceView(PermissionRequiredMixin, BulkComponentCreateView):
    permission_required = 'dcim.add_interface'
    parent_model = Device
    parent_field = 'device'
    form = forms.DeviceBulkAddInterfaceForm
    model = Interface
    model_form = forms.InterfaceForm
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    default_return_url = 'dcim:device_list'


class DeviceBulkAddDeviceBayView(PermissionRequiredMixin, BulkComponentCreateView):
    permission_required = 'dcim.add_devicebay'
    parent_model = Device
    parent_field = 'device'
    form = forms.DeviceBulkAddComponentForm
    model = DeviceBay
    model_form = forms.DeviceBayForm
    filter = filters.DeviceFilter
    table = tables.DeviceTable
    default_return_url = 'dcim:device_list'


#
# Cables
#

class CableListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_cable'
    queryset = Cable.objects.prefetch_related(
        'termination_a', 'termination_b'
    )
    filter = filters.CableFilter
    filter_form = forms.CableFilterForm
    table = tables.CableTable
    template_name = 'dcim/cable_list.html'


class CableView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_cable'

    def get(self, request, pk):

        cable = get_object_or_404(Cable, pk=pk)

        return render(request, 'dcim/cable.html', {
            'cable': cable,
        })


class CableTraceView(PermissionRequiredMixin, View):
    """
    Trace a cable path beginning from the given termination.
    """
    permission_required = 'dcim.view_cable'

    def get(self, request, model, pk):

        obj = get_object_or_404(model, pk=pk)

        return render(request, 'dcim/cable_trace.html', {
            'obj': obj,
            'trace': obj.trace(follow_circuits=True),
        })


class CableCreateView(PermissionRequiredMixin, GetReturnURLMixin, View):
    permission_required = 'dcim.add_cable'
    template_name = 'dcim/cable_connect.html'

    def dispatch(self, request, *args, **kwargs):

        termination_a_type = kwargs.get('termination_a_type')
        termination_a_id = kwargs.get('termination_a_id')

        termination_b_type_name = kwargs.get('termination_b_type')
        self.termination_b_type = ContentType.objects.get(model=termination_b_type_name.replace('-', ''))

        self.obj = Cable(
            termination_a=termination_a_type.objects.get(pk=termination_a_id),
            termination_b_type=self.termination_b_type
        )
        self.form_class = {
            'console-port': forms.ConnectCableToConsolePortForm,
            'console-server-port': forms.ConnectCableToConsoleServerPortForm,
            'power-port': forms.ConnectCableToPowerPortForm,
            'power-outlet': forms.ConnectCableToPowerOutletForm,
            'interface': forms.ConnectCableToInterfaceForm,
            'front-port': forms.ConnectCableToFrontPortForm,
            'rear-port': forms.ConnectCableToRearPortForm,
            'power-feed': forms.ConnectCableToPowerFeedForm,
            'circuit-termination': forms.ConnectCableToCircuitTerminationForm,
        }[termination_b_type_name]

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):

        # Parse initial data manually to avoid setting field values as lists
        initial_data = {k: request.GET[k] for k in request.GET}

        form = self.form_class(instance=self.obj, initial=initial_data)

        return render(request, self.template_name, {
            'obj': self.obj,
            'obj_type': Cable._meta.verbose_name,
            'termination_b_type': self.termination_b_type.name,
            'form': form,
            'return_url': self.get_return_url(request, self.obj),
        })

    def post(self, request, *args, **kwargs):

        form = self.form_class(request.POST, request.FILES, instance=self.obj)

        if form.is_valid():
            obj = form.save()

            msg = 'Created cable <a href="{}">{}</a>'.format(
                obj.get_absolute_url(),
                escape(obj)
            )
            messages.success(request, mark_safe(msg))

            if '_addanother' in request.POST:
                return redirect(request.get_full_path())

            return_url = form.cleaned_data.get('return_url')
            if return_url is not None and is_safe_url(url=return_url, allowed_hosts=request.get_host()):
                return redirect(return_url)
            else:
                return redirect(self.get_return_url(request, obj))

        return render(request, self.template_name, {
            'obj': self.obj,
            'obj_type': Cable._meta.verbose_name,
            'termination_b_type': self.termination_b_type.name,
            'form': form,
            'return_url': self.get_return_url(request, self.obj),
        })


class CableEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_cable'
    model = Cable
    model_form = forms.CableForm
    template_name = 'dcim/cable_edit.html'
    default_return_url = 'dcim:cable_list'


class CableDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_cable'
    model = Cable
    default_return_url = 'dcim:cable_list'


class CableBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_cable'
    model_form = forms.CableCSVForm
    table = tables.CableTable
    default_return_url = 'dcim:cable_list'


class CableBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_cable'
    queryset = Cable.objects.prefetch_related('termination_a', 'termination_b')
    filter = filters.CableFilter
    table = tables.CableTable
    form = forms.CableBulkEditForm
    default_return_url = 'dcim:cable_list'


class CableBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_cable'
    queryset = Cable.objects.prefetch_related('termination_a', 'termination_b')
    filter = filters.CableFilter
    table = tables.CableTable
    default_return_url = 'dcim:cable_list'


#
# Connections
#

class ConsoleConnectionsListView(PermissionRequiredMixin, ObjectListView):
    permission_required = ('dcim.view_consoleport', 'dcim.view_consoleserverport')
    queryset = ConsolePort.objects.select_related(
        'device', 'connected_endpoint__device'
    ).filter(
        connected_endpoint__isnull=False
    ).order_by(
        'cable', 'connected_endpoint__device__name', 'connected_endpoint__name'
    )
    filter = filters.ConsoleConnectionFilter
    filter_form = forms.ConsoleConnectionFilterForm
    table = tables.ConsoleConnectionTable
    template_name = 'dcim/console_connections_list.html'

    def queryset_to_csv(self):
        csv_data = [
            # Headers
            ','.join(['console_server', 'port', 'device', 'console_port', 'connection_status'])
        ]
        for obj in self.queryset:
            csv = csv_format([
                obj.connected_endpoint.device.identifier if obj.connected_endpoint else None,
                obj.connected_endpoint.name if obj.connected_endpoint else None,
                obj.device.identifier,
                obj.name,
                obj.get_connection_status_display(),
            ])
            csv_data.append(csv)
        return csv_data


class PowerConnectionsListView(PermissionRequiredMixin, ObjectListView):
    permission_required = ('dcim.view_powerport', 'dcim.view_poweroutlet')
    queryset = PowerPort.objects.select_related(
        'device', '_connected_poweroutlet__device'
    ).filter(
        _connected_poweroutlet__isnull=False
    ).order_by(
        'cable', '_connected_poweroutlet__device__name', '_connected_poweroutlet__name'
    )
    filter = filters.PowerConnectionFilter
    filter_form = forms.PowerConnectionFilterForm
    table = tables.PowerConnectionTable
    template_name = 'dcim/power_connections_list.html'

    def queryset_to_csv(self):
        csv_data = [
            # Headers
            ','.join(['pdu', 'outlet', 'device', 'power_port', 'connection_status'])
        ]
        for obj in self.queryset:
            csv = csv_format([
                obj.connected_endpoint.device.identifier if obj.connected_endpoint else None,
                obj.connected_endpoint.name if obj.connected_endpoint else None,
                obj.device.identifier,
                obj.name,
                obj.get_connection_status_display(),
            ])
            csv_data.append(csv)
        return csv_data


class InterfaceConnectionsListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_interface'
    queryset = Interface.objects.select_related(
        'device', 'cable', '_connected_interface__device'
    ).filter(
        # Avoid duplicate connections by only selecting the lower PK in a connected pair
        _connected_interface__isnull=False,
        pk__lt=F('_connected_interface')
    ).order_by(
        'device'
    )
    filter = filters.InterfaceConnectionFilter
    filter_form = forms.InterfaceConnectionFilterForm
    table = tables.InterfaceConnectionTable
    template_name = 'dcim/interface_connections_list.html'

    def queryset_to_csv(self):
        csv_data = [
            # Headers
            ','.join([
                'device_a', 'interface_a', 'interface_a_description',
                'device_b', 'interface_b', 'interface_b_description',
                'connection_status'
            ])
        ]
        for obj in self.queryset:
            csv = csv_format([
                obj.connected_endpoint.device.identifier if obj.connected_endpoint else None,
                obj.connected_endpoint.name if obj.connected_endpoint else None,
                obj.connected_endpoint.description if obj.connected_endpoint else None,
                obj.device.identifier,
                obj.name,
                obj.description,
                obj.get_connection_status_display(),
            ])
            csv_data.append(csv)
        return csv_data


#
# Inventory items
#

class InventoryItemListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_inventoryitem'
    queryset = InventoryItem.objects.select_related('device', 'manufacturer')
    filter = filters.InventoryItemFilter
    filter_form = forms.InventoryItemFilterForm
    table = tables.InventoryItemTable
    template_name = 'dcim/inventoryitem_list.html'


class InventoryItemEditView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.change_inventoryitem'
    model = InventoryItem
    model_form = forms.InventoryItemForm

    def alter_obj(self, obj, request, url_args, url_kwargs):
        if 'device' in url_kwargs:
            obj.device = get_object_or_404(Device, pk=url_kwargs['device'])
        return obj

    def get_return_url(self, request, obj):
        return reverse('dcim:device_inventory', kwargs={'pk': obj.device.pk})


class InventoryItemDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_inventoryitem'
    model = InventoryItem


class InventoryItemBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_inventoryitem'
    model_form = forms.InventoryItemCSVForm
    table = tables.InventoryItemTable
    default_return_url = 'dcim:inventoryitem_list'


class InventoryItemBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_inventoryitem'
    queryset = InventoryItem.objects.select_related('device', 'manufacturer')
    filter = filters.InventoryItemFilter
    table = tables.InventoryItemTable
    form = forms.InventoryItemBulkEditForm
    default_return_url = 'dcim:inventoryitem_list'


class InventoryItemBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_inventoryitem'
    queryset = InventoryItem.objects.select_related('device', 'manufacturer')
    table = tables.InventoryItemTable
    template_name = 'dcim/inventoryitem_bulk_delete.html'
    default_return_url = 'dcim:inventoryitem_list'


#
# Virtual chassis
#

class VirtualChassisListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_virtualchassis'
    queryset = VirtualChassis.objects.select_related('master').annotate(member_count=Count('members'))
    table = tables.VirtualChassisTable
    filter = filters.VirtualChassisFilter
    filter_form = forms.VirtualChassisFilterForm
    template_name = 'dcim/virtualchassis_list.html'


class VirtualChassisCreateView(PermissionRequiredMixin, View):
    permission_required = 'dcim.add_virtualchassis'

    def post(self, request):

        # Get the list of devices being added to a VirtualChassis
        pk_form = forms.DeviceSelectionForm(request.POST)
        pk_form.full_clean()
        if not pk_form.cleaned_data.get('pk'):
            messages.warning(request, "No devices were selected.")
            return redirect('dcim:device_list')
        device_queryset = Device.objects.filter(
            pk__in=pk_form.cleaned_data.get('pk')
        ).select_related('rack').order_by('vc_position')

        VCMemberFormSet = modelformset_factory(
            model=Device,
            formset=forms.BaseVCMemberFormSet,
            form=forms.DeviceVCMembershipForm,
            extra=0
        )

        if '_create' in request.POST:

            vc_form = forms.VirtualChassisForm(request.POST)
            vc_form.fields['master'].queryset = device_queryset
            formset = VCMemberFormSet(request.POST, queryset=device_queryset)

            if vc_form.is_valid() and formset.is_valid():

                with transaction.atomic():

                    # Assign each device to the VirtualChassis before saving
                    virtual_chassis = vc_form.save()
                    devices = formset.save(commit=False)
                    for device in devices:
                        device.virtual_chassis = virtual_chassis
                        device.save()

                return redirect(vc_form.cleaned_data['master'].get_absolute_url())

        else:

            vc_form = forms.VirtualChassisForm()
            vc_form.fields['master'].queryset = device_queryset
            formset = VCMemberFormSet(queryset=device_queryset)

        return render(request, 'dcim/virtualchassis_edit.html', {
            'pk_form': pk_form,
            'vc_form': vc_form,
            'formset': formset,
            'return_url': reverse('dcim:device_list'),
        })


class VirtualChassisEditView(PermissionRequiredMixin, GetReturnURLMixin, View):
    permission_required = 'dcim.change_virtualchassis'

    def get(self, request, pk):

        virtual_chassis = get_object_or_404(VirtualChassis, pk=pk)
        VCMemberFormSet = modelformset_factory(
            model=Device,
            form=forms.DeviceVCMembershipForm,
            formset=forms.BaseVCMemberFormSet,
            extra=0
        )
        members_queryset = virtual_chassis.members.select_related('rack').order_by('vc_position')

        vc_form = forms.VirtualChassisForm(instance=virtual_chassis)
        vc_form.fields['master'].queryset = members_queryset
        formset = VCMemberFormSet(queryset=members_queryset)

        return render(request, 'dcim/virtualchassis_edit.html', {
            'vc_form': vc_form,
            'formset': formset,
            'return_url': self.get_return_url(request, virtual_chassis),
        })

    def post(self, request, pk):

        virtual_chassis = get_object_or_404(VirtualChassis, pk=pk)
        VCMemberFormSet = modelformset_factory(
            model=Device,
            form=forms.DeviceVCMembershipForm,
            formset=forms.BaseVCMemberFormSet,
            extra=0
        )
        members_queryset = virtual_chassis.members.select_related('rack').order_by('vc_position')

        vc_form = forms.VirtualChassisForm(request.POST, instance=virtual_chassis)
        vc_form.fields['master'].queryset = members_queryset
        formset = VCMemberFormSet(request.POST, queryset=members_queryset)

        if vc_form.is_valid() and formset.is_valid():

            with transaction.atomic():

                # Save the VirtualChassis
                vc_form.save()

                # Nullify the vc_position of each member first to allow reordering without raising an IntegrityError on
                # duplicate positions. Then save each member instance.
                members = formset.save(commit=False)
                Device.objects.filter(pk__in=[m.pk for m in members]).update(vc_position=None)
                for member in members:
                    member.save()

            return redirect(vc_form.cleaned_data['master'].get_absolute_url())

        return render(request, 'dcim/virtualchassis_edit.html', {
            'vc_form': vc_form,
            'formset': formset,
            'return_url': self.get_return_url(request, virtual_chassis),
        })


class VirtualChassisDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_virtualchassis'
    model = VirtualChassis
    default_return_url = 'dcim:device_list'


class VirtualChassisAddMemberView(PermissionRequiredMixin, GetReturnURLMixin, View):
    permission_required = 'dcim.change_virtualchassis'

    def get(self, request, pk):

        virtual_chassis = get_object_or_404(VirtualChassis, pk=pk)

        initial_data = {k: request.GET[k] for k in request.GET}
        member_select_form = forms.VCMemberSelectForm(initial=initial_data)
        membership_form = forms.DeviceVCMembershipForm(initial=initial_data)

        return render(request, 'dcim/virtualchassis_add_member.html', {
            'virtual_chassis': virtual_chassis,
            'member_select_form': member_select_form,
            'membership_form': membership_form,
            'return_url': self.get_return_url(request, virtual_chassis),
        })

    def post(self, request, pk):

        virtual_chassis = get_object_or_404(VirtualChassis, pk=pk)

        member_select_form = forms.VCMemberSelectForm(request.POST)

        if member_select_form.is_valid():

            device = member_select_form.cleaned_data['device']
            device.virtual_chassis = virtual_chassis
            data = {k: request.POST[k] for k in ['vc_position', 'vc_priority']}
            membership_form = forms.DeviceVCMembershipForm(data=data, validate_vc_position=True, instance=device)

            if membership_form.is_valid():

                membership_form.save()
                msg = 'Added member <a href="{}">{}</a>'.format(device.get_absolute_url(), escape(device))
                messages.success(request, mark_safe(msg))

                if '_addanother' in request.POST:
                    return redirect(request.get_full_path())

                return redirect(self.get_return_url(request, device))

        else:

            membership_form = forms.DeviceVCMembershipForm(data=request.POST)

        return render(request, 'dcim/virtualchassis_add_member.html', {
            'virtual_chassis': virtual_chassis,
            'member_select_form': member_select_form,
            'membership_form': membership_form,
            'return_url': self.get_return_url(request, virtual_chassis),
        })


class VirtualChassisRemoveMemberView(PermissionRequiredMixin, GetReturnURLMixin, View):
    permission_required = 'dcim.change_virtualchassis'

    def get(self, request, pk):

        device = get_object_or_404(Device, pk=pk, virtual_chassis__isnull=False)
        form = ConfirmationForm(initial=request.GET)

        return render(request, 'dcim/virtualchassis_remove_member.html', {
            'device': device,
            'form': form,
            'return_url': self.get_return_url(request, device),
        })

    def post(self, request, pk):

        device = get_object_or_404(Device, pk=pk, virtual_chassis__isnull=False)
        form = ConfirmationForm(request.POST)

        # Protect master device from being removed
        virtual_chassis = VirtualChassis.objects.filter(master=device).first()
        if virtual_chassis is not None:
            msg = 'Unable to remove master device {} from the virtual chassis.'.format(escape(device))
            messages.error(request, mark_safe(msg))
            return redirect(device.get_absolute_url())

        if form.is_valid():

            Device.objects.filter(pk=device.pk).update(
                virtual_chassis=None,
                vc_position=None,
                vc_priority=None
            )

            msg = 'Removed {} from virtual chassis {}'.format(device, device.virtual_chassis)
            messages.success(request, msg)

            return redirect(self.get_return_url(request, device))

        return render(request, 'dcim/virtualchassis_remove_member.html', {
            'device': device,
            'form': form,
            'return_url': self.get_return_url(request, device),
        })


#
# Power panels
#

class PowerPanelListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_powerpanel'
    queryset = PowerPanel.objects.select_related(
        'site', 'rack_group'
    ).annotate(
        powerfeed_count=Count('powerfeeds')
    )
    filter = filters.PowerPanelFilter
    filter_form = forms.PowerPanelFilterForm
    table = tables.PowerPanelTable
    template_name = 'dcim/powerpanel_list.html'


class PowerPanelView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_powerpanel'

    def get(self, request, pk):

        powerpanel = get_object_or_404(PowerPanel.objects.select_related('site', 'rack_group'), pk=pk)
        powerfeed_table = tables.PowerFeedTable(
            data=PowerFeed.objects.filter(power_panel=powerpanel).select_related('rack'),
            orderable=False
        )
        powerfeed_table.exclude = ['power_panel']

        return render(request, 'dcim/powerpanel.html', {
            'powerpanel': powerpanel,
            'powerfeed_table': powerfeed_table,
        })


class PowerPanelCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_powerpanel'
    model = PowerPanel
    model_form = forms.PowerPanelForm
    default_return_url = 'dcim:powerpanel_list'


class PowerPanelEditView(PowerPanelCreateView):
    permission_required = 'dcim.change_powerpanel'


class PowerPanelDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_powerpanel'
    model = PowerPanel
    default_return_url = 'dcim:powerpanel_list'


class PowerPanelBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_powerpanel'
    model_form = forms.PowerPanelCSVForm
    table = tables.PowerPanelTable
    default_return_url = 'dcim:powerpanel_list'


class PowerPanelBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_powerpanel'
    queryset = PowerPanel.objects.select_related(
        'site', 'rack_group'
    ).annotate(
        rack_count=Count('powerfeeds')
    )
    filter = filters.PowerPanelFilter
    table = tables.PowerPanelTable
    default_return_url = 'dcim:powerpanel_list'


#
# Power feeds
#

class PowerFeedListView(PermissionRequiredMixin, ObjectListView):
    permission_required = 'dcim.view_powerfeed'
    queryset = PowerFeed.objects.select_related(
        'power_panel', 'rack'
    )
    filter = filters.PowerFeedFilter
    filter_form = forms.PowerFeedFilterForm
    table = tables.PowerFeedTable
    template_name = 'dcim/powerfeed_list.html'


class PowerFeedView(PermissionRequiredMixin, View):
    permission_required = 'dcim.view_powerfeed'

    def get(self, request, pk):

        powerfeed = get_object_or_404(PowerFeed.objects.select_related('power_panel', 'rack'), pk=pk)

        return render(request, 'dcim/powerfeed.html', {
            'powerfeed': powerfeed,
        })


class PowerFeedCreateView(PermissionRequiredMixin, ObjectEditView):
    permission_required = 'dcim.add_powerfeed'
    model = PowerFeed
    model_form = forms.PowerFeedForm
    template_name = 'dcim/powerfeed_edit.html'
    default_return_url = 'dcim:powerfeed_list'


class PowerFeedEditView(PowerFeedCreateView):
    permission_required = 'dcim.change_powerfeed'


class PowerFeedDeleteView(PermissionRequiredMixin, ObjectDeleteView):
    permission_required = 'dcim.delete_powerfeed'
    model = PowerFeed
    default_return_url = 'dcim:powerfeed_list'


class PowerFeedBulkImportView(PermissionRequiredMixin, BulkImportView):
    permission_required = 'dcim.add_powerfeed'
    model_form = forms.PowerFeedCSVForm
    table = tables.PowerFeedTable
    default_return_url = 'dcim:powerfeed_list'


class PowerFeedBulkEditView(PermissionRequiredMixin, BulkEditView):
    permission_required = 'dcim.change_powerfeed'
    queryset = PowerFeed.objects.select_related('power_panel', 'rack')
    filter = filters.PowerFeedFilter
    table = tables.PowerFeedTable
    form = forms.PowerFeedBulkEditForm
    default_return_url = 'dcim:powerfeed_list'


class PowerFeedBulkDeleteView(PermissionRequiredMixin, BulkDeleteView):
    permission_required = 'dcim.delete_powerfeed'
    queryset = PowerFeed.objects.select_related('power_panel', 'rack')
    filter = filters.PowerFeedFilter
    table = tables.PowerFeedTable
    default_return_url = 'dcim:powerfeed_list'

from django.db.models import Count

from dcim.models import Device, Interface
from extras.api.views import CustomFieldModelViewSet
from utilities.api import FieldChoicesViewSet, ModelViewSet
from utilities.utils import get_subquery
from virtualization import filters
from virtualization.models import Cluster, ClusterGroup, ClusterType, VirtualMachine
from . import serializers


#
# Field choices
#

class VirtualizationFieldChoicesViewSet(FieldChoicesViewSet):
    fields = (
        (VirtualMachine, ['status']),
    )


#
# Clusters
#

class ClusterTypeViewSet(ModelViewSet):
    queryset = ClusterType.objects.annotate(
        cluster_count=Count('clusters')
    )
    serializer_class = serializers.ClusterTypeSerializer
    filterset_class = filters.ClusterTypeFilter


class ClusterGroupViewSet(ModelViewSet):
    queryset = ClusterGroup.objects.annotate(
        cluster_count=Count('clusters')
    )
    serializer_class = serializers.ClusterGroupSerializer
    filterset_class = filters.ClusterGroupFilter


class ClusterViewSet(CustomFieldModelViewSet):
    queryset = Cluster.objects.select_related(
        'type', 'group', 'site',
    ).prefetch_related(
        'tags'
    ).annotate(
        device_count=get_subquery(Device, 'cluster'),
        virtualmachine_count=get_subquery(VirtualMachine, 'cluster')
    )
    serializer_class = serializers.ClusterSerializer
    filterset_class = filters.ClusterFilter


#
# Virtual machines
#

class VirtualMachineViewSet(CustomFieldModelViewSet):
    queryset = VirtualMachine.objects.select_related(
        'cluster__site', 'role', 'tenant', 'platform', 'primary_ip4', 'primary_ip6'
    ).prefetch_related('tags')
    filterset_class = filters.VirtualMachineFilter

    def get_serializer_class(self):
        """
        Select the specific serializer based on the request context.

        If the `brief` query param equates to True, return the NestedVirtualMachineSerializer

        If the `exclude` query param includes `config_context` as a value, return the VirtualMachineSerializer

        Else, return the VirtualMachineWithConfigContextSerializer
        """

        request = self.get_serializer_context()['request']
        if request.query_params.get('brief', False):
            return serializers.NestedVirtualMachineSerializer

        elif 'config_context' in request.query_params.get('exclude', []):
            return serializers.VirtualMachineSerializer

        return serializers.VirtualMachineWithConfigContextSerializer


class InterfaceViewSet(ModelViewSet):
    queryset = Interface.objects.filter(
        virtual_machine__isnull=False
    ).select_related('virtual_machine').prefetch_related('tags')
    serializer_class = serializers.InterfaceSerializer
    filterset_class = filters.InterfaceFilter

    def get_serializer_class(self):
        request = self.get_serializer_context()['request']
        if request.query_params.get('brief', False):
            # Override get_serializer_for_model(), which will return the DCIM NestedInterfaceSerializer
            return serializers.NestedInterfaceSerializer
        return serializers.InterfaceSerializer

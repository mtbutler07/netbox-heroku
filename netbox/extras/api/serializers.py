from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from drf_yasg.utils import swagger_serializer_method
from rest_framework import serializers

from dcim.api.nested_serializers import (
    NestedDeviceSerializer, NestedDeviceRoleSerializer, NestedPlatformSerializer, NestedRackSerializer,
    NestedRegionSerializer, NestedSiteSerializer,
)
from dcim.models import Device, DeviceRole, Platform, Rack, Region, Site
from extras.constants import *
from extras.models import (
    ConfigContext, ExportTemplate, Graph, ImageAttachment, ObjectChange, ReportResult, TopologyMap,
    Tag
)
from tenancy.api.nested_serializers import NestedTenantSerializer, NestedTenantGroupSerializer
from tenancy.models import Tenant, TenantGroup
from users.api.nested_serializers import NestedUserSerializer
from utilities.api import (
    ChoiceField, ContentTypeField, get_serializer_for_model, SerializerNotFound, SerializedPKRelatedField,
    ValidatedModelSerializer,
)
from .nested_serializers import *


#
# Graphs
#

class GraphSerializer(ValidatedModelSerializer):
    type = ChoiceField(choices=GRAPH_TYPE_CHOICES)

    class Meta:
        model = Graph
        fields = ['id', 'type', 'weight', 'name', 'source', 'link']


class RenderedGraphSerializer(serializers.ModelSerializer):
    embed_url = serializers.SerializerMethodField()
    embed_link = serializers.SerializerMethodField()
    type = ChoiceField(choices=GRAPH_TYPE_CHOICES)

    class Meta:
        model = Graph
        fields = ['id', 'type', 'weight', 'name', 'embed_url', 'embed_link']

    def get_embed_url(self, obj):
        return obj.embed_url(self.context['graphed_object'])

    def get_embed_link(self, obj):
        return obj.embed_link(self.context['graphed_object'])


#
# Export templates
#

class ExportTemplateSerializer(ValidatedModelSerializer):
    template_language = ChoiceField(
        choices=TEMPLATE_LANGUAGE_CHOICES,
        default=TEMPLATE_LANGUAGE_JINJA2
    )

    class Meta:
        model = ExportTemplate
        fields = [
            'id', 'content_type', 'name', 'description', 'template_language', 'template_code', 'mime_type',
            'file_extension',
        ]


#
# Topology maps
#

class TopologyMapSerializer(ValidatedModelSerializer):
    site = NestedSiteSerializer()

    class Meta:
        model = TopologyMap
        fields = ['id', 'name', 'slug', 'site', 'device_patterns', 'description']


#
# Tags
#

class TagSerializer(ValidatedModelSerializer):
    tagged_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'color', 'comments', 'tagged_items']


#
# Image attachments
#

class ImageAttachmentSerializer(ValidatedModelSerializer):
    content_type = ContentTypeField(
        queryset=ContentType.objects.all()
    )
    parent = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ImageAttachment
        fields = [
            'id', 'content_type', 'object_id', 'parent', 'name', 'image', 'image_height', 'image_width', 'created',
        ]

    def validate(self, data):

        # Validate that the parent object exists
        try:
            data['content_type'].get_object_for_this_type(id=data['object_id'])
        except ObjectDoesNotExist:
            raise serializers.ValidationError(
                "Invalid parent object: {} ID {}".format(data['content_type'], data['object_id'])
            )

        # Enforce model validation
        super().validate(data)

        return data

    @swagger_serializer_method(serializer_or_field=serializers.DictField)
    def get_parent(self, obj):

        # Static mapping of models to their nested serializers
        if isinstance(obj.parent, Device):
            serializer = NestedDeviceSerializer
        elif isinstance(obj.parent, Rack):
            serializer = NestedRackSerializer
        elif isinstance(obj.parent, Site):
            serializer = NestedSiteSerializer
        else:
            raise Exception("Unexpected type of parent object for ImageAttachment")

        return serializer(obj.parent, context={'request': self.context['request']}).data


#
# Config contexts
#

class ConfigContextSerializer(ValidatedModelSerializer):
    regions = SerializedPKRelatedField(
        queryset=Region.objects.all(),
        serializer=NestedRegionSerializer,
        required=False,
        many=True
    )
    sites = SerializedPKRelatedField(
        queryset=Site.objects.all(),
        serializer=NestedSiteSerializer,
        required=False,
        many=True
    )
    roles = SerializedPKRelatedField(
        queryset=DeviceRole.objects.all(),
        serializer=NestedDeviceRoleSerializer,
        required=False,
        many=True
    )
    platforms = SerializedPKRelatedField(
        queryset=Platform.objects.all(),
        serializer=NestedPlatformSerializer,
        required=False,
        many=True
    )
    tenant_groups = SerializedPKRelatedField(
        queryset=TenantGroup.objects.all(),
        serializer=NestedTenantGroupSerializer,
        required=False,
        many=True
    )
    tenants = SerializedPKRelatedField(
        queryset=Tenant.objects.all(),
        serializer=NestedTenantSerializer,
        required=False,
        many=True
    )

    class Meta:
        model = ConfigContext
        fields = [
            'id', 'name', 'weight', 'description', 'is_active', 'regions', 'sites', 'roles', 'platforms',
            'tenant_groups', 'tenants', 'data',
        ]


#
# Reports
#

class ReportResultSerializer(serializers.ModelSerializer):

    class Meta:
        model = ReportResult
        fields = ['created', 'user', 'failed', 'data']


class ReportSerializer(serializers.Serializer):
    module = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(max_length=255, required=False)
    test_methods = serializers.ListField(child=serializers.CharField(max_length=255))
    result = NestedReportResultSerializer()


class ReportDetailSerializer(ReportSerializer):
    result = ReportResultSerializer()


#
# Change logging
#

class ObjectChangeSerializer(serializers.ModelSerializer):
    user = NestedUserSerializer(
        read_only=True
    )
    action = ChoiceField(
        choices=OBJECTCHANGE_ACTION_CHOICES,
        read_only=True
    )
    changed_object_type = ContentTypeField(
        read_only=True
    )
    changed_object = serializers.SerializerMethodField(
        read_only=True
    )

    class Meta:
        model = ObjectChange
        fields = [
            'id', 'time', 'user', 'user_name', 'request_id', 'action', 'changed_object_type', 'changed_object',
            'object_data',
        ]

    @swagger_serializer_method(serializer_or_field=serializers.DictField)
    def get_changed_object(self, obj):
        """
        Serialize a nested representation of the changed object.
        """
        if obj.changed_object is None:
            return None

        try:
            serializer = get_serializer_for_model(obj.changed_object, prefix='Nested')
        except SerializerNotFound:
            return obj.object_repr
        context = {
            'request': self.context['request']
        }
        data = serializer(obj.changed_object, context=context).data

        return data

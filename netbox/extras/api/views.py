from collections import OrderedDict

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet, ViewSet

from extras import filters
from extras.models import (
    ConfigContext, CustomFieldChoice, ExportTemplate, Graph, ImageAttachment, ObjectChange, ReportResult, TopologyMap,
    Tag,
)
from extras.reports import get_report, get_reports
from utilities.api import FieldChoicesViewSet, IsAuthenticatedOrLoginNotRequired, ModelViewSet
from . import serializers


#
# Field choices
#

class ExtrasFieldChoicesViewSet(FieldChoicesViewSet):
    fields = (
        (ExportTemplate, ['template_language']),
        (Graph, ['type']),
        (ObjectChange, ['action']),
    )


#
# Custom field choices
#

class CustomFieldChoicesViewSet(ViewSet):
    """
    """
    permission_classes = [IsAuthenticatedOrLoginNotRequired]

    def __init__(self, *args, **kwargs):
        super(CustomFieldChoicesViewSet, self).__init__(*args, **kwargs)

        self._fields = OrderedDict()

        for cfc in CustomFieldChoice.objects.all():
            self._fields.setdefault(cfc.field.name, {})
            self._fields[cfc.field.name][cfc.value] = cfc.pk

    def list(self, request):
        return Response(self._fields)

    def retrieve(self, request, pk):
        if pk not in self._fields:
            raise Http404
        return Response(self._fields[pk])

    def get_view_name(self):
        return "Custom Field choices"


#
# Custom fields
#

class CustomFieldModelViewSet(ModelViewSet):
    """
    Include the applicable set of CustomFields in the ModelViewSet context.
    """

    def get_serializer_context(self):

        # Gather all custom fields for the model
        content_type = ContentType.objects.get_for_model(self.queryset.model)
        custom_fields = content_type.custom_fields.prefetch_related('choices')

        # Cache all relevant CustomFieldChoices. This saves us from having to do a lookup per select field per object.
        custom_field_choices = {}
        for field in custom_fields:
            for cfc in field.choices.all():
                custom_field_choices[cfc.id] = cfc.value
        custom_field_choices = custom_field_choices

        context = super().get_serializer_context()
        context.update({
            'custom_fields': custom_fields,
            'custom_field_choices': custom_field_choices,
        })
        return context

    def get_queryset(self):
        # Prefetch custom field values
        return super().get_queryset().prefetch_related('custom_field_values__field')


#
# Graphs
#

class GraphViewSet(ModelViewSet):
    queryset = Graph.objects.all()
    serializer_class = serializers.GraphSerializer
    filterset_class = filters.GraphFilter


#
# Export templates
#

class ExportTemplateViewSet(ModelViewSet):
    queryset = ExportTemplate.objects.all()
    serializer_class = serializers.ExportTemplateSerializer
    filterset_class = filters.ExportTemplateFilter


#
# Topology maps
#

class TopologyMapViewSet(ModelViewSet):
    queryset = TopologyMap.objects.select_related('site')
    serializer_class = serializers.TopologyMapSerializer
    filterset_class = filters.TopologyMapFilter

    @action(detail=True)
    def render(self, request, pk):

        tmap = get_object_or_404(TopologyMap, pk=pk)
        img_format = 'png'

        try:
            data = tmap.render(img_format=img_format)
        except Exception as e:
            return HttpResponse(
                "There was an error generating the requested graph: %s" % e
            )

        response = HttpResponse(data, content_type='image/{}'.format(img_format))
        response['Content-Disposition'] = 'inline; filename="{}.{}"'.format(tmap.slug, img_format)

        return response


#
# Tags
#

class TagViewSet(ModelViewSet):
    queryset = Tag.objects.annotate(
        tagged_items=Count('extras_taggeditem_items', distinct=True)
    )
    serializer_class = serializers.TagSerializer
    filterset_class = filters.TagFilter


#
# Image attachments
#

class ImageAttachmentViewSet(ModelViewSet):
    queryset = ImageAttachment.objects.all()
    serializer_class = serializers.ImageAttachmentSerializer


#
# Config contexts
#

class ConfigContextViewSet(ModelViewSet):
    queryset = ConfigContext.objects.prefetch_related(
        'regions', 'sites', 'roles', 'platforms', 'tenant_groups', 'tenants',
    )
    serializer_class = serializers.ConfigContextSerializer
    filterset_class = filters.ConfigContextFilter


#
# Reports
#

class ReportViewSet(ViewSet):
    permission_classes = [IsAuthenticatedOrLoginNotRequired]
    _ignore_model_permissions = True
    exclude_from_schema = True
    lookup_value_regex = '[^/]+'  # Allow dots

    def _retrieve_report(self, pk):

        # Read the PK as "<module>.<report>"
        if '.' not in pk:
            raise Http404
        module_name, report_name = pk.split('.', 1)

        # Raise a 404 on an invalid Report module/name
        report = get_report(module_name, report_name)
        if report is None:
            raise Http404

        return report

    def list(self, request):
        """
        Compile all reports and their related results (if any). Result data is deferred in the list view.
        """
        report_list = []

        # Iterate through all available Reports.
        for module_name, reports in get_reports():
            for report in reports:

                # Attach the relevant ReportResult (if any) to each Report.
                report.result = ReportResult.objects.filter(report=report.full_name).defer('data').first()
                report_list.append(report)

        serializer = serializers.ReportSerializer(report_list, many=True, context={
            'request': request,
        })

        return Response(serializer.data)

    def retrieve(self, request, pk):
        """
        Retrieve a single Report identified as "<module>.<report>".
        """

        # Retrieve the Report and ReportResult, if any.
        report = self._retrieve_report(pk)
        report.result = ReportResult.objects.filter(report=report.full_name).first()

        serializer = serializers.ReportDetailSerializer(report)

        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def run(self, request, pk):
        """
        Run a Report and create a new ReportResult, overwriting any previous result for the Report.
        """

        # Check that the user has permission to run reports.
        if not request.user.has_perm('extras.add_reportresult'):
            raise PermissionDenied("This user does not have permission to run reports.")

        # Retrieve and run the Report. This will create a new ReportResult.
        report = self._retrieve_report(pk)
        report.run()

        serializer = serializers.ReportDetailSerializer(report)

        return Response(serializer.data)


#
# Change logging
#

class ObjectChangeViewSet(ReadOnlyModelViewSet):
    """
    Retrieve a list of recent changes.
    """
    queryset = ObjectChange.objects.select_related('user')
    serializer_class = serializers.ObjectChangeSerializer
    filterset_class = filters.ObjectChangeFilter

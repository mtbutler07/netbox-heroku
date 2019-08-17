import django_filters
from django.db.models import Q

from dcim.models import Device
from extras.filters import CustomFieldFilterSet
from utilities.filters import NameSlugSearchFilterSet, NumericInFilter, TagFilter
from .models import Secret, SecretRole


class SecretRoleFilter(NameSlugSearchFilterSet):

    class Meta:
        model = SecretRole
        fields = ['id', 'name', 'slug']


class SecretFilter(CustomFieldFilterSet):
    id__in = NumericInFilter(
        field_name='id',
        lookup_expr='in'
    )
    q = django_filters.CharFilter(
        method='search',
        label='Search',
    )
    role_id = django_filters.ModelMultipleChoiceFilter(
        queryset=SecretRole.objects.all(),
        label='Role (ID)',
    )
    role = django_filters.ModelMultipleChoiceFilter(
        field_name='role__slug',
        queryset=SecretRole.objects.all(),
        to_field_name='slug',
        label='Role (slug)',
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Device.objects.all(),
        label='Device (ID)',
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name='device__name',
        queryset=Device.objects.all(),
        to_field_name='name',
        label='Device (name)',
    )
    tag = TagFilter()

    class Meta:
        model = Secret
        fields = ['name']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) |
            Q(device__name__icontains=value)
        )

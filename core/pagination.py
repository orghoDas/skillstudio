from rest_framework.pagination import PageNumberPagination


class SummaryPageNumberPagination(PageNumberPagination):
    """Page-number responses that include totals over the filtered collection."""

    summary_properties = {}

    def get_paginated_response_schema(self, schema):
        page = super().get_paginated_response_schema(schema)
        page['required'].append('summary')
        page['properties']['summary'] = {
            'type': 'object',
            'required': list(self.summary_properties),
            'properties': self.summary_properties,
        }
        return page

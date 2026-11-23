from rest_framework import serializers


def optional_id(params, name):
    """Validate an optional positive database identifier before querying."""
    if name not in params:
        return None
    try:
        return serializers.IntegerField(min_value=1, max_value=2**63 - 1).run_validation(params[name])
    except serializers.ValidationError as exc:
        raise serializers.ValidationError({name: exc.detail}) from exc

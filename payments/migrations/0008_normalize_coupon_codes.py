import django.db.models.functions.text
from django.db import migrations, models


def preserve_coupon_history(apps, schema_editor):
    alias = schema_editor.connection.alias
    coupons = apps.get_model('payments', 'Coupon').objects.using(alias)
    seen = {}
    changes = []
    collisions = set()
    for pk, code in coupons.values_list('pk', 'code').iterator():
        normalized = code.strip().upper()
        if not normalized or len(normalized) > 64:
            raise RuntimeError(f'Fix the invalid code for coupon ID {pk} before migrating.')
        if normalized in seen:
            collisions.update((seen[normalized], pk))
        else:
            seen[normalized] = pk
        if code != normalized:
            changes.append((pk, normalized))
    if collisions:
        raise RuntimeError(f'Resolve duplicate coupon codes for coupon IDs {sorted(collisions)} before migrating.')
    for pk, normalized in changes:
        coupons.filter(pk=pk).update(code=normalized)

    redemptions = apps.get_model('payments', 'CouponRedemption').objects.using(alias)
    for pk, course_id in redemptions.filter(payment__course__isnull=False).values_list(
        'pk', 'payment__course_id',
    ).iterator():
        redemptions.filter(pk=pk).update(course_id=course_id)


class Migration(migrations.Migration):
    dependencies = [('payments', '0007_couponredemption_course_and_more')]

    operations = [
        migrations.RunPython(preserve_coupon_history, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='coupon',
            constraint=models.UniqueConstraint(django.db.models.functions.text.Upper('code'), name='unique_coupon_code_case_insensitive'),
        ),
    ]

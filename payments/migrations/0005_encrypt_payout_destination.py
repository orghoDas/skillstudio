from django.db import migrations, models

from payments.payout_details import decrypt_payout_details, encrypt_payout_details


def encrypt_existing_details(apps, schema_editor):
    Payout = apps.get_model('payments', 'Payout')
    payouts = Payout.objects.using(schema_editor.connection.alias)
    for pk, details in payouts.values_list('pk', 'account_details').iterator():
        ciphertext = encrypt_payout_details(details)
        if ciphertext:
            payouts.filter(pk=pk).update(account_details_encrypted=ciphertext)


def restore_plaintext_details(apps, schema_editor):
    Payout = apps.get_model('payments', 'Payout')
    payouts = Payout.objects.using(schema_editor.connection.alias)
    for pk, ciphertext in payouts.exclude(account_details_encrypted='').values_list(
        'pk', 'account_details_encrypted',
    ).iterator():
        payouts.filter(pk=pk).update(account_details=decrypt_payout_details(ciphertext))


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0004_remove_paymentgatewayconfig'),
        ('instructors', '0003_move_payouts_to_wallet_ledger'),
    ]

    operations = [
        migrations.AddField(
            model_name='payout',
            name='account_details_encrypted',
            field=models.TextField(blank=True, default='', editable=False),
        ),
        migrations.RunPython(encrypt_existing_details, restore_plaintext_details),
        migrations.RemoveField(model_name='payout', name='account_details'),
    ]

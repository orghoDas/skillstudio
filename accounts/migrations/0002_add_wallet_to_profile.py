from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="wallet",
            field=models.DecimalField(default=0, max_digits=12, decimal_places=2, help_text="User wallet balance"),
        ),
    ]

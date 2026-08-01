from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("helpdesk", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="admin",
            name="role",
            field=models.CharField(
                choices=[
                    ("AD", "Administrator"),
                    ("HD", "Helpdesk"),
                    ("HL", "Helpdesk Lite"),
                    ("AB", "Address Book"),
                    ("PW", "Password"),
                ],
                default="HD",
                max_length=4,
            ),
        ),
        migrations.AlterField(
            model_name="gwsettings",
            name="gwPass",
            field=models.CharField(max_length=256),
        ),
    ]

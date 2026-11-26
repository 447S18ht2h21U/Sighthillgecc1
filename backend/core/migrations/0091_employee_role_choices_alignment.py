from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0090_distributor_invoice_foundation_5998'),
    ]

    operations = [
        migrations.AlterField(
            model_name='temporarydutyauthorization',
            name='permanent_role',
            field=models.CharField(choices=[('CEO', 'Chief Executive Officer'), ('MARKETING', 'Marketing'), ('SALES_ASSOCIATE', 'Sales Associate'), ('SALES_MANAGER', 'Sales Manager'), ('COMPTROLLER', 'Comptroller'), ('INSTALLATION_MANAGER', 'Installation Manager'), ('TECHNICIAN', 'Technician'), ('ACCOUNTS_PAYABLE_ASSOCIATE', 'Accounts Payable Associate'), ('DATABASE_ADMINISTRATOR', 'Database Administrator')], max_length=32),
        ),
        migrations.AlterField(
            model_name='temporarydutyauthorization',
            name='temporary_role',
            field=models.CharField(choices=[('CEO', 'Chief Executive Officer'), ('MARKETING', 'Marketing'), ('SALES_ASSOCIATE', 'Sales Associate'), ('SALES_MANAGER', 'Sales Manager'), ('COMPTROLLER', 'Comptroller'), ('INSTALLATION_MANAGER', 'Installation Manager'), ('TECHNICIAN', 'Technician'), ('ACCOUNTS_PAYABLE_ASSOCIATE', 'Accounts Payable Associate'), ('DATABASE_ADMINISTRATOR', 'Database Administrator')], max_length=32),
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('CEO', 'Chief Executive Officer'), ('MARKETING', 'Marketing'), ('SALES_ASSOCIATE', 'Sales Associate'), ('SALES_MANAGER', 'Sales Manager'), ('COMPTROLLER', 'Comptroller'), ('INSTALLATION_MANAGER', 'Installation Manager'), ('TECHNICIAN', 'Technician'), ('ACCOUNTS_PAYABLE_ASSOCIATE', 'Accounts Payable Associate'), ('DATABASE_ADMINISTRATOR', 'Database Administrator')], max_length=32),
        ),
    ]

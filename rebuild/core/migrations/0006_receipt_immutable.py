from django.db import migrations
class Migration(migrations.Migration):
    dependencies=[('core','0005_providerreceipt')]
    operations=[migrations.RunSQL('CREATE TRIGGER receipt_append_only BEFORE UPDATE OR DELETE ON core_providerreceipt FOR EACH ROW EXECUTE FUNCTION quillmd_append_only();','DROP TRIGGER receipt_append_only ON core_providerreceipt;')]

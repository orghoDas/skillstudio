from django.db import models
from django.conf import settings

# PostgreSQL Equivalent:
# CREATE TABLE audit_auditlog (
#     id SERIAL PRIMARY KEY,
#     actor_id INTEGER REFERENCES accounts_user(id) ON DELETE SET NULL,
#     action VARCHAR(255) NOT NULL,
#     entity VARCHAR(100),
#     entity_id VARCHAR(255),
#     old_data JSONB,
#     new_data JSONB,
#     metadata JSONB DEFAULT '{}',
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX audit_auditlog_actor_id_idx ON audit_auditlog(actor_id);
# CREATE INDEX audit_auditlog_entity_idx ON audit_auditlog(entity);
# CREATE INDEX audit_auditlog_created_at_idx ON audit_auditlog(created_at);
class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    entity = models.CharField(max_length=100, blank=True, null=True)
    entity_id = models.CharField(max_length=255, blank=True, null=True)
    old_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

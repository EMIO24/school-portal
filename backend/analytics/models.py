from django.db import models


class AnalyticsSnapshot(models.Model):
    school      = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='analytics_snapshots')
    term        = models.ForeignKey('academics.Term', on_delete=models.CASCADE, related_name='analytics_snapshots')
    computed_at = models.DateTimeField(auto_now=True)
    data        = models.JSONField(default=dict)

    class Meta:
        unique_together = [('school', 'term')]
        ordering        = ['-computed_at']

    def __str__(self):
        return f"Analytics — {self.school.name} | {self.term} | {self.computed_at:%Y-%m-%d %H:%M}"

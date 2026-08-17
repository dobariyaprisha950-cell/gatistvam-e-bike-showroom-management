from django.apps import AppConfig
from zoneinfo import ZoneInfo


_daily_reminder_scheduler = None


class YakuzaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'yakuza'
    verbose_name = 'GATISTVAM E-Bike System Management'

    def ready(self):
        global _daily_reminder_scheduler
        if _daily_reminder_scheduler is not None:
            return

        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from django.core.management import call_command

        def trigger_daily_reminder():
            call_command('generate_daily_reminders')

        _daily_reminder_scheduler = BackgroundScheduler(timezone=ZoneInfo('Asia/Kolkata'), daemon=True)
        _daily_reminder_scheduler.add_job(
            trigger_daily_reminder,
            CronTrigger(hour=19, minute=45, timezone=ZoneInfo('Asia/Kolkata')),
            id='daily_745pm_reminder',
            replace_existing=True,
        )
        _daily_reminder_scheduler.start()

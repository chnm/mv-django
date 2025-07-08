from django.db import models

class HistoricalDateField(models.ForeignKey):
    def __init__(self, **kwargs):
        kwargs['to'] = 'historical_dates.HistoricalDate'
        kwargs['on_delete'] = models.SET_NULL
        kwargs['null'] = True
        super().__init__(**kwargs)

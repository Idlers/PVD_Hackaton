from django.db import models

class Client(models.Model):
    id = models.IntegerField(primary_key=True)
    OKVED2Name = models.CharField(max_length=255, verbose_name="ОКВЭД2. Наименование")
    leavingChance = models.FloatField(verbose_name="Шанс ухода")

    def __str__(self):
        return f"{self.OKVED2Name}"

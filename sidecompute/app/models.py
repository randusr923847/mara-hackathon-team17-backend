from django.db import models
import uuid

# Create your models here.
class Compute(models.Model):
    uuid = models.TextField(default=uuid.uuid4, editable=False)
    host = models.TextField() # host (ip + port) for api
    auth = models.TextField() # api auth token
    flops = models.PositiveBigIntegerField(default=0) # measure of compute power
    power = models.IntegerField() # max power consumption of gpu in watts
    rpm = models.FloatField() # min rate per minute, willing to sell for
    zip = models.IntegerField() # zip code
    dpkwh = models.FloatField() # dollars per killowatt hour average energy bill

class Task(models.Model):
    uuid = models.TextField(default=uuid.uuid4, editable=False)
    file_path = models.TextField() # path to task file
    compute_id = models.TextField() # uuid of scheduled compute
    time = models.PositiveBigIntegerField() # scheduled time to run

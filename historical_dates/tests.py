from django.test import TestCase
from .models import HistoricalDate

class HistoricalDateTests(TestCase):
    def test_edtf_parsing(self):
        hd = HistoricalDate.objects.create(
            display_date="circa 1850",
            edtf_date="1850~"
        )
        self.assertEqual(hd.start_date.year, 1850)


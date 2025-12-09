import django_tables2 as tables

from .models import Crime


class CrimeTable(tables.Table):
    """Table for displaying Crime data"""

    number = tables.Column(
        linkify=("crime_detail", {"crime_id": tables.A("pk")}), verbose_name="Case"
    )
    crime = tables.Column(verbose_name="Violence Type")
    date = tables.DateColumn(format="Y-m-d", verbose_name="Date")
    city = tables.Column(accessor="address__city__name", verbose_name="City")
    victims = tables.Column(empty_values=(), orderable=False, verbose_name="Victim(s)")
    perpetrators = tables.Column(
        empty_values=(), orderable=False, verbose_name="Perpetrator(s)"
    )
    fatality = tables.BooleanColumn(yesno="Yes,No", verbose_name="Fatal")

    class Meta:
        model = Crime
        template_name = "django_tables2/bootstrap4.html"
        fields = (
            "number",
            "crime",
            "date",
            "city",
            "victims",
            "perpetrators",
            "fatality",
        )
        attrs = {
            "class": "table table-striped table-hover",
            "thead": {"class": "thead-dark"},
        }
        per_page = 50

    def render_victims(self, record):
        """Render victim names as comma-separated list"""
        victims = record.victim.all()
        if victims:
            return ", ".join([str(v) for v in victims])
        return "-"

    def render_perpetrators(self, record):
        """Render perpetrator names as comma-separated list"""
        perpetrators = record.perpetrator.all()
        if perpetrators:
            return ", ".join([str(p) for p in perpetrators])
        return "-"

from django.db import models

from historical_dates.fields import HistoricalDateField
from locations.models import Location


class Weapon(models.Model):
    name = models.CharField(max_length=255)
    # definition = models.TextField(blank=True)
    # category = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Person(models.Model):
    first_name = models.CharField(blank=True, max_length=255)
    last_name = models.CharField(blank=True, max_length=255)
    occupation = models.CharField(blank=True, max_length=255)
    identifying_information = models.CharField(blank=True, max_length=255)

    relationships = models.ManyToManyField(
        "self",
        related_name="related_to",
        symmetrical=False,
        through="PersonRelation",
        verbose_name="Related People",
    )

    # gender options
    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"
    GENDER_CHOICES = (
        (MALE, ("Male")),
        (FEMALE, ("Female")),
        (UNKNOWN, ("Unknown")),
    )
    gender = models.CharField(blank=True, max_length=1, choices=GENDER_CHOICES)
    citizenship = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        if self.first_name and self.last_name:
            return self.first_name + " " + self.last_name
        else:
            return self.last_name


class Crime(models.Model):
    victim = models.ManyToManyField(Person, related_name="crime_victim")
    perpetrator = models.ManyToManyField(Person, related_name="crime_perpetrator")
    crime = models.CharField(blank=True, max_length=255)
    motive = models.CharField(blank=True, max_length=255)
    weapon = models.ForeignKey(Weapon, null=True, on_delete=models.SET_NULL)
    date = models.DateField()
    historical_date = HistoricalDateField()
    liturgical_occasion = models.CharField(blank=True, max_length=255)
    time_of_day = models.CharField(blank=True, max_length=255)
    address = models.ForeignKey(Location, null=True, on_delete=models.SET_NULL)
    violence_caused_death = models.BooleanField(
        verbose_name="Did the crime cause the victim to die?"
    )
    pardoned = models.BooleanField(verbose_name="Was the perpetrator pardoned?")
    convicted = models.BooleanField(verbose_name="Was the perpetrator convicted?")
    judge = models.ForeignKey(Person, null=True, on_delete=models.SET_NULL)
    source = models.CharField(blank=True, max_length=255)

    def __str__(self) -> str:
        return self.crime

    class Meta:
        verbose_name = "Violence Event"


# Modeling person relationships, based off Geniza:
# https://github.com/Princeton-CDH/geniza/
class PersonRelationTypeManager(models.Manager):
    def get_by_natural_key(self, name):
        "natural key lookup, based on name"
        return self.get(name_en=name)


class PersonRelationType(models.Model):
    """Controlled vocabulary of people's relationships to other people."""

    name = models.CharField(
        max_length=255, unique=True, help_text="Name of this relationship."
    )
    converse_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="""The converse of the relationship, e.g., 'Child' when Person is 'Parent'.
        Leave blank if the converse is identical (for example, 'Spouse' or 'Business Partner').""",
    )
    # categories for relations:
    IMMEDIATE_FAMILY = "I"
    EXTENDED_FAMILY = "E"
    BY_MARRIAGE = "M"
    BUSINESS = "B"
    AMBIGUITY = "A"
    CATEGORY_CHOICES = (
        (IMMEDIATE_FAMILY, ("Immediate family relations")),
        (EXTENDED_FAMILY, ("Extended family")),
        (BY_MARRIAGE, ("Relatives by marriage")),
        (BUSINESS, ("Business and property relationships")),
        (AMBIGUITY, ("Ambiguity")),
    )
    category = models.CharField(
        max_length=1,
        choices=CATEGORY_CHOICES,
    )
    objects = PersonRelationTypeManager()

    class Meta:
        verbose_name = "Person-Person relationship"
        verbose_name_plural = "Person-Person relationships"

    def __str__(self):
        return self.name

    def relation_set(self):
        # own relationships QuerySet as required by MergeRelationTypesMixin
        return self.personrelation_set.all()


class PersonRelation(models.Model):
    """A relationship between two people."""

    from_person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="to_person"
    )
    to_person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="from_person",
        verbose_name="Person",
    )
    type = models.ForeignKey(
        PersonRelationType,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Relation",
    )
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            # only allow one relationship per type between person and person
            models.UniqueConstraint(
                fields=("type", "from_person", "to_person"),
                name="unique_person_relation_by_type",
            ),
            # do not allow from_person and to_person to be the same person
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_prevent_self_relationship",
                check=~models.Q(from_person=models.F("to_person")),
            ),
        ]

    def __str__(self):
        relation_type = (
            f"{self.type}-{self.type.converse_name}"
            if self.type.converse_name
            else self.type
        )
        return f"{relation_type} relation: {self.to_person} and {self.from_person}"

from django.contrib.auth import get_user_model
from django.db import models

from historical_dates.fields import HistoricalDateField
from locations.models import Location

User = get_user_model()


class WeaponCategory(models.Model):
    name = models.CharField(max_length=500)

    def __str__(self) -> str:
        return self.name


WEAPON_CATEGORY_CHOICES = [
    ("firearm", "Firearm"),
    ("blade", "Blade"),
    ("blunt_instrument", "Blunt Instrument"),
    ("hands", "Hands"),
    ("other", "Other"),
]


class Weapon(models.Model):
    name = models.CharField(max_length=255)
    definition = models.TextField(blank=True)
    category = models.ForeignKey(
        WeaponCategory, null=True, blank=True, on_delete=models.SET_NULL
    )
    weapon_category = models.CharField(
        max_length=50,
        blank=True,
        choices=WEAPON_CATEGORY_CHOICES,
        verbose_name="Weapon Category",
        help_text="Select the top-level weapon category",
    )
    weapon_subcategory = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Weapon Subcategory",
        help_text="Enter subcategory (e.g. pistol, arquebus, dagger, sword, club)",
    )

    def __str__(self):
        return self.name


class Person(models.Model):
    first_name = models.CharField(
        blank=True, max_length=255, help_text="Enter first name"
    )
    last_name = models.CharField(
        blank=True,
        max_length=255,
        help_text="Enter last name first, as in: Badoer, Angelo",
    )
    description = models.TextField(
        blank=True,
        help_text="Input description of person. Example: Youth of 18 years without beard, or Madonna Anzola, wife of Lodovico",
    )
    occupation = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input occupation, if known. Example: massaro. If honorific given, also input here.",
    )
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
    gender = models.CharField(
        blank=True, max_length=1, choices=GENDER_CHOICES, help_text="Input gender: M/F"
    )
    citizenship = models.CharField(max_length=255, null=True, blank=True)
    nationality_ethnicity = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name="Nationality/Ethnicity",
        help_text="Input nationality or ethnicity if recorded in the source, e.g. Ottoman, Jewish, Greek",
    )
    repeat_offender = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True)

    def __str__(self):
        if self.first_name and self.last_name:
            return self.first_name + " " + self.last_name
        else:
            return self.last_name


class Event(models.Model):
    """Model for ceremonial events that may be connected to crimes"""

    name = models.CharField(
        max_length=255,
        help_text="Name of the event, example: feast of the Ascension, wedding of Giovanni Grimani",
    )
    event_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of event, example: feast day, wedding, procession, market day",
    )
    date = models.DateField(
        null=True, blank=True, help_text="Date of the event if known"
    )
    historical_date = HistoricalDateField(
        null=True, blank=True, help_text="Historical date representation if uncertain"
    )
    description = models.TextField(
        blank=True, help_text="Additional details about the event"
    )
    location = models.ForeignKey(
        Location,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Primary location where the event took place",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Event"
        verbose_name_plural = "Events"


class Witness(models.Model):
    name = models.ForeignKey(Person, null=True, on_delete=models.SET_NULL)
    crime = models.ForeignKey(
        "Crime", null=True, on_delete=models.SET_NULL, related_name="witnesses"
    )
    date_of_testimony = HistoricalDateField()
    claims = models.TextField(blank=True)
    notes = models.TextField(blank=True)


class Crime(models.Model):
    # Basic identification
    number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="Input number of case, e.g. 001",
    )
    crime = models.CharField(
        blank=True,
        max_length=255,
        verbose_name="Crime",
        help_text="Input type of crime according to modern taxonomy, e.g., assault, homicide, battery",
    )  # TODO: possibly convert to a model for a controlled vocab
    offense_category = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("homicide", "Homicide"),
            ("premeditated_homicide", "Pre-meditated Homicide"),
            ("insult", "Insult"),
            ("sexual_offenses", "Sexual Offenses"),
            ("abduction", "Abduction"),
            ("assault", "Assault"),
            ("other", "Other"),
        ],
        verbose_name="Offense Category",
        help_text="Select the top-level offense category",
    )
    description_of_case = models.TextField(
        blank=True,
        verbose_name="Description of Case",
        help_text="Description of Case as presented, eg: Giovanni Grimani is accused of assaulting an unnamed servant in the streets of Venice due to malice and a bad nature.",
    )

    # Court and legal information
    court = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input court of first instance that generated case, e.g. Giudice del Maleficio Verona. If unknown, input unknown",
    )
    court_classification = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input classification of crime according to court records (often different from modern taxonomy), for example: assault with a gun, battery with fists, pre-meditated homicide, violent sexual assault, infanticide",
    )
    trial_phase = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input trial phase, if known, example: denunciation, quarrel, summons, sentence",
    )
    arbitration = models.BooleanField(
        default=False,
        verbose_name="Arbitration (Y/N)",
        help_text="Did parties submit to arbitration (e.g. peace agreement or fine?). If so, check Y.",
    )
    sentence = models.TextField(
        blank=True,
        help_text="Input sentence of convicted if known. Examples: death penalty, exile, fine. If multiple penalties, input all in field separated by commas.",
    )
    sentence_in_absentia = models.BooleanField(
        default=False,
        verbose_name="In Contumacia (Y/N)",
        help_text="Was the sentence issued in absentia (in contumacia)? Check Y if the person was sentenced without being present.",
    )
    sentence_enforced = models.BooleanField(
        default=False,
        verbose_name="Sentence Enforced (Y/N)",
        help_text="If sentence was carried about, check Y. If not, leave unchecked.",
    )

    # TODO: image fields

    # Date and time information
    date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date (Modern Format)",
        help_text="Input modern format of date. Example: October 23, 1615 should be converted to 1615-10-23",
    )
    historical_date = HistoricalDateField(null=True, blank=True)
    year = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input year of crime (not year of document) - auto-populated from date field",
    )
    month = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input month of crime - auto-populated from date field",
    )
    day = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input numeric day of crime - auto-populated from date field",
    )
    day_of_week = models.CharField(
        blank=True,
        max_length=20,
        help_text="Input day of week, example: Monday, Thursday - auto-populated from date field",
    )
    time = models.CharField(
        blank=True,
        max_length=255,
        verbose_name="Time",
        help_text="Input specific time if known",
    )
    time_of_day = models.CharField(
        blank=True, max_length=255
    )  # keeping for backward compatibility
    liturgical_occasion = models.CharField(
        blank=True, max_length=255, help_text="Input liturgical occasion if relevant"
    )

    # Connected events
    connected_event = models.ForeignKey(
        Event,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Select connected ceremonial event if applicable (feast day, wedding, procession, etc.)",
    )

    # People involved
    victim = models.ManyToManyField(
        Person,
        related_name="crime_victim",
        help_text="Select victim(s). Names should be entered as: last name, first name. Example: Badoer, Angelo",
    )
    victim_description = models.TextField(
        blank=True,
        help_text="Input description of victim. Example: Youth of 18 years without beard",
    )
    perpetrator = models.ManyToManyField(
        Person,
        related_name="crime_perpetrator",
        verbose_name="Assailant",
        help_text="Select assailant(s). Names should be entered as: lastname, first. Example: Badoer, Francesco.",
    )
    assailant_description = models.TextField(
        blank=True,
        help_text="Input assailant description. Example: Madonna Anzola, wife of Lodovico",
    )

    # Case details
    motive = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input description of motive as given, if known: example: mortal hatred",
    )
    relationship = models.CharField(
        blank=True,
        max_length=255,
        help_text="Input relationship between victim and assailant, if known. Example: husband and wife, friend, enemy",
    )
    weapon = models.ForeignKey(
        Weapon,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Type of Weapon",
        help_text="Input type of weapon if known according to taxonomy (firearm, edged weapon, blunt instrument, hands)",
    )

    # Location
    address = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.SET_NULL
    )
    sestiere = models.CharField(
        blank=True, max_length=255, help_text="If Venetian crime, input neighborhood"
    )
    description_of_location = models.TextField(
        blank=True,
        help_text="Input description of location if given. Example: in front of the Madonna di Miracoli, on the bridge of sighs",
    )

    # Outcome information
    fatality = models.BooleanField(
        default=False,
        verbose_name="Fatality (Y/N)",
        help_text="If the crime was fatal, check Y. If not, leave unchecked.",
    )
    violence_caused_death = models.BooleanField(
        default=False, verbose_name="Did the crime cause the victim to die?"
    )  # keeping for backward compatibility
    pardoned = models.BooleanField(
        default=False, verbose_name="Was the perpetrator pardoned?"
    )
    convicted = models.BooleanField(
        default=False, verbose_name="Was the perpetrator convicted?"
    )
    accord = models.BooleanField(
        default=False, verbose_name="Did the case end with a peace accord?"
    )
    accord_date = models.DateField(
        null=True, blank=True, help_text="If an accord was reached, what was the date?"
    )
    judge = models.ForeignKey(Person, null=True, blank=True, on_delete=models.SET_NULL)

    # Source and archival information
    source = models.CharField(blank=True, max_length=255)
    archival_location = models.CharField(
        blank=True,
        max_length=500,
        help_text="Input archival location of file, example: Archivio di Stato Verona, Giudice del Maleficio",
    )
    reference = models.CharField(
        blank=True,
        max_length=500,
        help_text="Input any bibliographic references to case, if available",
    )

    # Metadata
    input_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="created_by",
        verbose_name="Created by",
        editable=False,
    )
    date_of_entry = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date of Entry",
        help_text="Date case entered into database - automatically populated",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="updated_by",
        editable=False,
    )

    def __str__(self) -> str:
        if self.number and self.crime:
            return f"{self.number}: {self.crime}"
        elif self.number:
            return self.number
        elif self.crime:
            return self.crime
        else:
            return f"Crime #{self.pk}"

    class Meta:
        verbose_name = "Violence Event"


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
    # TODO: Add Romanic relationships
    # TODO: Can we modify this to allow users to add people and categories?
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

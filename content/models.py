from django.db import models
from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.images.blocks import ImageChooserBlock
from wagtail.models import Page, PreviewableMixin
from wagtail.snippets.models import register_snippet


class ImageGalleryBlock(blocks.StructBlock):
    """A gallery block for displaying multiple images with captions."""

    title = blocks.CharBlock(required=False, help_text="Optional title for the gallery")
    images = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("image", ImageChooserBlock(required=True)),
                (
                    "caption",
                    blocks.RichTextBlock(
                        required=False, help_text="Optional caption for the image"
                    ),
                ),
            ]
        ),
        help_text="Add images to the gallery",
    )

    class Meta:
        template = "content/blocks/image_gallery.html"
        icon = "image"
        label = "Image Gallery"


@register_snippet
class HomePageContent(PreviewableMixin, models.Model):
    """
    Snippet for managing home page content including main text and lede.
    """

    title = models.CharField(
        max_length=255, help_text="Internal title for this content block"
    )
    lede = models.TextField(
        max_length=500, help_text="Short introductory text that appears prominently"
    )
    main_content = RichTextField(
        help_text="Main body content for the left column of the home page"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only one home page content block should be active at a time",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("title"),
        FieldPanel("lede"),
        FieldPanel("main_content"),
        FieldPanel("is_active"),
    ]

    class Meta:
        verbose_name = "Home Page Content"
        verbose_name_plural = "Home Page Content"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title

    def get_preview_template(self, request, mode_name):
        return "content/preview/home_page_content.html"

    def get_preview_context(self, request, mode_name):
        return {"content": self}

    def save(self, *args, **kwargs):
        if self.is_active:
            # Ensure only one active content block
            HomePageContent.objects.filter(is_active=True).exclude(pk=self.pk).update(
                is_active=False
            )
        super().save(*args, **kwargs)


@register_snippet
class ProjectPerson(PreviewableMixin, models.Model):
    """
    Snippet for managing project team members displayed on the home page.
    """

    TEAM_TYPE_CHOICES = [
        ("project_team", "Project Team"),
        ("advisory_board", "Advisory Board"),
    ]

    name = models.CharField(max_length=255)
    role = models.CharField(
        max_length=255,
        blank=True,
        help_text="Their role on the project (e.g., Principal Investigator, Research Associate) - optional",
    )
    university = models.CharField(max_length=255, help_text="Associated institution")
    team_type = models.CharField(
        max_length=20,
        choices=TEAM_TYPE_CHOICES,
        default="project_team",
        help_text="Whether this person is part of the Project Team or Advisory Board",
    )
    profile_photo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project_people",
        help_text="Profile photo for the team member",
    )
    bio = RichTextField(
        blank=True, help_text="Brief biographical information (optional)"
    )
    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Order in which this person appears within their group (lower numbers first)",
    )
    is_active = models.BooleanField(
        default=True, help_text="Whether this person should be displayed on the site"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("role"),
        FieldPanel("university"),
        FieldPanel("team_type"),
        FieldPanel("profile_photo"),
        FieldPanel("bio"),
        FieldPanel("display_order"),
        FieldPanel("is_active"),
    ]

    class Meta:
        verbose_name = "Project Person"
        verbose_name_plural = "Project People"
        ordering = ["team_type", "display_order", "name"]

    def __str__(self):
        return f"{self.name} - {self.get_team_type_display()}"

    def get_preview_template(self, request, mode_name):
        return "content/preview/project_person.html"

    def get_preview_context(self, request, mode_name):
        return {"person": self}


class GeneralPage(Page):
    """
    Page model for general pages content.
    """

    content = StreamField(
        [
            ("paragraph", blocks.RichTextBlock(help_text="Rich text content")),
            ("image_gallery", ImageGalleryBlock()),
        ],
        use_json_field=True,
        help_text="Main content for the page",
    )

    content_panels = Page.content_panels + [
        FieldPanel("content"),
    ]

    def save(self, *args, **kwargs):
        # Default to showing in menus
        if not self.pk:  # Only on creation
            self.show_in_menus = True
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "About Page"
        verbose_name_plural = "About Pages"

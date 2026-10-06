import uuid

from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify

from core.image_service import compress_image
from core.models import TimestampedModel


class ProductCategory(TimestampedModel):
    # Category Identity
    name = models.CharField(
        max_length=120,
        help_text="Singular name, e.g. 'Soft Drink'",
    )
    label = models.CharField(
        max_length=120,
        help_text="Display/plural label, e.g. 'Soft Drinks'",
    )
    display_name = models.CharField(
        max_length=80,
        blank=True,
        help_text="Short UI name if different from label.",
    )
    slug = models.SlugField(
        max_length=150,
        unique=True,
        db_index=True,
    )
    aliases = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated search aliases.",
    )

    # Hierarchy
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )

    # Visual / UI
    image = models.ImageField(
        upload_to="product_categories",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"]
            )
        ],
        blank=True,
    )

    # Controls
    sort_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
    )

    # Useful when category should appear in store/product navigation
    is_searchable = models.BooleanField(
        default=True,
    )

    class Meta:
        db_table = "product_categories"
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"
        ordering = [
            "sort_order",
            "name",
        ]

        indexes = [
            models.Index(
                fields=["parent", "is_active", "sort_order"],
                name="prodcat_parent_active_idx",
            ),
            models.Index(
                fields=["is_featured", "is_active"],
                name="prodcat_featured_idx",
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"],
                name="unique_product_category_parent_name",
            ),
            models.CheckConstraint(
                condition=~Q(id=models.F("parent_id")),
                name="product_category_not_own_parent",
            ),
        ]

        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent} → {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.image and not self.image._committed:
            processed_image = compress_image(
                self.image,
                max_width=300,
                quality=85,
                convert_to_webp=False,
            )
            extension = processed_image.name.rsplit(".", 1)[-1]
            processed_image.name = f"{uuid.uuid4().hex}.{extension}"
            self.image = processed_image
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"image"}

        if not self.slug:
            base_slug = slugify(self.label)
            slug = base_slug
            counter = 2

            while ProductCategory.objects.filter(
                slug=slug
            ).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    @property
    def full_name(self):
        parts = [self.name]

        parent = self.parent

        while parent:
            parts.append(parent.name)
            parent = parent.parent

        return " > ".join(reversed(parts))

from .product import Product, ProductVariant

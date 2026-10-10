from django import forms
from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from products.models import (
    Product,
    ProductCategory,
    ProductVariant,
)


# ============================================================
# Helpers
# ============================================================


def get_unit_choices(units):
    """
    Preserve the ordering defined in ProductVariant.Unit.
    """

    return [
        (value, label)
        for value, label in ProductVariant.Unit.choices
        if value in units
    ]


def format_thousand_value(value):
    """
    1000 -> 1
    1500 -> 1.5
    1250 -> 1.25
    """

    whole = value // 1000
    remainder = value % 1000

    if remainder == 0:
        return str(whole)

    decimal = (
        str(remainder)
        .rjust(3, "0")
        .rstrip("0")
    )

    return f"{whole}.{decimal}"


def format_total_measurement(obj):
    """
    Human-readable total content of a variant.

    Examples:
        75 g × 3     -> 225 g
        500 ml × 3   -> 1.5 L
        6 Pcs × 2    -> 12 Pcs
        3 Packs      -> 3 Packs
    """

    if not obj:
        return "-"

    measurement_type = (
        obj.product.measurement_type
    )

    # --------------------------------------------------------
    # NONE
    # --------------------------------------------------------

    if (
        measurement_type
        == Product.MeasurementType.NONE
    ):
        return obj.name or "-"

    total = obj.total_measurement_value

    if total is None:
        return "-"

    # --------------------------------------------------------
    # WEIGHT
    # --------------------------------------------------------

    if (
        measurement_type
        == Product.MeasurementType.WEIGHT
    ):
        if total < 1000:
            return f"{total} g"

        return (
            f"{format_thousand_value(total)} kg"
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if (
        measurement_type
        == Product.MeasurementType.VOLUME
    ):
        if total < 1000:
            return f"{total} ml"

        return (
            f"{format_thousand_value(total)} L"
        )

    # --------------------------------------------------------
    # COUNT
    # --------------------------------------------------------

    if (
        measurement_type
        == Product.MeasurementType.COUNT
    ):
        labels = (
            ProductVariant.UNIT_LABELS.get(
                obj.unit
            )
        )

        if not labels:
            return str(total)

        singular, plural = labels

        label = (
            singular
            if total == 1
            else plural
        )

        return f"{total} {label}"

    return str(total)


# ============================================================
# Product Category Admin
# ============================================================


class ParentWithChildrenListFilter(
    admin.SimpleListFilter
):
    title = "parent"
    parameter_name = "parent__id__exact"

    def lookups(self, request, model_admin):
        categories = (
            ProductCategory.objects
            .filter(children__isnull=False)
            .distinct()
            .order_by("sort_order", "name")
        )

        return [
            (category.pk, str(category))
            for category in categories
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                parent_id=self.value()
            )

        return queryset


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "label",
        "parent",
        "sort_order",
        "is_active",
        "is_featured",
        "is_searchable",
        "updated_at",
    )

    list_filter = (
        "is_active",
        "is_featured",
        "is_searchable",
        ParentWithChildrenListFilter,
    )

    list_editable = (
        "sort_order",
        "is_searchable",
    )

    search_fields = (
        "name",
        "label",
        "display_name",
        "slug",
        "aliases",
    )

    prepopulated_fields = {
        "slug": (
            "label",
        )
    }

    autocomplete_fields = (
        "parent",
    )

    ordering = (
        "sort_order",
        "name",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )


# ============================================================
# Product Variant Admin Form
# ============================================================


class ProductVariantAdminForm(forms.ModelForm):

    unit = forms.ChoiceField(
        required=False,
        choices=ProductVariant.Unit.choices,
    )

    class Meta:
        model = ProductVariant
        fields = "__all__"

    def __init__(
        self,
        *args,
        product_context=None,
        measurement_type_context=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.measurement_type_context = (
            measurement_type_context
        )

        # ----------------------------------------------------
        # Inline product context
        # ----------------------------------------------------

        if (
            self.measurement_type_context
            is None
            and product_context
        ):
            self.measurement_type_context = (
                product_context.measurement_type
            )

        # ----------------------------------------------------
        # Existing standalone variant
        # ----------------------------------------------------

        if (
            self.measurement_type_context
            is None
            and self.instance
            and self.instance.pk
            and self.instance.product_id
        ):
            self.measurement_type_context = (
                self.instance
                .product
                .measurement_type
            )

        # ----------------------------------------------------
        # Standalone add/change POST
        # ----------------------------------------------------

        if (
            self.measurement_type_context
            is None
            and self.is_bound
        ):
            product_id = self.data.get(
                self.add_prefix("product")
            )

            if product_id:
                product = (
                    Product.objects
                    .filter(pk=product_id)
                    .only("measurement_type")
                    .first()
                )

                if product:
                    self.measurement_type_context = (
                        product.measurement_type
                    )

        self._configure_unit_field()

    def _configure_unit_field(self):
        field = self.fields.get("unit")

        if not field:
            return

        measurement_type = (
            self.measurement_type_context
        )

        # ----------------------------------------------------
        # WEIGHT
        #
        # Always stored as gram.
        # ----------------------------------------------------

        if (
            measurement_type
            == Product.MeasurementType.WEIGHT
        ):
            field.choices = [
                (
                    ProductVariant.Unit.GRAM,
                    ProductVariant.Unit.GRAM.label,
                )
            ]

            field.initial = (
                ProductVariant.Unit.GRAM
            )

            field.disabled = True

            field.help_text = (
                "Weight is stored internally in grams. "
                "kg is generated automatically for display."
            )

        # ----------------------------------------------------
        # VOLUME
        #
        # Always stored as ml.
        # ----------------------------------------------------

        elif (
            measurement_type
            == Product.MeasurementType.VOLUME
        ):
            field.choices = [
                (
                    ProductVariant.Unit.MILLILITRE,
                    ProductVariant.Unit.MILLILITRE.label,
                )
            ]

            field.initial = (
                ProductVariant.Unit.MILLILITRE
            )

            field.disabled = True

            field.help_text = (
                "Volume is stored internally in ml. "
                "L is generated automatically for display."
            )

        # ----------------------------------------------------
        # COUNT
        #
        # Seller selects:
        # Pcs / Pack / Box / Jar / Can / etc.
        # ----------------------------------------------------

        elif (
            measurement_type
            == Product.MeasurementType.COUNT
        ):
            field.choices = [
                ("", "---------"),
                *get_unit_choices(
                    ProductVariant.COUNT_UNITS
                ),
            ]

            field.required = True

            field.help_text = (
                "Select what is being counted, "
                "for example Pcs, Pack, Box, Can or Bottle."
            )

        # ----------------------------------------------------
        # NONE
        #
        # Seller chooses package/selling form.
        # ----------------------------------------------------

        elif (
            measurement_type
            == Product.MeasurementType.NONE
        ):
            field.choices = [
                ("", "---------"),
                *get_unit_choices(
                    ProductVariant.NONE_UNITS
                ),
            ]

            field.required = True

            field.help_text = (
                "Select the selling/package unit, "
                "for example Pcs, Pack, Box, Jar, Can or Carton."
            )

    def clean(self):
        cleaned_data = super().clean()

        measurement_type = (
            self.measurement_type_context
        )

        # Ensure canonical units are present before
        # model validation runs.

        if (
            measurement_type
            == Product.MeasurementType.WEIGHT
        ):
            cleaned_data["unit"] = (
                ProductVariant.Unit.GRAM
            )

            self.instance.unit = (
                ProductVariant.Unit.GRAM
            )

        elif (
            measurement_type
            == Product.MeasurementType.VOLUME
        ):
            cleaned_data["unit"] = (
                ProductVariant.Unit.MILLILITRE
            )

            self.instance.unit = (
                ProductVariant.Unit.MILLILITRE
            )

        return cleaned_data


# ============================================================
# Variant Inline FormSet
# ============================================================


class RequiredProductVariantInlineFormSet(
    BaseInlineFormSet
):

    measurement_type_context = None

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)

        kwargs["product_context"] = self.instance

        kwargs["measurement_type_context"] = (
            self.measurement_type_context
        )

        return kwargs

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        active_forms = [
            form
            for form in self.forms
            if (
                form.cleaned_data
                and not form.cleaned_data.get(
                    "DELETE",
                    False,
                )
            )
        ]

        if not active_forms:
            raise forms.ValidationError(
                "Add at least one product variant."
            )


# ============================================================
# Product Variant Inline
# ============================================================


class ProductVariantInline(admin.TabularInline):

    model = ProductVariant

    form = ProductVariantAdminForm

    formset = (
        RequiredProductVariantInlineFormSet
    )

    extra = 1

    min_num = 1

    validate_min = True

    fields = (
        "name",
        "value",
        "unit",
        "pack_count",
        "price",
        "mrp",
        "cost_price",
        "is_default",
        "is_active",
        "sort_order",
        "total_measurement_display",
    )

    readonly_fields = (
        "name",
        "total_measurement_display",
    )

    ordering = (
        "sort_order",
        "value",
        "pack_count",
    )

    show_change_link = True

    def get_formset(
        self,
        request,
        obj=None,
        **kwargs,
    ):
        BaseFormSet = super().get_formset(
            request,
            obj,
            **kwargs,
        )

        # Product measurement type from submitted
        # parent Product form.
        measurement_type = request.POST.get(
            "measurement_type"
        )

        # Existing product page.
        if not measurement_type and obj:
            measurement_type = (
                obj.measurement_type
            )

        # New product GET.
        if not measurement_type:
            measurement_type = (
                Product.MeasurementType.NONE
            )

        class ContextFormSet(BaseFormSet):
            measurement_type_context = (
                measurement_type
            )

        return ContextFormSet

    @admin.display(
        description="Total",
    )
    def total_measurement_display(
        self,
        obj,
    ):
        return format_total_measurement(obj)


# ============================================================
# Product Admin Form
# ============================================================


class ProductAdminForm(forms.ModelForm):

    slug = forms.SlugField(
        required=False,
    )

    class Meta:
        model = Product
        fields = "__all__"


# ============================================================
# Product Admin
# ============================================================


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    form = ProductAdminForm

    list_display = (
        "name",
        "store",
        "measurement_type",
        "allow_custom_quantity",
        "display_price",
        "variant_count",
        "is_active",
        "is_featured",
        "created_at",
    )

    list_filter = (
        "measurement_type",
        "allow_custom_quantity",
        "is_active",
        "is_featured",
        "created_at",
    )

    search_fields = (
        "name",
        "public_id",
        "brand",
        "slug",
    )

    readonly_fields = (
        "id",
        "public_id",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "store",
        "categories",
        "uploads",
    )

    ordering = (
        "sort_order",
        "-created_at",
    )

    list_per_page = 50

    list_select_related = (
        "store",
    )

    inlines = [
        ProductVariantInline,
    ]

    fieldsets = (
        (
            "Product",
            {
                "fields": (
                    "id",
                    "public_id",
                    "store",
                    "name",
                    "slug",
                    "short_description",
                    "brand",
                )
            },
        ),

        (
            "Categories",
            {
                "fields": (
                    "categories",
                )
            },
        ),

        (
            "Media",
            {
                "fields": (
                    "uploads",
                )
            },
        ),

        (
            "Measurement",
            {
                "fields": (
                    "measurement_type",
                ),
                "description": (
                    "Weight = g/kg, Volume = ml/L, "
                    "Count = numeric units such as Pcs/Boxes, "
                    "No Measurement = Pack/Jar/Can/etc. "
                    "without a numeric content value."
                ),
            },
        ),

        (
            "Information",
            {
                "fields": (
                    "specifications",
                )
            },
        ),

        (
            "Custom Quantity",
            {
                "fields": (
                    "allow_custom_quantity",
                    "base_quantity",
                    "base_price",
                    "minimum_quantity",
                    "quantity_step",
                ),
                "description": (
                    "Use for products such as loose sugar, "
                    "rice, vegetables or loose liquids."
                ),
            },
        ),

        (
            "Visibility",
            {
                "fields": (
                    "is_active",
                    "is_featured",
                    "sort_order",
                )
            },
        ),

        (
            "System",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(
        description="Price",
        ordering=None,
    )
    def display_price(self, obj):
        variant = obj.default_variant

        if variant:
            return f"₹{variant.price}"

        price = obj.starting_price

        if price is not None:
            return f"₹{price}"

        return "-"

    @admin.display(
        description="Variants",
    )
    def variant_count(self, obj):
        return obj.variants.count()


# ============================================================
# Product Variant Admin
# ============================================================


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):

    form = ProductVariantAdminForm

    list_display = (
        "product",
        "variant_display",
        "value",
        "unit_display",
        "pack_count",
        "total_measurement_display",
        "price",
        "mrp",
        "is_default",
        "is_active",
        "created_at",
    )

    list_filter = (
        "unit",
        "product__measurement_type",
        "is_default",
        "is_active",
        "created_at",
    )

    search_fields = (
        "product__name",
        "product__public_id",
        "name",
    )

    autocomplete_fields = (
        "product",
    )

    readonly_fields = (
        "id",
        "name",
        "total_measurement_display",
        "created_at",
        "updated_at",
    )

    ordering = (
        "product",
        "sort_order",
        "value",
        "pack_count",
    )

    list_per_page = 50

    list_select_related = (
        "product",
        "product__store",
    )

    fieldsets = (
        (
            "Variant",
            {
                "fields": (
                    "id",
                    "product",
                    "name",
                    "value",
                    "unit",
                    "pack_count",
                    "total_measurement_display",
                )
            },
        ),

        (
            "Pricing",
            {
                "fields": (
                    "price",
                    "mrp",
                    "cost_price",
                )
            },
        ),

        (
            "Controls",
            {
                "fields": (
                    "is_default",
                    "is_active",
                    "sort_order",
                )
            },
        ),

        (
            "System",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(
        description="Variant",
    )
    def variant_display(self, obj):
        return obj.name or "-"

    @admin.display(
        description="Unit",
    )
    def unit_display(self, obj):
        return (
            obj.get_unit_display()
            if obj.unit
            else "-"
        )

    @admin.display(
        description="Total",
    )
    def total_measurement_display(
        self,
        obj,
    ):
        return format_total_measurement(obj)

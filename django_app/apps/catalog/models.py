"""
apps.catalog.models
=====================
The dynamic product catalog: Department -> Category (tree) -> Product,
plus images, flexible key/value specifications, and reviews.

Design goal: a store owner should be able to add a brand-new department
("Home & Garden") or an arbitrarily nested category ("Electronics >
Laptops > Gaming Laptops") entirely through the Django admin, with zero
code or migration changes. That's achieved by:
  * Department: a flat top-level grouping (rarely changes, but still data).
  * Category: self-referential (parent FK) so it can be nested to any
    depth, and it belongs to a Department.
  * ProductSpecification: arbitrary key/value pairs per product, so a
    "Laptop" can have "RAM" / "16GB" while a "T-Shirt" has "Size" / "L"
    without needing a different Product subclass or schema change.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Department(models.Model):
    """Top-level storefront grouping, e.g. 'Electronics', 'Fashion'."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="departments/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first in navigation.")

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:department_detail", kwargs={"slug": self.slug})


class Category(models.Model):
    """
    a (possibly nested) category within a Department.

    The parent field is what gives us unlimited
    category depth without schema changes e.g "Electronics > Computers >
    Laptops > Gaming Laptops" is just four Category rows chained together
    """
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="categories"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="children",
        null=True, blank=True,
        help_text="Leave blank for a top-level category within the department.",
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["display_order", "name"]
        unique_together = ("department", "parent", "slug")

    def __str__(self):
        return " > ".join(self.get_ancestors_names())

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_ancestors_names(self):
        """Walk up the parent chain to build a breadcrumb-friendly list"""
        names = [self.name]
        node = self.parent
        while node is not None:
            names.insert(0, node.name)
            node = node.parent
        return names

    def get_descendant_ids(self, include_self=True):
        """
        Recursively collect this category's own id plus every descendant's
        id. Used by product listing views so that browsing e.g "Electronics"
        also shows products filed under "Laptops" and "Gaming Laptops"
        """
        ids = [self.pk] if include_self else []
        for child in self.children.all():
            ids.extend(child.get_descendant_ids(include_self=True))
        return ids

    def get_absolute_url(self):
        return reverse("catalog:category_detail", kwargs={"slug": self.slug})


class ProductQuerySet(models.QuerySet):
    """Reusable query helpers so views/templates stay declarative"""

    def active(self):
        return self.filter(is_active=True)

    def in_stock(self):
        return self.filter(stock_quantity__gt=0)

    def on_sale(self):
        return self.filter(discount_price__isnull=False, discount_price__gt=0)


class Product(models.Model):
    """A single sellable item."""
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="products"
    )
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=270, unique=True, blank=True)
    sku = models.CharField("SKU", max_length=64, unique=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="If set and lower than price, the product is 'on sale'.",
    )

    stock_quantity = models.PositiveIntegerField(default=0)
    weight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00"),
        help_text="Used for shipping estimates.",
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active", "is_featured"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            # Guarantee slug uniqueness even for two products with the
            # same name (e.g. same shirt in different colors added, separately) by appending an incrementing suffix.
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def is_on_sale(self):
        return bool(self.discount_price and self.discount_price < self.price)

    @property
    def current_price(self):
        """The price a customer actually pays right now."""
        return self.discount_price if self.is_on_sale else self.price

    @property
    def discount_percent(self):
        if not self.is_on_sale:
            return 0
        return round((1 - (self.discount_price / self.price)) * 100)

    @property
    def in_stock(self):
        return self.stock_quantity > 0

    def get_primary_image(self):
        return self.images.filter(is_primary=True).first() or self.images.first()


class ProductImage(models.Model):
    """A product can have many images; one must be flagged primary for listing"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Only one primary image per product.
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class ProductSpecification(models.Model):
    """
    Arbitrary key/value attribute for a product, e.g. ("RAM", "16GB") or
    ("Material", "100% Cotton"). This is what gives the catalog it's
    flexibility: wildly different product types can coexist under one
    Product model without sparse, product-type-specific columns.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specifications")
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = ("product", "name")

    def __str__(self):
        return f"{self.name}: {self.value}"

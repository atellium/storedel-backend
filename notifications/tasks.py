import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from core.notifications import send_push_notification
from notifications.models import DeviceToken
from orders.models import Order


logger = logging.getLogger(__name__)


@shared_task
def send_store_owner_order_placed_notification(order_id):
    order = (
        Order.objects.select_related("store", "store__owner")
        .filter(pk=order_id)
        .first()
    )
    if order is None:
        logger.info("Skipping order push notification; order %s was not found.", order_id)
        return {"sent": 0, "failed": 0, "skipped": 1}

    if order.store.owner_id is None:
        logger.info(
            "Skipping order push notification; store %s has no owner.",
            order.store_id,
        )
        return {"sent": 0, "failed": 0, "skipped": 1}

    tokens = list(
        DeviceToken.objects.filter(
            user_id=order.store.owner_id,
            is_active=True,
        ).exclude(token="")
    )
    if not tokens:
        return {"sent": 0, "failed": 0, "skipped": 1}

    title = "New Order Received! 🛍️"
    body = (
        f"₹{order.total_amount} • "
        f"{order.get_fullfillment_type_display()} • "
        f"Order #{order.order_number}"
    )
    url = ""
    if settings.SITE_URL:
        url = (
            f"{settings.SITE_URL}/{order.store.slug}/manage/orders/"
            f"{order.order_number}"
        )
    data = {
        "type": "order_placed",
        "order_id": order.id,
        "order_number": order.order_number,
        "store_id": order.store_id,
        "store_slug": order.store.slug,
        "status": order.status,
        "fullfillment_type": order.fullfillment_type,
        "total_amount": order.total_amount,
        "url": url,
    }

    sent = 0
    failed = 0
    now = timezone.now()

    for device_token in tokens:
        response = send_push_notification(
            token=device_token.token,
            title=title,
            body=body,
            data=data,
        )

        if response:
            sent += 1
            device_token.failure_count = 0
            device_token.last_notification_at = now
            device_token.save(
                update_fields=[
                    "failure_count",
                    "last_notification_at",
                    "updated_at",
                ]
            )
            continue

        failed += 1
        device_token.failure_count += 1
        device_token.save(update_fields=["failure_count", "updated_at"])

    return {"sent": sent, "failed": failed, "skipped": 0}

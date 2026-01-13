"""Prometheus Metrics Endpoint.

Exposes application metrics in Prometheus format.
"""

from fastapi import APIRouter, Response

from app.core.constants import Metrics
from app.core.metrics import get_content_type, get_metrics

router = APIRouter()


@router.get(Metrics.ENDPOINT_PATH)
async def prometheus_metrics():
    """Expose Prometheus metrics.

    This endpoint is scraped by Prometheus server to collect metrics.
    Returns metrics in Prometheus text format.

    Example Prometheus configuration:
    ```yaml
    scrape_configs:
      - job_name: 'credit-application-api'
        static_configs:
          - targets: ['backend:8000']
        metrics_path: '/metrics'
        scrape_interval: 15s
    ```
    """
    metrics_data = get_metrics()

    return Response(
        content=metrics_data,
        media_type=get_content_type()
    )

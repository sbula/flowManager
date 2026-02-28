import json
import urllib.error
import urllib.request
from typing import Any, Dict

from pydantic import Field

from .base import Atom, AtomConfig, AtomResult, AtomStatus, RetryStrategy


class WebhookAtomConfig(AtomConfig):
    url: str
    method: str = "POST"
    payload: Dict[str, Any] = Field(default_factory=dict)


class WebhookAtom(Atom):
    """
    WebhookAtom (System Integration).
    Executes a standard HTTP REST call.
    Includes Idempotency-Key handling.
    """

    def _parse_config(self, config: Dict[str, Any]) -> WebhookAtomConfig:
        return WebhookAtomConfig(**config)

    def run(self, context: Dict[str, Any]) -> AtomResult:
        # Use the already parsed config from self.config
        config: WebhookAtomConfig = self.config  # type: ignore

        if not config.url:
            return AtomResult(status=AtomStatus.FAILED, message="Missing Webhook URL")

        # Generate Deterministic Idempotency Key based on Engine Run ID.
        # Expecting the engine to embed its context IDs.
        task_id = context.get("__task_id__", "unknown-task")
        run_id = config.run_id or task_id

        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": f"webhook-{run_id}",
        }

        try:
            req = urllib.request.Request(
                config.url,
                method=config.method,
                data=(
                    json.dumps(config.payload).encode("utf-8")
                    if config.payload
                    else None
                ),
            )
            for k, v in headers.items():
                req.add_header(k, v)

            with urllib.request.urlopen(req) as response:
                resp_data = response.read().decode("utf-8")

                # Check status
                if response.status >= 400:
                    return AtomResult(
                        status=AtomStatus.FAILED,
                        message=f"HTTP {response.status}: {resp_data}",
                    )

                return AtomResult(
                    status=AtomStatus.SUCCESS,
                    message=f"Webhook successfully delivered to {config.url}",
                    exports={
                        "webhook_response": resp_data,
                        "webhook_status": response.status,
                    },
                )
        except urllib.error.HTTPError as e:
            if e.code in [429, 500, 502, 503, 504]:
                return AtomResult(
                    status=AtomStatus.RETRY,
                    message=f"HTTP {e.code}",
                    retry_strategy=RetryStrategy.BACKOFF,
                )
            return AtomResult(status=AtomStatus.FAILED, message=f"HTTP Error: {e.code}")
        except urllib.error.URLError as e:
            return AtomResult(
                status=AtomStatus.RETRY,
                message=f"URL Error: {str(e)}",
                retry_strategy=RetryStrategy.BACKOFF,
            )
        except Exception as e:
            return AtomResult(
                status=AtomStatus.FAILED, message=f"Webhook exception: {str(e)}"
            )

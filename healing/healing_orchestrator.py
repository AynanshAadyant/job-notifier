"""Coordinates the full healing loop: trigger -> generate -> test -> accept/retry/escalate."""

import asyncio
from domain.site_config import SiteConfig
from domain.results import HealingEvent
from healing.config_generator import ConfigGenerator
from healing.config_tester import ConfigTester


class HealingOrchestrator:
    """Coordinates self-healing cycles with bounded retries and human escalation."""

    def __init__(
        self,
        generator: ConfigGenerator,
        tester: ConfigTester | None = None,
        max_attempts: int = 3,
    ):
        self.generator = generator
        self.tester = tester or ConfigTester()
        self.max_attempts = max_attempts

    async def heal(
        self,
        html_sample: str,
        failure_reason: str,
        current_config: SiteConfig,
    ) -> tuple[SiteConfig | None, list[HealingEvent]]:
        events: list[HealingEvent] = []
        last_error = ""

        for attempt in range(1, self.max_attempts + 1):
            context = f"{failure_reason} (Attempt {attempt}/{self.max_attempts})"
            if last_error:
                context += f"; Previous sandbox test failed with: {last_error}"

            try:
                # Step 1: LLM generates candidate config data
                candidate = await self.generator.generate(
                    html_sample=html_sample,
                    failure_context=context,
                    current_config=current_config,
                )

                # Step 2: Validate in sandbox on real HTML sample
                test_result = self.tester.test_config(candidate, html_sample)

                event = HealingEvent(
                    site_name=current_config.site_name,
                    old_version=current_config.version,
                    new_version=candidate.version if test_result.is_valid else None,
                    trigger_reason=failure_reason,
                    passed_sandbox=test_result.is_valid,
                    details=f"Attempt {attempt}: {test_result.reason}",
                    candidate_config_json=candidate.model_dump_json(),
                )
                events.append(event)

                if test_result.is_valid:
                    # Promoted!
                    return candidate, events
                else:
                    last_error = test_result.reason

            except Exception as e:
                last_error = f"Generation error: {e}"
                events.append(
                    HealingEvent(
                        site_name=current_config.site_name,
                        old_version=current_config.version,
                        trigger_reason=failure_reason,
                        passed_sandbox=False,
                        details=f"Attempt {attempt} exception: {e}",
                    )
                )

            # Brief backoff between LLM retry attempts
            await asyncio.sleep(1.0)

        # All attempts exhausted -> escalate to human
        events.append(
            HealingEvent(
                site_name=current_config.site_name,
                old_version=current_config.version,
                trigger_reason=failure_reason,
                passed_sandbox=False,
                details=f"Exhausted {self.max_attempts} healing attempts. Human escalation required.",
            )
        )
        return None, events

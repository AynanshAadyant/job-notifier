"""Command-line entry point for the job scraper application."""

import asyncio
import argparse
import sys
from dotenv import load_dotenv

from settings import settings
from bot import start_bot, run_once

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Self-Healing Job Scraper & Notifier Bot",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scrape pass across active sites and exit immediately (no daemon/scheduler)",
    )
    parser.add_argument(
        "--site",
        type=str,
        default=None,
        help="Target a specific site name (e.g. 'remoteok'). Defaults to all active sites.",
    )
    parser.add_argument(
        "--no-initial-scrape",
        action="store_true",
        help="When running as a daemon, do not run an immediate scrape pass on startup",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default=None,
        help="Override AI provider (gemini, openai, ollama, groq, mock)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    # Optional runtime settings override
    if args.provider:
        settings.ai_provider = args.provider

    if args.once:
        print(f"Executing single-pass scrape (site={args.site or 'all'})...")
        results = await run_once(site_name=args.site, settings=settings)
        total_jobs = sum(len(r.postings) for r in results)
        print(f"Single-pass scrape complete: {len(results)} site(s) processed, {total_jobs} total valid jobs found.")
        for r in results:
            status = "SUCCESS" if r.success else f"FAILED: {r.error}"
            print(f"  [{status}] {r.site_name}: {len(r.postings)} postings in {r.execution_time_seconds:.2f}s")
    else:
        site_filter = [args.site] if args.site else None
        print("Starting Job Notifier Bot daemon (Ctrl+C to stop)...")
        await start_bot(
            settings=settings,
            site_names=site_filter,
            run_initial_scrape=not args.no_initial_scrape,
            block=True,
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nShutdown complete.")
        sys.exit(0)

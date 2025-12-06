#!/usr/bin/env python3
"""
Load test for DMFV version isolation.

Makes concurrent async requests to different versions and verifies
each response matches the expected version - proving isolation works.

Usage:
    # Start the server first:
    uvicorn app.main:app --port 8000

    # Run the load test:
    python load_test.py

    # Or with custom parameters:
    python load_test.py --requests 200 --concurrency 50 --url http://localhost:8000
"""
import argparse
import asyncio
import time
from dataclasses import dataclass

import httpx


@dataclass
class TestResult:
    version_requested: str
    version_received: str
    expected_result: str
    actual_result: str
    success: bool
    duration_ms: float
    error: str | None = None


async def call_version(
    client: httpx.AsyncClient,
    base_url: str,
    version: str,
    expected_result: str,
) -> TestResult:
    """Make a single request and verify the response."""
    start = time.perf_counter()
    try:
        response = await client.get(
            f"{base_url}/api/foo",
            params={"version": version},
        )
        duration_ms = (time.perf_counter() - start) * 1000

        if response.status_code != 200:
            return TestResult(
                version_requested=version,
                version_received="",
                expected_result=expected_result,
                actual_result="",
                success=False,
                duration_ms=duration_ms,
                error=f"HTTP {response.status_code}: {response.text}",
            )

        data = response.json()
        actual_result = data.get("result", "")
        version_received = data.get("version", "")

        success = (actual_result == expected_result and version_received == version)

        return TestResult(
            version_requested=version,
            version_received=version_received,
            expected_result=expected_result,
            actual_result=actual_result,
            success=success,
            duration_ms=duration_ms,
            error=None if success else f"Expected {expected_result}, got {actual_result}",
        )

    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        return TestResult(
            version_requested=version,
            version_received="",
            expected_result=expected_result,
            actual_result="",
            success=False,
            duration_ms=duration_ms,
            error=str(e),
        )


async def run_load_test(
    base_url: str,
    total_requests: int,
    concurrency: int,
) -> list[TestResult]:
    """Run load test with concurrent requests to both versions."""

    # Create mix of v1 and v2 requests
    tasks_config = []
    for i in range(total_requests):
        if i % 2 == 0:
            tasks_config.append(("1.0.0", "bar"))
        else:
            tasks_config.append(("2.0.0", "bat"))

    results: list[TestResult] = []
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_call(client: httpx.AsyncClient, version: str, expected: str):
        async with semaphore:
            return await call_version(client, base_url, version, expected)

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [
            bounded_call(client, version, expected)
            for version, expected in tasks_config
        ]
        results = await asyncio.gather(*tasks)

    return results


def print_results(results: list[TestResult], duration: float):
    """Print test results summary."""
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful

    v1_results = [r for r in results if r.version_requested == "1.0.0"]
    v2_results = [r for r in results if r.version_requested == "2.0.0"]

    v1_success = sum(1 for r in v1_results if r.success)
    v2_success = sum(1 for r in v2_results if r.success)

    avg_duration = sum(r.duration_ms for r in results) / total if total > 0 else 0
    min_duration = min(r.duration_ms for r in results) if results else 0
    max_duration = max(r.duration_ms for r in results) if results else 0

    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS - VERSION ISOLATION TEST")
    print("=" * 60)
    print(f"\nTotal Requests:     {total}")
    print(f"Total Duration:     {duration:.2f}s")
    print(f"Requests/sec:       {total / duration:.2f}")
    print(f"\nSuccessful:         {successful} ({100 * successful / total:.1f}%)")
    print(f"Failed:             {failed} ({100 * failed / total:.1f}%)")

    print(f"\n--- Version 1.0.0 (expects 'bar') ---")
    print(f"Requests:           {len(v1_results)}")
    print(f"Successful:         {v1_success} ({100 * v1_success / len(v1_results):.1f}%)")

    print(f"\n--- Version 2.0.0 (expects 'bat') ---")
    print(f"Requests:           {len(v2_results)}")
    print(f"Successful:         {v2_success} ({100 * v2_success / len(v2_results):.1f}%)")

    print(f"\n--- Response Times ---")
    print(f"Average:            {avg_duration:.2f}ms")
    print(f"Min:                {min_duration:.2f}ms")
    print(f"Max:                {max_duration:.2f}ms")

    if failed > 0:
        print(f"\n--- Failures ---")
        for r in results:
            if not r.success:
                print(f"  v{r.version_requested}: {r.error}")

    print("\n" + "=" * 60)

    if failed == 0:
        print("SUCCESS: All requests returned correct version-specific results!")
        print("Version isolation is working correctly under concurrent load.")
    else:
        print("FAILURE: Some requests returned incorrect results.")
        print("Version isolation may not be working correctly.")
    print("=" * 60 + "\n")

    return failed == 0


async def main():
    parser = argparse.ArgumentParser(description="Load test for DMFV version isolation")
    parser.add_argument(
        "--requests", "-n",
        type=int,
        default=100,
        help="Total number of requests (default: 100)",
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=20,
        help="Number of concurrent requests (default: 20)",
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default="http://localhost:8000",
        help="Base URL of the API (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    print(f"\nStarting load test...")
    print(f"  URL:         {args.url}")
    print(f"  Requests:    {args.requests}")
    print(f"  Concurrency: {args.concurrency}")
    print(f"\nSending requests to both v1.0.0 (expects 'bar') and v2.0.0 (expects 'bat')...")

    start = time.perf_counter()
    results = await run_load_test(args.url, args.requests, args.concurrency)
    duration = time.perf_counter() - start

    success = print_results(results, duration)
    return 0 if success else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))

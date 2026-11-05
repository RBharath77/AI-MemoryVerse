#!/usr/bin/env python3
"""AI-MemoryVerse — Production & Staging Smoke Test Suite

Runs a sequence of HTTP verification checks against a live deployed
instance of AI-MemoryVerse to ensure:
1. Health and Readiness probes
2. User registration and authentication
3. Private workspace initialization
4. Memory vault ingestion and retrieval
5. Hybrid search engine execution
6. Knowledge graph extraction probe
7. Quota and Billing status check
8. Controlled agent tool registry inspection

Usage:
    python scripts/smoke_test.py --base-url https://memoryverse-api.onrender.com
    python scripts/smoke_test.py --base-url http://localhost:8000
"""

import argparse
import sys
import time
import uuid
import requests


def main():
    parser = argparse.ArgumentParser(description="AI-MemoryVerse Production Smoke Test")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the Backend API (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    print(f"==================================================")
    print(f" AI-MemoryVerse Production Smoke Test Suite")
    print(f" Target Endpoint: {base_url}")
    print(f"==================================================\n")

    passed_checks = 0
    total_checks = 8

    # 1. Health Probe Check
    print("[1/8] Verifying Health Probe (/health)...", end=" ")
    try:
        res = requests.get(f"{base_url}/health", timeout=10)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert res.json().get("status") == "healthy", f"Expected status healthy"
        print("✓ PASSED")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    # 2. Readiness Probe Check
    print("[2/8] Verifying Readiness Probe (/ready)...", end=" ")
    try:
        res = requests.get(f"{base_url}/ready", timeout=10)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        data = res.json()
        assert data.get("status") in ("ready", "degraded"), f"Unexpected status: {data}"
        print(f"✓ PASSED (DB: {data.get('database', 'unknown')})")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    # 3. User Registration & Auth
    print("[3/8] Verifying Registration & Auth Token Generation...", end=" ")
    token = None
    workspace_id = None
    try:
        random_id = uuid.uuid4().hex[:8]
        reg_payload = {
            "email": f"smoketest_{random_id}@memoryverse.ai",
            "password": "SmokeTestPassword123!",
            "full_name": f"Smoke Test Bot {random_id}",
            "workspace_name": f"Smoke Test Workspace {random_id}",
        }
        res = requests.post(f"{base_url}/api/v1/auth/register", json=reg_payload, timeout=10)
        assert res.status_code == 201, f"Expected 201, got {res.status_code} ({res.text})"
        auth_data = res.json()["data"]
        token = auth_data["tokens"]["access_token"]
        workspace_id = auth_data["workspace"]["id"]
        print("✓ PASSED")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    headers = {}
    if token and workspace_id:
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Workspace-ID": workspace_id,
            "Content-Type": "application/json",
        }

    # 4. Memory Ingestion
    print("[4/8] Verifying Memory Vault Ingestion...", end=" ")
    mem_id = None
    try:
        if not token:
            raise RuntimeError("Authentication token not available.")
        mem_payload = {
            "content": f"Smoke test verification memory created at {time.time()}.",
            "category": "project",
            "importance": 8,
        }
        res = requests.post(f"{base_url}/api/v1/memories", json=mem_payload, headers=headers, timeout=10)
        assert res.status_code == 201, f"Expected 201, got {res.status_code} ({res.text})"
        mem_id = res.json()["data"]["id"]
        print("✓ PASSED")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    # 5. Hybrid Search Retrieval
    print("[5/8] Verifying Hybrid Search Retrieval Engine...", end=" ")
    try:
        if not token:
            raise RuntimeError("Authentication token not available.")
        search_payload = {
            "query": "verification memory smoke test",
            "top_k": 3,
            "include_memories": True,
            "include_documents": False,
        }
        res = requests.post(f"{base_url}/api/v1/search/hybrid", json=search_payload, headers=headers, timeout=10)
        assert res.status_code == 200, f"Expected 200, got {res.status_code} ({res.text})"
        results = res.json()["data"]["results"]
        assert len(results) >= 1, "Expected at least 1 search result"
        print(f"✓ PASSED (Found {len(results)} matches)")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    # 6. Knowledge Graph Extraction
    print("[6/8] Verifying Knowledge Graph Triplet Extractor...", end=" ")
    try:
        if not token:
            raise RuntimeError("Authentication token not available.")
        graph_payload = {
            "text": "Antigravity powers AI-MemoryVerse. Google Deepmind engineers create autonomous software."
        }
        res = requests.post(f"{base_url}/api/v1/graph/extract", json=graph_payload, headers=headers, timeout=10)
        assert res.status_code == 200, f"Expected 200, got {res.status_code} ({res.text})"
        print("✓ PASSED")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    # 7. Quota and Billing Telemetry
    print("[7/8] Verifying Quota Metering & Subscription State...", end=" ")
    try:
        if not token:
            raise RuntimeError("Authentication token not available.")
        res = requests.get(f"{base_url}/api/v1/billing/usage", headers=headers, timeout=10)
        assert res.status_code == 200, f"Expected 200, got {res.status_code} ({res.text})"
        usage = res.json()["data"]
        assert usage.get("plan_tier") == "free"
        assert usage["memories"]["used"] >= 1
        print("✓ PASSED")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    # 8. Agent Tool Registry Inspection
    print("[8/8] Verifying Controlled Agent Tool Registry...", end=" ")
    try:
        if not token:
            raise RuntimeError("Authentication token not available.")
        res = requests.get(f"{base_url}/api/v1/agents/tools", headers=headers, timeout=10)
        assert res.status_code == 200, f"Expected 200, got {res.status_code} ({res.text})"
        tools = res.json()["data"]["tools"]
        assert len(tools) >= 5, f"Expected at least 5 tools, got {len(tools)}"
        print(f"✓ PASSED ({len(tools)} tools verified)")
        passed_checks += 1
    except Exception as e:
        print(f"✗ FAILED: {e}")

    print(f"\n==================================================")
    print(f" Smoke Test Summary: {passed_checks}/{total_checks} Checks Passed")
    print(f" Success Rate: {(passed_checks / total_checks) * 100:.1f}%")
    print(f"==================================================")

    if passed_checks == total_checks:
        print("🚀 DEPLOYMENT HEALTH CONFIRMED: System is fully operational!")
        sys.exit(0)
    else:
        print("⚠️ SOME CHECKS FAILED: Review endpoint logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()


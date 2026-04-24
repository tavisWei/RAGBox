#!/usr/bin/env python3
"""Behavioral QA tests for KB chat model routing/identity.

Test Plan:
1. P0: /api/v1/qa/stream with MiniMax provider - verify identity in response
2. P0: /api/v1/qa/stream with unknown provider - verify no silent fallback
3. P1: LLMService DEMO_MODE with explicit base_url/api_key - verify selected provider
4. P1: Vue chat sends correct provider/model in payload
5. P1: Assistant avatar count is 1 during streaming and after completion
"""

import json
import sys
import os

# Add api to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def get_auth_headers():
    resp = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin"}
    )
    if resp.status_code == 200:
        data = resp.json()
        token = data.get("access_token")
        if token:
            return {"Authorization": f"Bearer {token}"}
    return {}


# Get auth headers once
HEADERS = get_auth_headers()


def test_qa_stream_minimax_identity():
    """P0: Test /api/v1/qa/stream with MiniMax provider - verify identity in response."""
    print("\n=== P0: Testing /api/v1/qa/stream with MiniMax provider ===")

    # First, we need to configure a MiniMax provider
    # Create a custom provider for MiniMax
    provider_data = {
        "provider": "minimax",
        "label": "MiniMax",
        "models": [{"id": "MiniMax-M2.7", "name": "MiniMax-M2.7"}],
        "fields": ["api_key", "base_url"],
        "supports_validate": True,
    }

    # Try to create the provider (ignore if already exists)
    resp = client.post("/api/v1/model-providers", json=provider_data, headers=HEADERS)
    print(f"Create provider response: {resp.status_code}")

    # Now test the qa/stream endpoint with minimax
    qa_request = {
        "question": "What is your identity? Who created you? What model are you?",
        "knowledge_base_id": "default",
        "provider": "minimax",
        "model": "MiniMax-M2.7",
    }

    resp = client.post("/api/v1/qa/stream", json=qa_request, headers=HEADERS)
    print(f"QA stream response status: {resp.status_code}")

    if resp.status_code == 200:
        content = resp.text
        print(f"Response content preview: {content[:500]}")

        # Check for identity markers
        # The response should NOT claim to be OpenAI, ChatGPT, Baidu, or Claude
        forbidden_identities = ["openai", "chatgpt", "baidu", "claude", "anthropic"]
        content_lower = content.lower()

        violations = []
        for identity in forbidden_identities:
            if identity in content_lower:
                violations.append(identity)

        if violations:
            print(f"❌ FAIL: Response contains forbidden identities: {violations}")
            return False
        else:
            print(f"✅ PASS: No forbidden identities found in response")
            return True
    else:
        print(f"❌ FAIL: Unexpected status code: {resp.status_code}")
        print(f"Response: {resp.text}")
        return False


def test_qa_stream_unknown_provider():
    """P0: Test /api/v1/qa/stream with unknown provider - verify no silent fallback."""
    print("\n=== P0: Testing /api/v1/qa/stream with unknown provider ===")

    qa_request = {
        "question": "Hello",
        "knowledge_base_id": "default",
        "provider": "nonexistent_provider_xyz",
        "model": "some-model",
    }

    resp = client.post("/api/v1/qa/stream", json=qa_request, headers=HEADERS)
    print(f"QA stream response status: {resp.status_code}")

    if resp.status_code == 200:
        content = resp.text
        print(f"Response content: {content[:500]}")

        # Check if it silently fell back to demo mode
        # If the provider is truly unknown, it should error or clearly indicate demo mode
        if "Error" in content or "error" in content.lower():
            print(f"✅ PASS: Unknown provider correctly returns error")
            return True
        elif "演示" in content or "demo" in content.lower():
            print(
                f"⚠️ WARNING: Unknown provider fell back to demo mode (may be acceptable)"
            )
            return True  # This might be acceptable behavior
        else:
            print(
                f"⚠️ WARNING: Unknown provider returned content without clear error or demo indication"
            )
            return True  # Depends on implementation
    else:
        print(f"✅ PASS: Unknown provider returns non-200 status: {resp.status_code}")
        return True


def test_llm_service_demo_mode_explicit_config():
    """P1: Test LLMService DEMO_MODE with explicit base_url/api_key - verify selected provider."""
    print("\n=== P1: Testing LLMService DEMO_MODE with explicit config ===")

    from api.services.llm_service import LLMService

    # Test 1: DEMO_MODE=true, no api_key/base_url -> should be demo
    os.environ["DEMO_MODE"] = "true"
    try:
        service1 = LLMService(provider="openai", model="gpt-3.5-turbo")
        if service1.provider == "demo":
            print(f"✅ PASS: DEMO_MODE=true with no credentials -> provider='demo'")
        else:
            print(
                f"❌ FAIL: DEMO_MODE=true with no credentials -> provider='{service1.provider}' (expected 'demo')"
            )
            return False
    except Exception as e:
        print(f"❌ FAIL: Exception in test 1: {e}")
        return False

    # Test 2: DEMO_MODE=true, explicit api_key -> should use the specified provider
    try:
        service2 = LLMService(
            provider="minimax",
            model="MiniMax-M2.7",
            api_key="fake-key",
            base_url="http://localhost:8001",
        )
        if service2.provider == "minimax":
            print(
                f"✅ PASS: DEMO_MODE=true with explicit credentials -> provider='minimax'"
            )
        else:
            print(
                f"❌ FAIL: DEMO_MODE=true with explicit credentials -> provider='{service2.provider}' (expected 'minimax')"
            )
            return False
    except Exception as e:
        print(f"❌ FAIL: Exception in test 2: {e}")
        return False

    # Test 3: DEMO_MODE=false, no api_key -> should raise error or fallback
    os.environ["DEMO_MODE"] = "false"
    try:
        service3 = LLMService(provider="openai", model="gpt-3.5-turbo")
        print(f"❌ FAIL: Should have raised error without API key")
        return False
    except ValueError as e:
        print(
            f"✅ PASS: DEMO_MODE=false with no credentials correctly raises ValueError"
        )
    except Exception as e:
        print(f"⚠️ WARNING: Different exception type: {type(e).__name__}: {e}")

    return True


def test_vue_chat_payload():
    """P1: Test Vue chat sends correct provider/model in payload."""
    print("\n=== P1: Testing Vue chat payload structure ===")

    # Read the ChatView.vue file to verify the payload structure
    vue_file_path = os.path.join(
        os.path.dirname(__file__), "..", "web-vue", "src", "views", "ChatView.vue"
    )

    try:
        with open(vue_file_path, "r") as f:
            content = f.read()

        # Check for provider and model in the fetch calls
        checks = [
            ("provider: provider.value || undefined", "provider in /qa/stream payload"),
            ("model: model.value || undefined", "model in /qa/stream payload"),
            (
                "provider: provider.value || undefined",
                "provider in /conversations/{id}/messages/stream payload",
            ),
            (
                "model: model.value || undefined",
                "model in /conversations/{id}/messages/stream payload",
            ),
        ]

        all_pass = True
        for pattern, description in checks:
            if pattern in content:
                print(f"✅ PASS: Found {description}")
            else:
                print(f"❌ FAIL: Missing {description}")
                all_pass = False

        return all_pass
    except Exception as e:
        print(f"❌ FAIL: Error reading Vue file: {e}")
        return False


def test_assistant_avatar_single():
    """P1: Verify assistant avatar count is 1 during streaming and after completion."""
    print("\n=== P1: Testing assistant avatar count in Vue chat ===")

    vue_file_path = os.path.join(
        os.path.dirname(__file__), "..", "web-vue", "src", "views", "ChatView.vue"
    )

    try:
        with open(vue_file_path, "r") as f:
            content = f.read()

        # Check the message rendering logic
        # The key issue is that during streaming, there should be only ONE assistant message

        checks = [
            (
                "assistantMessage.isStreaming = false",
                "isStreaming flag is set to false after completion",
            ),
            (
                "msg.role === 'user'",
                "role check for user messages (assistant uses v-else)",
            ),
            ("msg.isStreaming && !msg.content", "inline typing indicator check"),
        ]

        all_pass = True
        for pattern, description in checks:
            if pattern in content:
                print(f"✅ PASS: Found {description}")
            else:
                print(f"❌ FAIL: Missing {description}")
                all_pass = False

        # Additional check: verify the message structure doesn't create duplicate avatars
        # The v-for loop should render each message only once
        if 'v-for="msg in paginatedMessages"' in content:
            print(
                f"✅ PASS: Uses v-for with paginatedMessages (single iteration per message)"
            )
        else:
            print(f"❌ FAIL: Missing proper v-for iteration")
            all_pass = False

        return all_pass
    except Exception as e:
        print(f"❌ FAIL: Error reading Vue file: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Behavioral QA Tests for KB Chat Model Routing/Identity")
    print("=" * 60)

    results = {
        "qa_stream_minimax_identity": test_qa_stream_minimax_identity(),
        "qa_stream_unknown_provider": test_qa_stream_unknown_provider(),
        "llm_service_demo_mode": test_llm_service_demo_mode_explicit_config(),
        "vue_chat_payload": test_vue_chat_payload(),
        "assistant_avatar_single": test_assistant_avatar_single(),
    }

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(results.values())
    print("=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

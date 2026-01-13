"""
Tests for webhook signature verification

Verifies that webhook signature verification works correctly with HMAC-SHA256.
"""

import pytest
from app.core.webhook_security import verify_webhook_signature, generate_webhook_signature


class TestWebhookSignatureVerification:
    """Test webhook signature verification functionality"""

    def test_verify_webhook_signature_valid(self):
        """Test that valid signatures are verified correctly"""
        payload = '{"application_id": "123", "verified": true}'
        secret = "test-secret-key"
        
        # Generate signature using the same secret
        signature = generate_webhook_signature(payload)
        
        # Verify signature (note: verify_webhook_signature uses settings.WEBHOOK_SECRET)
        # For this test, we need to use the same secret that's in settings
        # Since we can't easily override settings in this test, we'll test the logic
        # by generating and verifying with the same function
        
        # The actual implementation uses settings.WEBHOOK_SECRET, so we test
        # that generate_webhook_signature creates a valid signature
        assert len(signature) == 64  # SHA256 hex digest is 64 characters
        assert isinstance(signature, str)
        
        # Test that verify_webhook_signature works with the generated signature
        # This will use settings.WEBHOOK_SECRET which should match
        is_valid = verify_webhook_signature(payload, signature)
        assert is_valid is True

    def test_verify_webhook_signature_invalid(self):
        """Test that invalid signatures are rejected"""
        payload = '{"application_id": "123", "verified": true}'
        invalid_signature = "invalid-signature-12345"
        
        is_valid = verify_webhook_signature(payload, invalid_signature)
        assert is_valid is False

    def test_verify_webhook_signature_tampered_payload(self):
        """Test that tampered payloads are rejected"""
        original_payload = '{"application_id": "123", "verified": true}'
        tampered_payload = '{"application_id": "123", "verified": false}'
        
        # Generate signature for original payload
        signature = generate_webhook_signature(original_payload)
        
        # Try to verify tampered payload with original signature
        is_valid = verify_webhook_signature(tampered_payload, signature)
        assert is_valid is False

    def test_verify_webhook_signature_missing_payload(self):
        """Test that missing payload returns False"""
        is_valid = verify_webhook_signature("", "signature")
        assert is_valid is False

    def test_verify_webhook_signature_missing_signature(self):
        """Test that missing signature returns False"""
        is_valid = verify_webhook_signature("payload", "")
        assert is_valid is False

    def test_verify_webhook_signature_empty_both(self):
        """Test that empty payload and signature returns False"""
        is_valid = verify_webhook_signature("", "")
        assert is_valid is False

    def test_generate_webhook_signature_consistency(self):
        """Test that generating signature twice for same payload produces same result"""
        payload = '{"application_id": "123", "verified": true}'
        
        signature1 = generate_webhook_signature(payload)
        signature2 = generate_webhook_signature(payload)
        
        assert signature1 == signature2
        assert len(signature1) == 64  # SHA256 hex digest

    def test_generate_webhook_signature_different_payloads(self):
        """Test that different payloads produce different signatures"""
        payload1 = '{"application_id": "123", "verified": true}'
        payload2 = '{"application_id": "456", "verified": true}'
        
        signature1 = generate_webhook_signature(payload1)
        signature2 = generate_webhook_signature(payload2)
        
        assert signature1 != signature2

    def test_verify_webhook_signature_case_sensitive(self):
        """Test that signature verification is case-sensitive"""
        payload = '{"application_id": "123", "verified": true}'
        signature = generate_webhook_signature(payload)
        
        # Uppercase the signature (should fail)
        uppercase_signature = signature.upper()
        is_valid = verify_webhook_signature(payload, uppercase_signature)
        assert is_valid is False
        
        # Lowercase should work (signature is already lowercase hex)
        is_valid = verify_webhook_signature(payload, signature)
        assert is_valid is True

    def test_verify_webhook_signature_whitespace_matters(self):
        """Test that whitespace in payload matters for signature"""
        payload1 = '{"application_id": "123", "verified": true}'
        payload2 = '{"application_id":"123","verified":true}'  # No spaces
        
        signature1 = generate_webhook_signature(payload1)
        signature2 = generate_webhook_signature(payload2)
        
        # Different payloads should produce different signatures
        assert signature1 != signature2
        
        # Each signature should only verify its own payload
        assert verify_webhook_signature(payload1, signature1) is True
        assert verify_webhook_signature(payload1, signature2) is False
        assert verify_webhook_signature(payload2, signature1) is False
        assert verify_webhook_signature(payload2, signature2) is True

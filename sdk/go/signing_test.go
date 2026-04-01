package hardenhmac

import (
	"testing"
)

const testSecret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24="

func TestSign_BasicGet(t *testing.T) {
	canonical := "GET\n/api/users\n\n\n1700000000"
	sig, err := Sign(testSecret, canonical)
	if err != nil {
		t.Fatalf("Sign returned error: %v", err)
	}
	expected := "9e0350740f4ac5444c58d10dbe4af08608916b287f517640877a2ea4145348a8"
	if sig != expected {
		t.Errorf("signature mismatch:\ngot:  %s\nwant: %s", sig, expected)
	}
}

func TestSign_OutputIs64Chars(t *testing.T) {
	sig, err := Sign(testSecret, "test")
	if err != nil {
		t.Fatalf("Sign returned error: %v", err)
	}
	if len(sig) != 64 {
		t.Errorf("expected 64 chars, got %d", len(sig))
	}
}

func TestSign_InvalidBase64(t *testing.T) {
	_, err := Sign("not-valid-base64!!!", "test")
	if err == nil {
		t.Error("expected error for invalid base64")
	}
}

func TestSign_EmptySecret(t *testing.T) {
	_, err := Sign("", "test")
	if err == nil {
		t.Error("expected error for empty secret")
	}
}

func TestVerify_ValidSignature(t *testing.T) {
	canonical := "GET\n/api/users\n\n\n1700000000"
	sig := "9e0350740f4ac5444c58d10dbe4af08608916b287f517640877a2ea4145348a8"
	ok, err := Verify(testSecret, canonical, sig)
	if err != nil {
		t.Fatalf("Verify returned error: %v", err)
	}
	if !ok {
		t.Error("expected valid signature")
	}
}

func TestVerify_InvalidSignature(t *testing.T) {
	canonical := "GET\n/api/users\n\n\n1700000000"
	ok, err := Verify(testSecret, canonical, "0000000000000000000000000000000000000000000000000000000000000000")
	if err != nil {
		t.Fatalf("Verify returned error: %v", err)
	}
	if ok {
		t.Error("expected invalid signature")
	}
}

func TestVerify_WrongLength(t *testing.T) {
	canonical := "GET\n/api/users\n\n\n1700000000"
	ok, err := Verify(testSecret, canonical, "short")
	if err != nil {
		t.Fatalf("Verify returned error: %v", err)
	}
	if ok {
		t.Error("expected invalid for wrong length")
	}
}

func TestVerify_InvalidBase64(t *testing.T) {
	_, err := Verify("not-valid!!!", "test", "sig")
	if err == nil {
		t.Error("expected error for invalid base64")
	}
}

func TestSign_DifferentSecretProducesDifferentSignature(t *testing.T) {
	canonical := "GET\n/api/health\n\n\n1700000008"
	sig1, _ := Sign(testSecret, canonical)
	sig2, _ := Sign("YW5vdGhlci10ZXN0LWtleS0yNTYtYml0cy1sb25nISE=", canonical)
	if sig1 == sig2 {
		t.Error("different secrets should produce different signatures")
	}
}

func TestVerify_ConstantTime(t *testing.T) {
	// This test verifies the function returns the correct result,
	// not timing properties (which require statistical analysis).
	canonical := "GET\n/test\n\n\n1000"
	sig, _ := Sign(testSecret, canonical)

	ok, err := Verify(testSecret, canonical, sig)
	if err != nil {
		t.Fatalf("error: %v", err)
	}
	if !ok {
		t.Error("expected valid")
	}

	// Flip one character
	tampered := "a" + sig[1:]
	ok, err = Verify(testSecret, canonical, tampered)
	if err != nil {
		t.Fatalf("error: %v", err)
	}
	if ok {
		t.Error("expected invalid for tampered signature")
	}
}

using FluentAssertions;

namespace HardenLabs.Hmac.Tests;

public class HmacSignerTests
{
    // Base64 of "test-secret-key-for-hmac-validation"
    private const string TestSecret = "dGVzdC1zZWNyZXQta2V5LWZvci1obWFjLXZhbGlkYXRpb24=";

    [Fact]
    public void Sign_ProducesLowercaseHex64Characters()
    {
        var sig = HmacSigner.Sign(TestSecret, "test data");

        sig.Should().HaveLength(64);
        sig.Should().MatchRegex("^[0-9a-f]{64}$");
    }

    [Fact]
    public void Sign_DeterministicForSameInputs()
    {
        var sig1 = HmacSigner.Sign(TestSecret, "canonical string");
        var sig2 = HmacSigner.Sign(TestSecret, "canonical string");

        sig1.Should().Be(sig2);
    }

    [Fact]
    public void Sign_DifferentInputsProduceDifferentSignatures()
    {
        var sig1 = HmacSigner.Sign(TestSecret, "input 1");
        var sig2 = HmacSigner.Sign(TestSecret, "input 2");

        sig1.Should().NotBe(sig2);
    }

    [Fact]
    public void Sign_DifferentKeysProduceDifferentSignatures()
    {
        var otherSecret = "YW5vdGhlci10ZXN0LWtleS0yNTYtYml0cy1sb25nISE=";
        var sig1 = HmacSigner.Sign(TestSecret, "same input");
        var sig2 = HmacSigner.Sign(otherSecret, "same input");

        sig1.Should().NotBe(sig2);
    }

    [Fact]
    public void Verify_ValidSignature_ReturnsTrue()
    {
        var canonical = "GET\n/api/test\n\n\n1700000000";
        var sig = HmacSigner.Sign(TestSecret, canonical);

        HmacSigner.Verify(TestSecret, canonical, sig).Should().BeTrue();
    }

    [Fact]
    public void Verify_InvalidSignature_ReturnsFalse()
    {
        var canonical = "GET\n/api/test\n\n\n1700000000";

        HmacSigner.Verify(TestSecret, canonical, "0000000000000000000000000000000000000000000000000000000000000000")
            .Should().BeFalse();
    }

    [Fact]
    public void Verify_TamperedCanonicalString_ReturnsFalse()
    {
        var canonical = "GET\n/api/test\n\n\n1700000000";
        var sig = HmacSigner.Sign(TestSecret, canonical);

        var tampered = "GET\n/api/test\n\n\n1700000001";
        HmacSigner.Verify(TestSecret, tampered, sig).Should().BeFalse();
    }

    [Fact]
    public void Sign_NullSecret_ThrowsArgumentNullException()
    {
        var act = () => HmacSigner.Sign(null!, "data");
        act.Should().Throw<ArgumentNullException>();
    }

    [Fact]
    public void Sign_NullCanonicalString_ThrowsArgumentNullException()
    {
        var act = () => HmacSigner.Sign(TestSecret, null!);
        act.Should().Throw<ArgumentNullException>();
    }
}

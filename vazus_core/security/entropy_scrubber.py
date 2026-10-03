"""
Shannon Entropy Secret Scrubber and Pre-Tool Sanitizer for Vazus OS.
Prevents accidental leaks of API tokens, SSH keys, credentials, and high-entropy secrets in LLM prompts or git commits.
"""

import math
import re
from collections import Counter


class SecretScrubber:
    """
    Two-layer secret detection: Regex pattern heuristics + Shannon information entropy scanner.
    """

    KNOWN_SECRET_PATTERNS = [
        # Google API Key
        re.compile(r"AIza[0-9A-Za-z-_]{35}"),
        # GitHub Personal Access Token (classic & fine-grained)
        re.compile(r"ghp_[0-9a-zA-Z]{36}"),
        re.compile(r"github_pat_[0-9a-zA-Z_]{82}"),
        # OpenAI & Anthropic API keys
        re.compile(r"sk-[a-zA-Z0-9]{32,64}"),
        re.compile(r"sk-ant-[a-zA-Z0-9-_]{32,100}"),
        # AWS Access Key & Secret
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r'(?i)aws_secret_access_key\s*[:=]\s*["\']?([A-Za-z0-9/+=]{40})["\']?'),
        # Generic Secret assignments
        re.compile(
            r'(?i)(?:api_key|secret_key|private_key|auth_token|bearer_token|password)[ \t]*[:=][ \t]*["\']?([a-zA-Z0-9_\-\.\$\@]{12,})["\']?'
        ),
        # Private Key Headers
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ]

    def __init__(self, entropy_threshold: float = 4.65, min_token_len: int = 24):
        self.entropy_threshold = entropy_threshold
        self.min_token_len = min_token_len

    @staticmethod
    def calculate_shannon_entropy(data: str) -> float:
        """
        Calculates the Shannon entropy H(S) = -sum(p * log2(p)) in bits per character.
        High-entropy random tokens (>4.65) indicate cryptographically generated keys/hashes.
        """
        if not data:
            return 0.0
        length = len(data)
        counts = Counter(data)
        entropy = 0.0
        for count in counts.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    def scrub(self, text: str) -> str:
        """
        Scrubs secrets from the input text, replacing them with sanitized placeholders.
        """
        if not text:
            return text

        scrubbed = text

        # Layer 1: Known Regex Heuristics
        for pattern in self.KNOWN_SECRET_PATTERNS:
            scrubbed = pattern.sub(r"[REDACTED_SECRET]", scrubbed)

        # Layer 2: High-Entropy Token Detection for Unformatted Keys
        tokens = re.split(r'[\s"\'=,;:<>/\\]+', scrubbed)
        for token in tokens:
            cleaned = token.strip()
            # Ignore standard URLs, file paths, and normal snake_case/camelCase code identifiers
            if len(cleaned) >= self.min_token_len:
                if not (
                    cleaned.startswith("http://") or cleaned.startswith("https://") or cleaned.startswith("file:///")
                ):
                    # If it contains multiple underscores, it's code (e.g. function_name_identifier)
                    if cleaned.count("_") >= 2 and all(part.isalnum() for part in cleaned.split("_") if part):
                        continue
                    entropy = self.calculate_shannon_entropy(cleaned)
                    if entropy >= self.entropy_threshold:
                        # Cryptographic secrets have high character diversity (mix of upper, lower, digits, symbols)
                        has_upper = any(c.isupper() for c in cleaned)
                        has_lower = any(c.islower() for c in cleaned)
                        has_digit = any(c.isdigit() for c in cleaned)
                        if has_upper and has_lower and has_digit:
                            scrubbed = scrubbed.replace(cleaned, f"[REDACTED_HIGH_ENTROPY_KEY(H={entropy:.2f})]")

        return scrubbed
